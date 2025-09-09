import random
from .models import UserCollection, Set

def random_navbar_icon(request):
    icons = [
        'images/navbar_icons/poke_icon1.png',
        'images/navbar_icons/poke_icon2.png',
        'images/navbar_icons/poke_icon3.png',
        'images/navbar_icons/poke_icon4.png',
        'images/navbar_icons/poke_icon5.png',
        'images/navbar_icons/poke_icon6.png',
        'images/navbar_icons/poke_icon7.png',
        'images/navbar_icons/poke_icon8.png',
        'images/navbar_icons/poke_icon9.png',
        'images/navbar_icons/poke_icon10.png',
        'images/navbar_icons/poke_icon11.png',
        'images/navbar_icons/poke_icon12.png',
        'images/navbar_icons/poke_icon13.png',
        'images/navbar_icons/poke_icon14.png',
        'images/navbar_icons/poke_icon15.png',
        'images/navbar_icons/poke_icon16.png',
        'images/navbar_icons/poke_icon17.png',
        'images/navbar_icons/poke_icon18.png',
        'images/navbar_icons/poke_icon19.png',
        'images/navbar_icons/poke_icon20.png',
    ]
    random_icon = random.choice(icons)
    return {'random_icon': random_icon}

def unseen_count_processor(request):
    if request.user.is_authenticated:
        return {'unseen_count': UserCollection.objects.filter(user=request.user, is_seen=False).count()}
    return {'unseen_count': 0}

def latest_set_id(request):
    return {'latest_set_id': Set.objects.latest('id').id}