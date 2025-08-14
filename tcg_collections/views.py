from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.http import JsonResponse
import json
from .models import UserCollection, Set, UserWant, Card, Message, Booster, BoosterDropRate
from tcg_collections.forms import CustomUserCreationForm, ProfileForm, MessageForm, PackOpenerForm

# Create your views here.
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
def profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'profile.html', {'form': form})

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
def tracker_set(request, set_id):
    set_obj = get_object_or_404(Set, id=set_id)
    all_sets = Set.objects.all().order_by('tcg_id')
    cards = Card.objects.filter(card_set=set_obj).order_by('tcg_id')

    owned = UserCollection.objects.filter(user=request.user, card__card_set=set_obj).values_list('card__id', 'quantity', 'for_trade')
    owned_dict = {cid: (qty, for_trade) for cid, qty, for_trade in owned}
    wants = UserWant.objects.filter(user=request.user, card__card_set=set_obj).values_list('card__id', flat=True)

    errors = []

    if request.method == 'POST':
        processed_cards = set()
        for key in request.POST:
            if key.startswith('quantity_'):
                card_id_str = key[9:]
                processed_cards.add(card_id_str)
            elif key.startswith('for_trade_'):
                card_id_str = key[10:]
                processed_cards.add(card_id_str)
            
            for card_id_str in processed_cards:
                try:
                    card_id = int(card_id_str)
                    print(f"Processing card_id: {card_id} for set: {set_obj.id}")
                    card= get_object_or_404(Card, id=card_id)
                except ValueError:
                    errors.append(f"Invalid card ID '{card_id_str}")
                    print(f"Invalid card_id_str: {card_id_str}")
                    continue

                obj = UserCollection.objects.filter(user=request.user, card=card).first()
                changed = False
                qty_str = request.POST.get(f"quantity_{card_id}", None)
                if qty_str is not None:
                    try:
                        qty = int(qty_str)
                        if qty < 0:
                            errors.append(f"Quantity for card '{card_id}' cannot be negative.")
                            continue
                    except ValueError:
                        errors.append(f"Invalid quantity for card '{card.name}'.")
                
                    if obj is None:
                        if qty > 0:
                            obj = UserCollection(user=request.user, card=card, quantity=qty, for_trade=False)
                            changed = True
                    else:
                        obj.quantity = qty
                        changed = True
                
                for_trade_str = request.POST.get(f"for_trade_{card_id}", None)
                if for_trade_str is not None:
                    for_trade = for_trade_str == 'true'
                    if for_trade and not card.is_tradeable:
                        errors.append(f'Card "{card.name}" is not tradeable.')
                        continue

                    if obj is None:
                        continue
                    else:
                        obj.for_trade = for_trade
                        changed = True

                if obj and changed:
                    if obj.quantity == 0:
                        obj.delete()
                    else:
                        obj.save()

            if key.startswith('want_toggle_'):
                print("Processing wishlist toggle...")
                card_id_str = key[12:]
                try:
                    card_id = int(card_id_str)
                    card = get_object_or_404(Card, id=card_id)
                    want_obj = UserWant.objects.filter(user=request.user, card=card).first()
                    print(want_obj)
                    if want_obj:
                        want_obj.delete()
                    else:
                        UserWant.objects.create(user=request.user, card=card, desired_quantity=1)
                except ValueError:
                    errors.append(f"Invalid card ID for wishlist: '{card_id_str}'")
                    continue

        if not errors:
            owned = UserCollection.objects.filter(user=request.user, card__card_set=set_obj).values_list('card__id', 'quantity', 'for_trade')
            owned_dict = {cid: (qty, for_trade) for cid, qty, for_trade in owned}
            wants = UserWant.objects.filter(user=request.user, card__card_set=set_obj).values_list('card__id', flat=True)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':  # Detect AJAX
                return JsonResponse({'status': 'success', 'message': 'Changes saved!'})
            else:
                return redirect('collection_set', set_id=set_id)  # Fallback for non-AJAX
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
    return render(request, 'tracker_set.html', context)

