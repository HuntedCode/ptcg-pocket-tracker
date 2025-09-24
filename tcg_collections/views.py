from collections import defaultdict
import colorsys
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncWeek
from django.http import JsonResponse, HttpResponseRedirect, Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.generic import TemplateView, View, RedirectView
import logging
import json
from .models import UserCollection, Set, UserWant, Card, Message, Booster, Profile, Activity, Match, PackPickerData, PackPickerBooster, PackPickerRarity, DailyStat, User
import random
from tcg_collections.forms import RegistrationForm, ProfileForm, MessageForm, TradeWantForm
from .utils import FREE_TRADE_SLOTS, PREMIUM_TRADE_SLOTS, THEME_COLORS, TRAINER_CLASSES, BASE_RARITIES, RARE_RARITIES, RARITY_ORDER

# Create your views here.

# Root Redirect
class RootRedirectView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return reverse('dashboard')
        return reverse('login')

# User Views

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            link = request.build_absolute_uri(reverse('confirm_email', args=(uid, token)))
            send_mail('Confirm Your Registration', f'Click to confirm: {link}', 'admin@pockettracker.io', [user.email],)
            messages.success(request, 'Confirmation email sent.')
            return redirect('login')
    else:
        form = RegistrationForm()
    return render(request, 'registration/register.html', {'form': form})

def confirm_email(request, uidb64, token):
    print('Confirming email')
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        print('Confirmation failed...')
        user = None
    if user and default_token_generator.check_token(user, token):
        print('Confirmed user and token...')
        user.is_active = True
        user.save()
        messages.success(request, 'Account confirmed. Login.')
        return redirect('login')
    print('Invalid user or token')
    messages.error(request, 'Invalid confirmation link.')
    return redirect('login')

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

    set_breakdowns = []
    all_sets = Set.objects.exclude(name__contains='Promo').order_by('tcg_id')

    for set_obj in all_sets:
        total_base_in_set = Card.objects.filter(card_set=set_obj, rarity__in=BASE_RARITIES).count()
        owned_base_in_set = UserCollection.objects.filter(user=user, card__card_set=set_obj, card__rarity__in=BASE_RARITIES).aggregate(owned=Count('card', distinct=True))['owned'] or 0
        base_completion = (owned_base_in_set / total_base_in_set * 100) if total_base_in_set else 0
        total_rare_in_set = Card.objects.filter(card_set=set_obj, rarity__in=RARE_RARITIES).count()
        owned_rare_in_set = UserCollection.objects.filter(user=user, card__card_set=set_obj, card__rarity__in=RARE_RARITIES).aggregate(owned=Count('card', distinct=True))['owned'] or 0
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

    context = {'form': form, 'profile': profile, 'is_own': is_own, 'total_unique_cards': total_unique_cards, 'all_sets': all_sets, 'set_breakdowns': set_breakdowns, 'feed': feed, 'theme': theme}
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

logger = logging.getLogger('tcg_collections.views')

