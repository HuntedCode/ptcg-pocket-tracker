from collections import defaultdict
import colorsys
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q, F
from django.http import JsonResponse, HttpResponseRedirect, Http404
from django.urls import reverse
from django.utils import timezone
import json
from .models import UserCollection, Set, UserWant, Card, Message, Booster, BoosterDropRate, Profile, Activity, Match
import random
from tcg_collections.forms import CustomUserCreationForm, ProfileForm, MessageForm, TradeWantForm
from .utils import FREE_TRADE_SLOTS, PREMIUM_TRADE_SLOTS, THEME_COLORS, TRAINER_CLASSES

# Create your views here.

# User Views

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Auto login after registering
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def profile(request, token):
    profile = get_object_or_404(Profile, share_token=token)
    user = get_object_or_404(User, profile=profile)
    is_own = request.user == user

    if request.method == 'POST':
        form = ProfileForm(request.POST ,instance=profile)
        if is_own and form.is_valid():
            form.save()
        else:
            print("Post-valid errors:", form.errors, form.non_field_errors())

        return redirect('profile', token=profile.share_token)

    form = ProfileForm(instance=profile) if is_own else None
    total_unique_cards = UserCollection.objects.filter(user=user).aggregate(owned=Count('card', distinct=True))['owned']

    BASE_RARITIES = ['One Diamond', 'Two Diamond', 'Three Diamond', 'Four Diamond']
    OTHER_RARITIES = ['One Star', 'Two Star', 'Three Star', 'One Shiny', 'Two Shiny', 'Crown']

    set_breakdowns = []
    all_sets = Set.objects.exclude(name__contains='Promo').order_by('tcg_id')

    for set_obj in all_sets:
        total_base_in_set = Card.objects.filter(card_set=set_obj, rarity__in=BASE_RARITIES).count()
        owned_base_in_set = UserCollection.objects.filter(user=user, card__card_set=set_obj, card__rarity__in=BASE_RARITIES).aggregate(owned=Count('card', distinct=True))['owned'] or 0
        base_completion = (owned_base_in_set / total_base_in_set * 100) if total_base_in_set else 0
        total_rare_in_set = Card.objects.filter(card_set=set_obj, rarity__in=OTHER_RARITIES).count()
        owned_rare_in_set = UserCollection.objects.filter(user=user, card__card_set=set_obj, card__rarity__in=OTHER_RARITIES).aggregate(owned=Count('card', distinct=True))['owned'] or 0
        rare_completion = (owned_rare_in_set / total_rare_in_set * 100) if total_rare_in_set else 0

        set_breakdowns.append({
            'set': set_obj,
            'owned_base': owned_base_in_set,
            'total_base': total_base_in_set,
            'base_completion': round(base_completion, 1),
            'owned_rare': owned_rare_in_set,
            'total_rare': total_rare_in_set,
            'rare_completion': round(rare_completion, 1)
        })
    
    displayed_favorites=  []
    if profile.display_favorites:
        displayed_favorites = Card.objects.filter(id__in=profile.display_favorites).order_by('tcg_id')

    activities = Activity.objects.filter(user=user).order_by('-timestamp')[:10]
    feed = []
    for activity in activities:
        try:
            parsed = json.loads(activity.content)
            cards = []
            card_id = parsed.get('card_id')
            if (card_id):
                cards.append(Card.objects.filter(id=int(card_id)).first())
            else:
                details = parsed.get('details')
                if (details):
                    for card_details in details:
                        cards.append(Card.objects.filter(id=int(card_details[0])).first())

        except json.JSONDecodeError:
            parsed = {'message': 'Invalid activity data'}
        feed.append({
            'type': activity.type,
            'timestamp': activity.timestamp,
            'parsed_content': parsed,
            'cards': cards
        })

    def hex_to_rgb(hex_str):
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    
    def rgb_to_hex(rgb):
        return '#%02x%02x%02x' % tuple(int(c * 255) for c in rgb)
    
    def generate_bases(primary_hex):
        rgb = hex_to_rgb(primary_hex)
        h, s, v = colorsys.rgb_to_hsv(*rgb)

        base_100 = rgb_to_hex(colorsys.hsv_to_rgb(h, max(0, s - 0.6), 0.78))
        base_200 = rgb_to_hex(colorsys.hsv_to_rgb(h, max(0, s - 0.55), 0.75))
        base_300 = rgb_to_hex(colorsys.hsv_to_rgb(h, max(0, s - 0.5), 0.72))
        return base_100, base_200, base_300

    theme_key = profile.theme
    colors = THEME_COLORS.get(theme_key, THEME_COLORS['default'])
    primary = colors['primary']
    accent = colors['accent']
    if theme_key == 'default':
        base_100, base_200, base_300 = '#F3F8FC', '#E8F0F5', '#DCE6EE'
    else:
        base_100, base_200, base_300 = generate_bases(primary)
    theme = {'primary': primary, 'accent': accent, 'base_100':base_100, 'base_200': base_200, 'base_300': base_300}

    context = {'form': form, 'profile': profile, 'is_own': is_own, 'total_unique_cards': total_unique_cards, 'all_sets': all_sets, 'set_breakdowns': set_breakdowns, 'displayed_favorites': displayed_favorites, 'feed': feed, 'theme': theme}

    if is_own:
        fav_cards = Card.objects.filter(
            usercollection__user=user,
            usercollection__is_favorite=True,
            usercollection__quantity__gt=0
        ).distinct().order_by('tcg_id')

        fav_sets = fav_cards.values('card_set__id', 'card_set__name').distinct().order_by('card_set__tcg_id')
        fav_rarities = fav_cards.values_list('rarity', flat=True).distinct()

        context['fav_cards'] = fav_cards
        context['fav_sets'] = [(set['card_set__id'], set['card_set__name']) for set in fav_sets]
        context['fav_rarities'] = sorted(set(fav_rarities))

    return render(request, 'profile.html', context)