@login_required
def trade_matches(request):

    def get_user_wants(user):
        user_wants = UserWant.objects.filter(user=user, desired_quantity__gt=0).select_related('card')
        user_wants_by_rarity = defaultdict(set)
        for want in user_wants:
            user_wants_by_rarity[want.card.rarity].add(want.card.id)
        return user_wants_by_rarity

    def get_user_haves(user):
        user_haves = UserCollection.objects.filter(user=user, quantity__gte=2, for_trade=True, card__is_tradeable=True).select_related('card')
        user_haves_by_rarity = defaultdict(set)
        for have in user_haves:
            user_haves_by_rarity[have.card.rarity].add(have.card.id)
        return user_haves_by_rarity

    # User wants/haves
    my_wants_by_rarity = get_user_wants(request.user)
    my_haves_by_rarity = get_user_haves(request.user)

    # Check if no wants/haves
    if not any(my_wants_by_rarity.values()) or not any(my_haves_by_rarity.values()):
        context = {'matches': [], 'message': 'Add some wants and mark tradeable haves to find matches.'}
        return render(request, 'trade_matches.html', context)

    # Get other user wants/haves
    other_users = User.objects.exclude(id=request.user.id)
    matches = []
    for user in other_users:
        user_wants_by_rarity = get_user_wants(user)
        user_haves_by_rarity = get_user_haves(user)

        # Matches
        rarity_matches = {}
        for rarity in set(my_wants_by_rarity.keys()) & set(user_haves_by_rarity.keys()):
            they_offer_me_ids = my_wants_by_rarity[rarity].intersection(user_haves_by_rarity[rarity])
            if they_offer_me_ids:
                they_offer_cards = Card.objects.filter(id__in=they_offer_me_ids)
                rarity_matches.setdefault(rarity, {'they_offer': they_offer_cards, 'i_offer': []})
        
        for rarity in set(my_haves_by_rarity.keys()) & set(user_wants_by_rarity.keys()):
            i_offer_them_ids = my_haves_by_rarity[rarity].intersection(user_wants_by_rarity[rarity])
            if i_offer_them_ids:
                i_offer_cards = Card.objects.filter(id__in=i_offer_them_ids)
                if rarity in rarity_matches:
                    rarity_matches[rarity]['i_offer'] = i_offer_cards
                else:
                    rarity_matches[rarity] = {'they_offer': [], 'i_offer': i_offer_cards}
        
        valid_rarity_matches = {r: data for r, data in rarity_matches.items() if data['they_offer'] and data['i_offer']}
        if valid_rarity_matches:
            matches.append({
                'username': user.username,
                'user_id': user.id,
                'rarity_matches': valid_rarity_matches,
            })
    
    context = {'matches': matches}
    return render(request, 'trade_matches.html', context)

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
def inbox(request):
    received = Message.objects.filter(receiver=request.user).order_by('-timestamp')
    sent = Message.objects.filter(sender=request.user).order_by('-timestamp')
    context = {'received': received, 'sent': sent}
    return render(request, 'inbox.html', context)

@login_required
def pack_opener(request):
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

                for card_id in commons:
                    card = get_object_or_404(Card, id=card_id)
                    if card not in booster.cards.all() or card.rarity != 'One Diamond':
                        errors.append(f"Invalid common card {card.name}")
                    else:
                        obj, created = UserCollection.objects.get_or_create(user=request.user, card=card, defaults={'quantity': 1, 'for_trade': False, 'is_seen': False})
                        if not created:
                            obj.quantity += 1
                            obj.save()

                for card_id in others:
                    card = get_object_or_404(Card, id=card_id)
                    if card not in booster.cards.all() or card.rarity == 'One Diamond':
                        errors.append(f"Invalid other card {card.name}")
                    else:
                        obj, created = UserCollection.objects.get_or_create(user=request.user, card=card, defaults={'quantity': 1, 'for_trade': False, 'is_seen': False})
                        if not created:
                            obj.quantity += 1
                            obj.save()

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

    print(others_list)
    return JsonResponse({
        'commons': common_list,
        'others': others_list,
        'booster_image': booster.local_image_small if booster.local_image_small else ''
    })

@login_required
def wishlist(request):
    def get_sorted_wants():
        wants = UserWant.objects.filter(user=request.user).select_related('card', 'card__card_set').order_by('card__card_set__tcg_id', 'card__tcg_id')
        wants_by_set = defaultdict(list)
        for want in wants:
            wants_by_set[want.card.card_set].append(want)
        return sorted(wants_by_set.items(), key=lambda x: x[0].tcg_id)
    
    errors = []
    sorted_sets = get_sorted_wants()

    if request.method == 'POST':
        for key in request.POST:
            print("Key: ", key)
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