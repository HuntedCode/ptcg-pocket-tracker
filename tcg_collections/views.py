from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from .models import UserCollection, Set, UserWant, Card
from tcg_collections.forms import CustomUserCreationForm, CollectionForm, WantForm, ProfileForm

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
    
    context = {
        'collections': collections,
        'wants': wants,
        'total_cards': total_cards,
        'sets_summary': sets_summary,
    }
    return render(request, 'dashboard.html', context)

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
                'user': user.username,
                'rarity_matches': valid_rarity_matches,
            })
    
    context = {'matches': matches}
    return render(request, 'trade_matches.html', context)