@login_required
def tracker(request, set_id):
    set_obj = get_object_or_404(Set, id=set_id)
    all_sets = Set.objects.all().exclude(tcg_id__contains='P').order_by('tcg_id')
    cards = Card.objects.filter(card_set=set_obj).order_by('tcg_id')

    owned = UserCollection.objects.filter(user=request.user, card__card_set=set_obj).values_list('card__id', 'quantity')
    owned_dict = {cid: qty for cid, qty in owned}
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

        if not errors:
            owned = UserCollection.objects.filter(user=request.user, card__card_set=set_obj).values_list('card__id', 'quantity')
            owned_dict = {cid: qty for cid, qty in owned}
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
                sixth = selected_cards.get('sixth', [])
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

                for card_id in sixth:
                    card = get_object_or_404(Card, id=card_id)
                    cards_selected.append(card)
                    if not card.is_sixth_exclusive or card not in booster.cards.all():
                        errors.append(f"Invalid sixth card {card.name}")
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

    commons = cards.filter(rarity='One Diamond', is_sixth_exclusive=False)
    others = cards.exclude(rarity='One Diamond').filter(is_sixth_exclusive=False)
    sixth = cards.filter(is_sixth_exclusive=True)
    has_sixth_option = sixth.exists()


    common_list = [
        {'id': c.id, 'name': c.name, 'image': c.local_image_small.url, 'rarity': c.rarity, 'tcg_id': c.tcg_id}
        for c in commons    
    ]

    others_list = [
        {'id': c.id, 'name': c.name, 'image': c.local_image_small.url, 'rarity': c.rarity, 'tcg_id': c.tcg_id}
        for c in others    
    ]

    sixth_list = [
        {'id': c.id, 'name': c.name, 'image': c.local_image_small.url, 'rarity': c.rarity, 'tcg_id': c.tcg_id}
        for c in sixth
    ]

    return JsonResponse({
        'commons': common_list,
        'others': others_list,
        'sixth': sixth_list,
        'has_sixth_option': has_sixth_option,
        'booster_image': booster.local_image_small.url if booster.local_image_small else ''
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

    collections = UserCollection.objects.filter(user=request.user).select_related('card', 'card__card_set').order_by('card__card_set__tcg_id', 'card__tcg_id')
    show_unowned = request.GET.get('show_unowned', '0') == '1'
    sorted_sets = get_sorted_sets(collections, show_unowned)

    if request.method == 'POST':
        errors = []
        set_id = None
        for key in request.POST:
            if key.startswith('mark_seen_'):
                item_id_str = key[10:]
                try:
                    item_id = int(item_id_str)
                    collection_item = collections.filter(id=item_id).first()
                    if collection_item:
                        collection_item.is_seen = True
                        collection_item.save()
                        set_id = collection_item.card.card_set.id
                    else:
                        errors.append(f"Item ID {item_id} not found.")
                except ValueError:
                    errors.append(f"Invalid item ID: {item_id_str}")
            elif key.startswith('mark_all_seen_'):
                set_id_str = key[14:]
                try:
                    set_id = int(set_id_str)
                    id_list = request.POST.get(key).split(',') if request.POST.get(key) else []
                    valid_ids = []
                    for id_str in id_list:
                        if id_str.strip():
                            try:
                                valid_ids.append(int(id_str))
                            except ValueError:
                                errors.append(f"Invalid collection ID in list: {id_str}")
                    if valid_ids:
                        updated_count = UserCollection.objects.filter(user=request.user, id__in=valid_ids, card__card_set__id=set_id).update(is_seen=True)
                        if updated_count == 0:
                            errors.append(f"No valid collection items found for set {set_id}")
                except ValueError:
                    errors.append(f"Invalid set ID: {set_id_str}")

        collections = UserCollection.objects.filter(user=request.user).select_related('card', 'card__card_set').order_by('card__card_set__tcg_id', 'card__tcg_id')
        sorted_sets = get_sorted_sets(collections, show_unowned)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            unseen_count = UserCollection.objects.filter(user=request.user, is_seen=False).count()
            if set_id:
                set_has_unseen = collections.filter(card__card_set__id=set_id).filter(is_seen=False).exists()
            status = 'success' if not errors else 'error'
            message = 'Collection updated!' if not errors else 'Errors occured'
            data = {
                'status': status,
                'message': message,
                'unseen_count': unseen_count,
                'has_unseen': set_has_unseen,
                'errors': errors if errors else None
            }
            if set_id:
                data['set_id'] = set_id
            return JsonResponse(data, status=200 if not errors else 400)
        else:
            return redirect('collection')
    
    context = {
        'sorted_sets': sorted_sets,
        'show_unowned': show_unowned
    }
    return render(request, 'collection.html', context)

# Dashboard Views

@login_required
def refresh_pack_picker(request):
    if request.method == 'POST':
        api_view = PackPickerAPI()
        response = api_view.get(request)
        data = json.loads(response.content)
        if 'error' in data:
            request.session['pack_picker_error'] = data['error']
        else:
            request.session.pop('pack_picker_error', None)
        return redirect('dashboard')
    return redirect('dashboard')

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        stats_view = CollectionStatsAPI()
        stats_response = stats_view.get(self.request)
        stats_data = json.loads(stats_response.content)
        context['total_stats'] = stats_data

        owned_breakdown = stats_data['rarity_breakdown']
        total_breakdown = stats_data['total_rarity_breakdown']
        combined_rarities = []
        all_keys = set(owned_breakdown.keys()) | set(total_breakdown.keys())
        for key in sorted(all_keys):
            owned_count = owned_breakdown.get(key, 0)
            total_count = total_breakdown.get(key, 0)
            combined_rarities.append({
                'rarity': key,
                'owned': owned_count,
                'total': total_count,
            })
        groups = ['Diamond', 'Star', 'Shiny', 'Crown']
        grouped_rarities = []
        for group in groups:
            filtered = [item for item in combined_rarities if group in item['rarity']]
            owned_sum = sum(item['owned'] for item in filtered)
            total_sum = sum(item['total'] for item in filtered)
            completion = (owned_sum / total_sum * 100) if total_sum > 0 else 0
            grouped_rarities.append({
                'group': group,
                'owned': owned_sum,
                'total': total_sum,
                'completion': round(completion, 2)
            }) 
        context['total_stats']['grouped_rarities'] = grouped_rarities
        
        set_view = SetBreakdownAPI()
        set_response = set_view.get(self.request)
        set_data = json.loads(set_response.content)
        context['set_breakdown'] = set_data['sets']
        context['all_sets'] = set_data['all_sets']

        set_rarities = {}
        for breakdown in set_data['sets']:
            set_id = breakdown['set_id']
            owned_breakdown = breakdown['rarity_breakdown']
            total_breakdown = breakdown['total_rarity_breakdown']

            combined_rarities = []
            all_keys = set(owned_breakdown.keys()) | set(total_breakdown.keys())
            for key in sorted(all_keys):
                owned_count = owned_breakdown.get(key, 0)
                total_count = total_breakdown.get(key, 0)
                completion = (owned_count / total_count * 100) if total_count > 0 else 0
                combined_rarities.append({
                    'rarity': key,
                    'owned': owned_count,
                    'total': total_count,
                    'completion': round(completion, 2)
                })

            combined_rarities = sorted(combined_rarities, key=lambda item: RARITY_ORDER.index(item['rarity']) if item['rarity'] in RARITY_ORDER else len(RARITY_ORDER))
            set_rarities[set_id] = combined_rarities
        context['set_rarities'] = set_rarities


        try:
            data_model = PackPickerData.objects.get(user=self.request.user)
            boosters = data_model.boosters.all()
            context['pack_picker'] = [b.to_dict() for b in boosters]
            context['last_refresh'] = data_model.last_refresh.isoformat() if data_model.last_refresh else None
        except PackPickerData.DoesNotExist:
            context['pack_picker'] = []
            context['last_refresh'] = timezone.now() - timedelta(hours=1)

        community_stats_view = DailyCommunityStatsAPI()
        community_stats_response = community_stats_view.get(self.request)
        community_stats_data = json.loads(community_stats_response.content)
        context['daily_stats'] = community_stats_data['daily_stats']

        return context

class CollectionStatsAPI(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        collections = UserCollection.objects.filter(user=user, quantity__gt=0).exclude(card__card_set__tcg_id__contains='P')
        all_cards = Card.objects.exclude(card_set__tcg_id__contains='P')

        total_unique = collections.count()
        total_base = collections.filter(card__rarity__in=BASE_RARITIES).count()
        total_rare = collections.filter(card__rarity__in=RARE_RARITIES).count()
        total_quantity = collections.aggregate(total=Sum('quantity'))['total'] or 0

        base_cards_count = all_cards.filter(rarity__in=BASE_RARITIES).count()
        rare_cards_count = all_cards.filter(rarity__in=RARE_RARITIES).count()
        all_cards_count = all_cards.count()

        base_completion = (total_base / base_cards_count * 100) if base_cards_count else 0
        rare_completion = (total_rare / rare_cards_count * 100) if rare_cards_count else 0
        overall_completion = (total_unique / all_cards_count * 100) if all_cards_count else 0

        rarities = collections.values('card__rarity').annotate(count=Count('card__rarity'))
        rarity_breakdown = {r['card__rarity']: r['count'] for r in rarities}
        total_rarities = all_cards.values('rarity').annotate(count=Count('rarity'))
        total_rarity_breakdown = {r['rarity']: r['count'] for r in total_rarities}

        # 6th Slot Exclusives
        exclusive_collections = collections.filter(card__is_sixth_exclusive=True)
        total_exclusive = exclusive_collections.count()
        exclusive_cards_count = all_cards.filter(is_sixth_exclusive=True).count()
        exclusive_completion = (total_exclusive / exclusive_cards_count * 100) if exclusive_cards_count else 0

        # Set Breakdowns
        all_sets = Set.objects.exclude(tcg_id__contains='P').order_by('tcg_id')
        set_breakdown = []
        for s in all_sets:
            set_base = collections.filter(card__card_set=s, card__rarity__in=BASE_RARITIES).count()
            set_rare = collections.filter(card__card_set=s, card__rarity__in=RARE_RARITIES).count()
            set_base_count = all_cards.filter(card_set=s, rarity__in=BASE_RARITIES).count()
            set_rare_count = all_cards.filter(card_set=s, rarity__in=RARE_RARITIES).count()
            set_base_completion = (set_base / set_base_count * 100) if set_base_count else 0
            set_rare_completion = (set_rare / set_rare_count * 100) if set_rare_count else 0
            set_total = set_base + set_rare
            set_total_count = set_base_count + set_rare_count
            set_total_completion = (set_total / set_total_count * 100) if set_total_count else 0

            set_breakdown.append({
                'set_name': s.name,
                'set_id': s.id,
                'set_tcg_id': s.tcg_id,
                'set_base': set_base,
                'set_base_count': set_base_count,
                'set_base_completion': round(set_base_completion, 2),
                'set_rare': set_rare,
                'set_rare_count': set_rare_count,
                'set_rare_completion': round(set_rare_completion, 2),
                'set_total': set_total,
                'set_total_count': set_total_count,
                'set_total_completion': round(set_total_completion, 2)
            })

        return JsonResponse({
            'total_unique': total_unique,
            'total_quantity': total_quantity,
            'total_base': total_base,
            'base_cards_count': base_cards_count,
            'base_completion': round(base_completion, 2),
            'total_rare': total_rare,
            'rare_cards_count':rare_cards_count,
            'rare_completion': round(rare_completion, 2),
            'total_exclusive': total_exclusive,
            'exclusive_cards_count': exclusive_cards_count,
            'exclusive_completion': round(exclusive_completion, 2),
            'overall_completion': round(overall_completion, 2),
            'rarity_breakdown': rarity_breakdown,
            'total_rarity_breakdown': total_rarity_breakdown,
            'set_breakdown': set_breakdown,
        })

class SetBreakdownAPI(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        sets = Set.objects.exclude(tcg_id__contains='P').prefetch_related('cards')
        all_sets = []
        breakdown = []
        for s in sets:
            all_sets.append({'name': s.name, 'id': s.tcg_id})
            set_cards_count = s.cards.count()
            owned_qs = UserCollection.objects.filter(user=user, card__card_set=s, quantity__gt=0)
            owned = owned_qs.count()
            completion = (owned / set_cards_count * 100) if set_cards_count else 0
            
            rarities = owned_qs.values('card__rarity').annotate(count=Count('card__rarity'))
            rarity_breakdown = {r['card__rarity']: r['count'] for r in rarities}
            rarities_total = s.cards.values('rarity').annotate(count=Count('rarity'))
            total_rarity_breakdown = {r['rarity']: r['count'] for r in rarities_total}
            
            breakdown.append({
                'set_name': s.name,
                'set_id': s.tcg_id,
                'owned': owned,
                'total': set_cards_count,
                'completion': round(completion, 2),
                'rarity_breakdown': rarity_breakdown,
                'total_rarity_breakdown': total_rarity_breakdown
            })
        return JsonResponse({'sets': breakdown, 'all_sets': all_sets})

class PackPickerAPI(LoginRequiredMixin, View):
    def get_rarity_dicts(self, cards_qs, user):
        cards_per_rarity = cards_qs.values('rarity').annotate(count=Count('id'))
        cards_dict = {r['rarity']: r['count'] for r in cards_per_rarity}

        owned_ids = UserCollection.objects.filter(user=user, card__in=cards_qs, quantity__gt=0).values_list('card__id', flat=True)
        missing_qs = cards_qs.exclude(id__in=owned_ids)
        missing_per_rarity = missing_qs.values('rarity').annotate(count=Count('id'))
        missing_dict = {r['rarity']: r['count'] for r in missing_per_rarity}

        return cards_dict, missing_dict
    
    def get(self, request):
        user = request.user
        data_model = PackPickerData.objects.get(user=user)

        if data_model.last_refresh and timezone.now() - data_model.last_refresh < timedelta(hours=1):
            print('Refresh limited')
            boosters = data_model.boosters.all()
            if not boosters.exists():
                return JsonResponse({'error': 'No data. Refresh again soon.'}, status=429)
            final_data = {'boosters': [b.to_dict() for b in boosters], 'last_refresh': data_model.last_refresh.isoformat()}
            return JsonResponse(final_data)

        boosters = Booster.objects.all().prefetch_related('cards', 'boosterdroprate_set')
        recommendations = []

        for booster in boosters:
            drop_rates = {}
            for dr in booster.boosterdroprate_set.all():
                if dr.slot not in drop_rates:
                    drop_rates[dr.slot] = {}
                drop_rates[dr.slot][dr.rarity] = dr.probability

            unique_rarities = set()
            for slot_rates in drop_rates.values():
                unique_rarities.update(slot_rates.keys())
            unique_rarities = list(unique_rarities)

            cards_qs = booster.cards.all()
            normal_cards_qs = cards_qs.filter(is_sixth_exclusive=False)
            sixth_cards_qs = cards_qs.filter(is_sixth_exclusive=True)

            normal_cards_dict, normal_missing_dict = self.get_rarity_dicts(normal_cards_qs, user)
            sixth_cards_dict, sixth_missing_dict = self.get_rarity_dicts(sixth_cards_qs, user)

            base_missing_count = sum(normal_missing_dict.get(rarity, 0) + sixth_missing_dict.get(rarity, 0) for rarity in BASE_RARITIES)
            rare_missing_count = sum(normal_missing_dict.get(rarity, 0) + sixth_missing_dict.get(rarity, 0) for rarity in RARE_RARITIES)
            base_total_count = sum(normal_cards_dict.get(rarity, 0) + sixth_cards_dict.get(rarity, 0) for rarity in BASE_RARITIES)
            rare_total_count = sum(normal_cards_dict.get(rarity, 0) + sixth_cards_dict.get(rarity, 0) for rarity in RARE_RARITIES)

            def get_rarity(slot):
                return random.choices(list(drop_rates[slot].keys()), list(drop_rates[slot].values()))[0]
            
            num_sim = 5000
            new_in_pack_counts = []
            has_new_count = 0
            rarity_new_per_sim = []

            for _ in range(num_sim):
                pack_rarities = []
                has_sixth = random.random() < booster.sixth_card_prob

                for _ in range(3):
                    if '1-3' in drop_rates:
                        pack_rarities.append((get_rarity('1-3'), False))
                
                if '4' in drop_rates:
                    pack_rarities.append((get_rarity('4'), False))
                
                if '5' in drop_rates:
                    pack_rarities.append((get_rarity('5'), False))
                
                if has_sixth and '6' in drop_rates:
                    pack_rarities.append((get_rarity('6'), True))
                
                new_in_this_pack = 0
                rarity_new_this_pack = {rarity: 0 for rarity in unique_rarities}

                for rarity, is_sixth in pack_rarities:
                    if is_sixth:
                        total_dict = sixth_cards_dict
                        missing_dict = sixth_missing_dict
                    else:
                        total_dict = normal_cards_dict
                        missing_dict = normal_missing_dict

                    total_in_rarity = total_dict.get(rarity, 0)
                    missing_in_rarity = missing_dict.get(rarity, 0)

                    if total_in_rarity > 0 and random.random() < (missing_in_rarity / total_in_rarity):
                        new_in_this_pack += 1
                        rarity_new_this_pack[rarity] += 1
                
                if new_in_this_pack > 0:
                    has_new_count += 1
                new_in_pack_counts.append(new_in_this_pack)
                rarity_new_per_sim.append(rarity_new_this_pack)

            base_has_new_count = sum(1 for sim_dict in rarity_new_per_sim if any(sim_dict.get(rarity, 0) > 0 for rarity in BASE_RARITIES))
            rare_has_new_count = sum(1 for sim_dict in rarity_new_per_sim if any(sim_dict.get(rarity, 0) > 0 for rarity in RARE_RARITIES))

            base_chance_new = round((base_has_new_count / num_sim) * 100, 2) if num_sim > 0 else 0.0
            rare_chance_new = round((rare_has_new_count / num_sim) * 100, 2) if num_sim > 0 else 0.0
            
            total_cards_dict, total_missing_dict = self.get_rarity_dicts(cards_qs, user)
            chance_new = (has_new_count / num_sim) * 100
            expected_new = sum(new_in_pack_counts) / num_sim

            rarity_chances = {}
            for rarity in unique_rarities:
                has_new_rarity_count = sum(1 for sim_dict in rarity_new_per_sim if sim_dict[rarity] > 0)
                total_new_rarity = sum(sim_dict[rarity] for sim_dict in rarity_new_per_sim)
                rarity_chances[rarity] = {
                    'chance_new': round((has_new_rarity_count / num_sim) * 100, 2),
                    'expected_new': round(total_new_rarity / num_sim, 2),
                    'missing_count': total_missing_dict.get(rarity, 0),
                    'total_count': total_cards_dict.get(rarity, 0)
                }
            
            recommendations.append({
                'booster_name': booster.name,
                'booster_id': booster.tcg_id,
                'booster_set_id': booster.sets.first().tcg_id,
                'chance_new': round(chance_new, 2),
                'expected_new': round(expected_new, 2),
                'missing_count': sum(total_missing_dict.values()),
                'total_count': sum(total_cards_dict.values()),
                'base_missing_count': base_missing_count,
                'base_total_count': base_total_count,
                'base_chance_new': base_chance_new,
                'rare_missing_count': rare_missing_count,
                'rare_total_count': rare_total_count,
                'rare_chance_new': rare_chance_new,
                'rarity_chances': rarity_chances,
            })
        
        recommendations.sort(key=lambda x: x['chance_new'], reverse=True)

        data_model.last_refresh = timezone.now()
        data_model.save()
        for rec in recommendations:
            booster_model = PackPickerBooster.objects.update_or_create(
                data=data_model,
                booster=Booster.objects.get(tcg_id=rec['booster_id']),
                defaults = {
                    'chance_new': rec['chance_new'],
                    'expected_new': rec['expected_new'],
                    'missing_count': rec['missing_count'],
                    'total_count': rec['total_count'],
                    'base_missing_count': rec['base_missing_count'],
                    'base_total_count': rec['base_total_count'],
                    'base_chance_new': rec['base_chance_new'],
                    'rare_missing_count': rec['rare_missing_count'],
                    'rare_total_count': rec['rare_total_count'],
                    'rare_chance_new': rec['rare_chance_new'],
                }
            )[0]

            for rarity, chances in rec['rarity_chances'].items():
                PackPickerRarity.objects.update_or_create(
                    booster=booster_model,
                    rarity=rarity,
                    defaults= {
                        'chance_new': chances['chance_new'],
                        'expected_new': chances['expected_new'],
                        'missing_count': chances['missing_count'],
                        'total_count': chances['total_count']
                    }
                )
        
        print('Refresh run and saved')

        final_data = {'boosters': recommendations, 'last_refresh': data_model.last_refresh.isoformat()}
        return JsonResponse(final_data)

class ActivityFeedAPI(LoginRequiredMixin, View):
    def get(self, request):
        activities = Activity.objects.filter(user=request.user).order_by('-timestamp')[:10]
        feed = [
            {
                'type': a.type,
                'content': a.content,
                'timestamp': a.timestamp.isoformat()
            }
            for a in activities
        ]
        return JsonResponse({'feed': feed})
    
class GrowthTrendAPI(LoginRequiredMixin, View):
    def get(self, request):
        data = Activity.objects.filter(user=request.user, type='collection_add') \
            .annotate(week=TruncWeek('timestamp')) \
            .values('week') \
            .annotate(adds=Count('id')) \
            .order_by('week')
        
        trend = [
            {
                'week': d['week'].isoformat() if d['week'] else None,
                'adds': d['adds']
            }
            for d in data
        ]
        return JsonResponse({'trend': trend})
    
class RarityDistributionAPI(LoginRequiredMixin, View):
    def get(self, request):
        set_id = request.GET.get('set_id')
        qs = UserCollection.objects.filter(user=request.user, quantity__gt=0)

        if set_id:
            qs = qs.filter(card__card_set__tcg_id=set_id)
        
        rarities = qs.values('card__rarity').annotate(count=Count('card__rarity'))
        distribution = {r['card__rarity']: r['count'] for r in rarities}

        return JsonResponse({'distribution': distribution})

class DailyCommunityStatsAPI(LoginRequiredMixin, View):
    def get(self, request):
        today = timezone.now().date()
        stats_obj, _ = DailyStat.objects.get_or_create(date=today)

        stats = {
            'packs_opened': stats_obj.packs_opened,
            'rare_cards_found': stats_obj.rare_cards_found,
            'four_diamond_found': stats_obj.four_diamond_found,
            'one_star_found': stats_obj.one_star_found,
            'two_star_found': stats_obj.two_star_found,
            'three_star_found': stats_obj.three_star_found,
            'one_shiny_found': stats_obj.one_shiny_found,
            'two_shiny_found': stats_obj.two_shiny_found,
            'crown_found': stats_obj.crown_found,
        }

        return JsonResponse({'daily_stats': stats})