from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from .models import UserCollection, Set
from tcg_collections.forms import CustomUserCreationForm, CollectionForm

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
def dashboard(request):
    collections = UserCollection.objects.filter(user=request.user).select_related('card', 'card__card_set')
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