@login_required
def inbox(request):
    received = Message.objects.filter(receiver=request.user).order_by('-timestamp')
    sent = Message.objects.filter(sender=request.user).order_by('-timestamp')
    context = {'received': received, 'sent': sent}
    return render(request, 'inbox.html', context)

@login_required
def send_message(request, receiver_id):
    receiver = get_object_or_404(User, id=receiver_id)
    if not receiver.profile.is_trading_active or not request.user.profile.is_trading_active:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.receiver = receiver
            message.save()
            return redirect('inbox')
    else:
        form = MessageForm()
    return render(request, 'send_message.html', {'form': form, 'receiver': receiver.username})

@login_required
def toggle_dark_mode(request):
    if request.method == 'POST':
        profile = request.user.profile
        profile.dark_mode = not profile.dark_mode
        profile.save()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/profile/' + str(profile.share_token)))
    return HttpResponseRedirect('/')

# Trade Match Views

@login_required
def trade_matches(request):
    form = TradeWantForm(user=request.user)
    matches = []
    if request.method == 'POST':
        form = TradeWantForm(request.POST, user=request.user)
        if form.is_valid():
            wanted_card = form.cleaned_data['wanted_card'].card
            rarity = wanted_card.rarity

            my_profile = request.user.profile
            my_haves = UserCollection.objects.filter(
                user=request.user,
                quantity__gt=my_profile.trade_threshold,
                card__rarity=rarity,
                card__is_tradeable=True
            ).select_related('card')

            potential_users = User.objects.filter(
                profile__is_trading_active=True,
                profile__last_active__gte=timezone.now() - timedelta(days=7),
                usercollection__card=wanted_card,
                usercollection__quantity__gt=F('profile__trade_threshold')
            ).distinct()[:10]

            filtered_users = []
            for user in potential_users:
                recipient_slots = get_trade_slots(user)
                if recipient_slots['incoming_free'] > 0:
                    filtered_users.append(user)
            potential_users = filtered_users

            for user in potential_users:
                their_wants = UserWant.objects.filter(
                    user=user,
                    desired_quantity__gt=0,
                    card__rarity=rarity
                ).select_related('card')

                possible_offers_qs = my_haves.filter(card__in=their_wants.values_list('card', flat=True))
                
                same_set_offers = possible_offers_qs.filter(card__card_set=wanted_card.card_set)
                if same_set_offers.exists():
                    best_offer = same_set_offers.order_by('-quantity').first()
                else:
                    if possible_offers_qs.exists():
                        best_offer = possible_offers_qs.order_by('-quantity').first()
                    else:
                        best_offer = None

                if best_offer:
                    random_class = random.choice(TRAINER_CLASSES)
                    random_num = f"{random.randint(0, 9999):04d}"
                    anon_name = f"{random_class} {random_num}"

                    matches.append({
                        'recipient': user,
                        'received_card': wanted_card,
                        'offered_card': best_offer.card,
                        'is_same_set': same_set_offers.exists(),
                        'anon_name': anon_name
                    })
    
    context = {'form': form, 'matches': matches, 'slots': get_trade_slots(request.user)}
    return render(request, 'trade_matches.html', context)

