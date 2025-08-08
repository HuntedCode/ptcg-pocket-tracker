from collections import defaultdict
import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.http import HttpResponse
from django.views.generic import ListView
from django.forms import modelformset_factory
from io import StringIO
from .models import UserCollection, Set, UserWant, Card, Message, Booster, BoosterDropRate
from tcg_collections.forms import CustomUserCreationForm, CollectionForm, WantForm, ProfileForm, MessageForm, PackOpenerForm, CollectionItemForm

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
def update_profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'profile_form.html', {'form': form})

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
def collection(request):
    cards = Card.objects.all().order_by('card_set__tcg_id', 'tcg_id')
    sets = Set.objects.all().order_by('tcg_id')

    cards_by_set = defaultdict(list)
    for card in cards:
        cards_by_set[card.card_set.name].append(card)
    
    owned = UserCollection.objects.filter(user=request.user).values_list('card__id', 'quantity', 'for_trade')
    owned_dict = {cid: (qty, for_trade) for cid, qty, for_trade in owned}
    wants = UserWant.objects.filter(user=request.user).values_list('card__id', flat=True)

    CollectionFormSet = modelformset_factory(UserCollection, form=CollectionItemForm, extra=0)
    if request.method == 'POST':
        formset = CollectionFormSet(request.POST, queryset=UserCollection.objects.filter(user=request.user))
        if formset.is_valid():
            formset.save()
            return redirect('collection')
    else:
        formset = CollectionFormSet(queryset=UserCollection.objects.filter(user=request.user))    

    context = {'sets': sets, 'cards_by_set': dict(cards_by_set), 'owned_dict': owned_dict, 'wants': set(wants), 'formset': formset}
    return render(request, 'collection.html', context)

@login_required
def add_collection(request):
    if request.method == "POST":
        form = CollectionForm(request.POST)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.user = request.user
            collection.save()
            return redirect('dashboard')
    else:
        form = CollectionForm()
    return render(request, 'collection_form.html', {'form': form, 'action': 'Add'})

@login_required
def edit_collection(request, pk):
    collection = get_object_or_404(UserCollection, pk=pk, user=request.user)
    if request.method == "POST":
        form = CollectionForm(request.POST, instance=collection)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = CollectionForm(instance=collection)
    return render(request, 'collection_form.html', {'form': form, 'action': 'Edit'})

@login_required
def add_want(request):
    if request.method == 'POST':
        form = WantForm(request.POST)
        if form.is_valid():
            want = form.save(commit=False)
            want.user = request.user
            want.save()
            return redirect('dashboard')
    else:
        form = WantForm()
    return render(request, 'collection_form.html', {'form': form, 'action': 'Add Want'})

@login_required
def edit_want(request, pk):
    want = get_object_or_404(UserWant, pk=pk, user=request.user)
    if request.method == "POST":
        form = WantForm(request.POST, instance=want)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = WantForm(instance=want)
    return render(request, 'collection_form.html', {'form': form, 'action': 'Edit Want'})

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
        form = PackOpenerForm(request.POST)
        if form.is_valid():
            for i in range(1, 7):
                card = form.cleaned_data.get(f'card{i}')
                if card:
                    obj, created = UserCollection.objects.get_or_create(
                        user=request.user,
                        card=card,
                        defaults={'quantity': 1, 'for_trade': False}
                    )
                    if not created:
                        obj.quantity += 1
                        obj.save()
            return redirect('dashboard')
    else:
        form = PackOpenerForm()
    return render(request, 'pack_opener.html', {'form': form})

@login_required
def export_collections(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="my_collections.csv"'
    writer = csv.writer(response)
    writer.writerow(['Card ID', 'Name', 'Set Name', 'Quantity', 'For Trade'])
    for item in UserCollection.objects.filter(user=request.user).select_related('card'):
        writer.writerow([item.card.tcg_id, item.card.name, item.card.card_set.name, item.quantity, item.for_trade])
    return response

@login_required
def import_collections(request):
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if csv_file:
            file_data = csv_file.read().decode('utf-8')
            csv_data = csv.reader(StringIO(file_data))
            next(csv_data) #skips header
            for row in csv_data:
                tcg_id, quantity, for_trade = row[0], int(row[3]), bool(row[4])
                card = Card.objects.filter(tcg_id=tcg_id).first()
                if card:
                    UserCollection.objects.update_or_create(
                        user=request.user,
                        card=card,
                        defaults={'quantity': quantity, 'for_trade': for_trade}
                    )
                else:
                    pass
            return redirect('dashboard')
    return render(request, 'import_csv.html')