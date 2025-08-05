from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from .models import UserCollection, Set
from django.db.models import Sum, Count
from tcg_collections.forms import CustomUserCreationForm

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