@login_required
def propose_trades(request):
    if request.method != 'POST':
        return redirect('trade_matches')
    
    selected = request.POST.getlist('selected_matches')
    errors = []
    created_matches = []
    slots = get_trade_slots(request.user)
    if len(selected) > slots['outgoing_free']:
        errors.append(f"Not enough free outgoing slots ({slots['outgoing_occupied']}/{FREE_TRADE_SLOTS if not request.user.profile.is_premium else PREMIUM_TRADE_SLOTS} occupied.) Rescind some pending trades to free up slots!")

    if not errors:
        for sel in selected:
            try:
                rec_id, rec_card_id, off_card_id = map(int, sel.split('|'))
                recipient = get_object_or_404(User, id=rec_id)
                received_card = get_object_or_404(Card, id=rec_card_id)
                offered_card = get_object_or_404(Card, id=off_card_id)

                if recipient == request.user:
                    errors.append('Cannot trade with self.')
                    continue

                if Match.objects.filter(
                    initiator=request.user, recipient=recipient, status='pending', 
                    received_card=received_card, offered_card=offered_card
                ).exists():
                    errors.append('Duplicate proposal.')
                    continue
                
                match = Match.objects.create(
                    initiator=request.user, recipient=recipient, status='pending',
                    received_card=received_card, offered_card=offered_card
                )
                created_matches.append(match)
            except ValueError:
                errors.append('Invalid selection.')        
    else:
        return render(request, 'trade_matches.html', {'errors': errors})
    
    return redirect('trade_matches')

@login_required
def trade_detail(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    print(match)
    if request.user not in [match.initiator, match.recipient]:
        raise Http404("Not authorized.")

    if request.method == 'POST':
        action = request.POST.get('action')
        if match.status == 'pending:':
            if request.user == match.recipient:
                if action == 'accept':
                    match.status = 'accepted'
                elif action == 'deny':
                    match.status = 'rejected'
            elif request.user == match.initiator:
                if action == 'rescind':
                    match.status = 'rejected'
        match.save()
        return redirect('trade_detail', match_id=match.id)
    
    context = {'match': match, 'match_id': match_id}
    return render(request, 'trade_detail.html', context)

def get_trade_slots(user):
    current_month = timezone.now().date().replace(day=1)
    if user.profile.last_trade_month != current_month:
        user.profile.accepted_trades_this_month = 0
        user.profile.last_trade_month = current_month
        user.profile.save()

    outgoing_pendings = Match.objects.filter(initiator=user, status='pending').prefetch_related('offered_card', 'received_card').order_by('-created_at')
    incoming_pendings = Match.objects.filter(recipient=user, status='pending').prefetch_related('offered_card', 'received_card').order_by('-created_at')

    outgoing_accepteds = Match.objects.filter(initiator=user, status='accepted').prefetch_related('offered_card', 'received_card').order_by('-created_at')
    incoming_accepteds = Match.objects.filter(recipient=user, status='accepted').prefetch_related('offered_card', 'received_card').order_by('-created_at')

    outgoing_occupied = outgoing_pendings.count() + outgoing_accepteds.count()
    incoming_occupied = incoming_pendings.count() + incoming_accepteds.count()

    base_slots = PREMIUM_TRADE_SLOTS if user.profile.is_premium else FREE_TRADE_SLOTS
    outgoing_free = base_slots - outgoing_occupied
    incoming_free = base_slots - incoming_occupied

    return {
        'base_slots': base_slots,
        'premium_slots': PREMIUM_TRADE_SLOTS,
        'outgoing_occupied': outgoing_occupied,
        'outgoing_free': max(0, outgoing_free),
        'incoming_occupied': incoming_occupied,
        'incoming_free': max(0, incoming_free),
        'outgoing_pendings': outgoing_pendings,
        'incoming_pendings': incoming_pendings,
        'outgoing_accepteds': outgoing_accepteds,
        'incoming_accepteds': incoming_accepteds
    }

@login_required
def accept_match(request, match_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    match = get_object_or_404(Match, id=match_id, recipient=request.user)
    match.status = 'accepted'
    match.save()
    # Add friend later?
    return JsonResponse({'success': 'Match accepted!'})

@login_required
def reject_match(request, match_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    match = get_object_or_404(Match, id=match_id, recipient=request.user)
    match.status = 'rejected'
    match.save()
    return JsonResponse({'success': 'Match rejected!'})

@login_required
def ignore_match(request, match_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    match = get_object_or_404(Match, id=match_id, recipient=request.user)
    match.status = 'ignored'
    match.save()
    return JsonResponse({'success': 'Match ignored!'})

# Collection Views

@login_required
def dashboard(request):
    collections = UserCollection.objects.filter(user=request.user).select_related('card', 'card__card_set').order_by('card__card_set__tcg_id', 'card__tcg_id')
    wants = UserWant.objects.filter(user=request.user).select_related('card', 'card__card_set').order_by('card__card_set__tcg_id', 'card__tcg_id')
    total_cards = collections.aggregate(total=Sum('quantity'))['total'] or 0
    sets_summary = collections.values('card__card_set__id', 'card__card_set__name').annotate(
        count=Count('card', distinct=True),
        total_quantity=Sum('quantity')
    ).order_by('card__card_set__name')

    for summary in sets_summary:
        set_obj = Set.objects.get(id=summary['card__card_set__id'])
        summary['completion'] = (summary['count'] / set_obj.card_count_total * 100) if set_obj.card_count_total else 0
    
    rarity_stats = collections.values('card__rarity').annotate(
        owned_count=Count('card', distinct=True),
        total_quantity=Sum('quantity')
    ).order_by('card__rarity')

    booster_probs_by_set = defaultdict(list)
    boosters = Booster.objects.all()
    for booster in boosters:
        drop_rates = BoosterDropRate.objects.filter(booster=booster)
        normal_prob = 0.0
        god_prob = 0.0
        sixth_prob = 0.0
        total_prob = 0.0

        for rate in drop_rates:
            total_in_rarity = Card.objects.filter(rarity=rate.rarity, boosters=booster).count()
            if total_in_rarity == 0:
                continue
            missing_in_rarity = Card.objects.filter(rarity=rate.rarity, boosters=booster).exclude(id__in=collections.values_list('card__id', flat=True)).count()

            slot_rarity_prob = rate.probability * (missing_in_rarity / total_in_rarity if total_in_rarity else 0)
            if rate.slot in ['1-3', '4', '5']:
                normal_prob += slot_rarity_prob
            elif rate.slot == 'god':
                god_prob += slot_rarity_prob
            elif rate.slot == '6':
                sixth_prob += slot_rarity_prob

        total_prob += (normal_prob / 5) + (booster.god_pack_prob * god_prob) + (booster.sixth_card_prob * sixth_prob)
        primary_set = booster.sets.first()
        set_name = primary_set.name if primary_set else 'Unknown Set'
        booster_probs_by_set[set_name].append((booster.name, (total_prob * 100)))

    for set_name in booster_probs_by_set:
        booster_probs_by_set[set_name].sort(key=lambda x: x[1], reverse=True)

    context = {
        'collections': collections,
        'wants': wants,
        'total_cards': total_cards,
        'sets_summary': sets_summary,
        'rarity_stats': rarity_stats,
        'booster_probs_by_set': dict(booster_probs_by_set)
    }
    return render(request, 'dashboard.html', context)

@login_required
def tracker(request, set_id):
    set_obj = get_object_or_404(Set, id=set_id)
    all_sets = Set.objects.all().order_by('tcg_id')
    cards = Card.objects.filter(card_set=set_obj).order_by('tcg_id')

    owned = UserCollection.objects.filter(user=request.user, card__card_set=set_obj).values_list('card__id', 'quantity', 'is_favorite')
    owned_dict = {cid: (qty, is_fav) for cid, qty, is_fav in owned}
    wants = UserWant.objects.filter(user=request.user, card__card_set=set_obj).values_list('card__id', flat=True)

    errors = []

    if request.method == 'POST':
        print(request.POST)
        for key in request.POST:
            if key.startswith('quantity_'):
                card_id_str = key[9:]
                try:
                    card_id = int(card_id_str)
                    card= get_object_or_404(Card, id=card_id)
                    collection = UserCollection.objects.filter(user=request.user, card=card).first()
                except ValueError:
                    errors.append(f"Invalid card ID '{card_id_str}'")

                qty_str = request.POST.get(f"quantity_{card_id}", None)
                try:
                    qty = int(qty_str)
                    if qty < 0:
                        errors.append(f"Quantity for card '{card_id}' cannot be negative.")
                    
                    if collection is None:
                        if qty > 0:
                            collection = UserCollection(user=request.user, card=card, quantity=qty)
                            collection.save()
                    elif qty > 0:
                        collection.quantity = qty

                        if qty >= 2:
                            want = UserWant.objects.filter(user=request.user, card=card)
                            if want:
                                want.delete()

                        collection.save()
                    elif qty == 0:
                        collection.delete()
                except ValueError:
                    errors.append(f"Invalid quantity for card Id {card_id}")

            elif key.startswith('want_toggle_'):
                card_id_str = key[12:]
                try:
                    card_id = int(card_id_str)
                    card = get_object_or_404(Card, id=card_id)
                    want_obj = UserWant.objects.filter(user=request.user, card=card).first()
                    collection = UserCollection.objects.filter(user=request.user, card=card).first()
                    qty = collection.quantity if collection else 0

                    if want_obj:
                        want_obj.delete()
                    else:
                        if qty > 1:
                            errors.append(f"Cannot add {card.name} to wishlist, user already owns 2+ copies.")
                        UserWant.objects.create(user=request.user, card=card, desired_quantity=1)
                except ValueError:
                    errors.append(f"Invalid card ID for wishlist: '{card_id_str}'")
                    continue

            elif key.startswith('favorite_toggle_'):
                card_id_str = key[16:]
                try:
                    card_id = int(card_id_str)
                    card = get_object_or_404(Card, id=card_id)
                    collection = UserCollection.objects.filter(user=request.user, card=card).first()
                    if collection and collection.quantity > 0:
                        collection.is_favorite = not collection.is_favorite
                        collection.save()
                    else:
                        errors.append(f"Cannot favorite unowned card ID {card_id}")
                except ValueError:
                    errors.append(f"Invalid card ID for favorite: {card_id_str}")

        if not errors:
            owned = UserCollection.objects.filter(user=request.user, card__card_set=set_obj).values_list('card__id', 'quantity', 'is_favorite')
            owned_dict = {cid: (qty, is_fav) for cid, qty, is_fav in owned}
            wants = UserWant.objects.filter(user=request.user, card__card_set=set_obj).values_list('card__id', flat=True)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':  # Detect AJAX
                return JsonResponse({'status': 'success', 'message': 'Changes saved!'})
            else:
                return redirect('collection', set_id=set_id)  # Fallback for non-AJAX
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'errors': errors}, status=400)
                
    context = {
        'set': set_obj,
        'sets': all_sets,
        'set_id': set_id,
        'cards': cards,
        'owned_dict': owned_dict,
        'wants': set(wants),
        'errors': errors,
    }
    return render(request, 'tracker.html', context)

@login_required
def pack_opener(request):

    def log_pack_open(user, booster, cards_added):
        if not cards_added:
            return
        
        card_details = [(card.id, card.tcg_id, card.name) for card in cards_added]
        set_name = booster.sets.first().name if booster.sets.exists() else 'Unknown'
        content = json.dumps({'message': f"{booster.name} ({set_name}) Pack", 'details': card_details})
        Activity.objects.create(user=user, type='pack_open', content=content)

    if request.method == 'POST':
        errors = []
        booster_id = request.POST.get('booster_id')
        selected_cards_str = request.POST.get('selected_cards')
        if not booster_id or not selected_cards_str:
            errors.append('Missing booster or card selections.')
        else:
            try:
                selected_cards = json.loads(selected_cards_str)
                commons = selected_cards.get('commons', [])
                others = selected_cards.get('others', [])
                booster = get_object_or_404(Booster, id=booster_id)

                cards_selected = []
                for card_id in commons:
                    card = get_object_or_404(Card, id=card_id)
                    cards_selected.append(card)
                    if card not in booster.cards.all() or card.rarity != 'One Diamond':
                        errors.append(f"Invalid common card {card.name}")
                    else:
                        obj, created = UserCollection.objects.get_or_create(user=request.user, card=card, defaults={'quantity': 1, 'is_seen': False})
                        if not created:
                            obj.quantity += 1
                            obj.save()

                for card_id in others:
                    card = get_object_or_404(Card, id=card_id)
                    cards_selected.append(card)
                    if card not in booster.cards.all() or card.rarity == 'One Diamond':
                        errors.append(f"Invalid other card {card.name}")
                    else:
                        obj, created = UserCollection.objects.get_or_create(user=request.user, card=card, defaults={'quantity': 1, 'is_seen': False})
                        if not created:
                            obj.quantity += 1
                            obj.save()

                log_pack_open(request.user, booster, cards_selected)

                if errors:
                    sets = Set.objects.all().prefetch_related('boosters').order_by('-tcg_id')
                    return render(request, 'pack_opener.html', {'sets': sets, 'errors': errors})
                return redirect('pack_opener')
            except json.JSONDecodeError:
                errors.append('Invalid selection data.')

        sets = Set.objects.all().prefetch_related('boosters').order_by('-tcg_id')
        return render(request, 'pack_opener.html', {'sets': sets, 'errors': errors})
    
    sets = Set.objects.all().prefetch_related('boosters').order_by('-tcg_id')
    return render(request, 'pack_opener.html', {'sets': sets})

@login_required
def get_booster_cards(request):
    booster_id = request.GET.get('booster_id')
    if not booster_id:
        return JsonResponse({'error': 'No booster selected'}, status=400)
    
    booster = get_object_or_404(Booster, id=booster_id)
    cards = booster.cards.all().order_by('card_set__tcg_id', 'tcg_id')

    commons = cards.filter(rarity='One Diamond')
    others = cards.exclude(rarity='One Diamond')

    common_list = [
        {'id': c.id, 'name': c.name, 'image': c.local_image_small, 'rarity': c.rarity, 'tcg_id': c.tcg_id}
        for c in commons    
    ]

    others_list = [
        {'id': c.id, 'name': c.name, 'image': c.local_image_small, 'rarity': c.rarity, 'tcg_id': c.tcg_id}
        for c in others    
    ]

    return JsonResponse({
        'commons': common_list,
        'others': others_list,
        'booster_image': booster.local_image_small if booster.local_image_small else ''
    })

@login_required
def wishlist(request, token):
    profile = get_object_or_404(Profile, share_token=token)  
    share_url = request.build_absolute_uri(reverse('wishlist', args=[profile.share_token]))

    def get_sorted_wants():
        wants = UserWant.objects.filter(user=profile.user).select_related('card', 'card__card_set').order_by('card__card_set__tcg_id', 'card__tcg_id')
        wants_by_set = defaultdict(list)
        for want in wants:
            if profile.user == request.user:
                wants_by_set[want.card.card_set].append(want)
            else:
                obj = UserCollection.objects.filter(user=request.user, card=want.card).first()
                calling_user_has_for_trade = obj and obj.quantity > request.user.profile.trade_threshold
                wants_by_set[want.card.card_set].append((want, calling_user_has_for_trade))

        return sorted(wants_by_set.items(), key=lambda x: x[0].tcg_id)

    errors = []
    sorted_sets = get_sorted_wants()

    if request.method == 'POST':
        if profile.user != request.user:
            print("Error: User attempted to edit wishlist of a separate user.")
            return redirect('dashboard')
        
        for key in request.POST:
            if key.startswith('remove_want_'):
                card_id_str = key[12:]
                try:
                    card_id = int(card_id_str)
                    want_obj = UserWant.objects.filter(user=request.user, card__id=card_id).first()
                    if want_obj:
                        want_obj.delete()
                    else:
                        errors.append(f"Want for card ID {card_id} not found.")
                except ValueError:
                    errors.append(f"Invalid card ID: {card_id_str}")
        
        sorted_sets = get_sorted_wants()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            if errors:
                return JsonResponse({'status': 'error', 'errors': errors}, status=400)
            return JsonResponse({'status': 'success', 'message': 'Wishlist updated!'})
        else:
            return redirect('wishlist')
    
    context = {
        'profile': profile,
        'share_url': share_url,
        'sorted_sets': sorted_sets,
        'errors': errors,
    }

    return render(request, 'wishlist.html', context)

@login_required
def collection(request):
    def get_sorted_sets(collections, show_unowned):
        owned_dict = {item.card.id: item for item in collections}
        sorted_sets = []

        if not show_unowned:
            # Owned only
            owned_by_set = defaultdict(list)
            for item in collections:
                owned_by_set[item.card.card_set].append(item)
            set_tuples = sorted(owned_by_set.items(), key=lambda x: x[0].tcg_id)

            for set_obj, items in set_tuples:
                owned_count = len(items)
                items = [{
                    'card': col.card,
                    'quantity': col.quantity,
                    'collection': col
                } for col in items]
                has_unseen = any(not item['collection'].is_seen for item in items)
                sorted_sets.append((set_obj, items, owned_count, 0, has_unseen))
        else:
            # Full Set
            all_sets = Set.objects.all().order_by('tcg_id')
            for set_obj in all_sets:
                all_cards = Card.objects.filter(card_set=set_obj).order_by('tcg_id')
                items = []
                owned_count = 0
                for card in all_cards:
                    owned_item = owned_dict.get(card.id)
                    quantity = owned_item.quantity if owned_item else 0
                    items.append({
                        'card': card,
                        'quantity': quantity,
                        'collection': owned_item
                    })
                    if quantity > 0:
                        owned_count += 1
                if items:
                    unowned_count = len(items) - owned_count
                    has_unseen = any(item['collection'] and not item['collection'].is_seen for item in items)
                    sorted_sets.append((set_obj, items, owned_count, unowned_count, has_unseen))
        return sorted_sets 

    errors = []
    collections = UserCollection.objects.filter(user=request.user).select_related('card', 'card__card_set').order_by('card__card_set__tcg_id', 'card__tcg_id')
    show_unowned = request.GET.get('show_unowned', '0') == '1'
    sorted_sets = get_sorted_sets(collections, show_unowned)

    if request.method == 'POST':
        for key in request.POST:
            if key.startswith('mark_seen_'):
                item_id_str = key[10:]
                try:
                    item_id = int(item_id_str)
                    collection_item = collections.filter(id=item_id).first()
                    if collection_item:
                        collection_item.is_seen = True
                        collection_item.save()
                    else:
                        errors.append(f"Item ID {item_id} not found.")
                except ValueError:
                    errors.append(f"Invalid item ID: {item_id_str}")

        sorted_sets = get_sorted_sets(collections, show_unowned)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            unseen_count = UserCollection.objects.filter(user=request.user, is_seen=False).count()
            set_id = collection_item.card.card_set.id
            set_has_unseen = collections.filter(card__card_set__id=set_id).filter(is_seen=False).exists()
            return JsonResponse({'status': 'success', 'message': 'Collection updated!', 'unseen_count': unseen_count, 'set_id': set_id, 'has_unseen': set_has_unseen} if not errors else {'status': 'error', 'errors': errors}, status=200 if not errors else 400)
        else:
            return redirect('collection')
    
    context = {
        'sorted_sets': sorted_sets,
        'show_unowned': show_unowned,
        'errors': errors,
    }
    return render(request, 'collection.html', context)