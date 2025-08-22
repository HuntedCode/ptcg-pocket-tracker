from django.contrib import admin
from .models import Booster, Card, Set, UserCollection, UserWant, Profile, Message, BoosterDropRate, Activity, Match

# Register your models here.
# Card/Collection Models

@admin.register(Booster)
class BoosterAdmin(admin.ModelAdmin):
    list_display = ('name', 'tcg_id')
    search_fields = ('name',)

@admin.register(BoosterDropRate)
class BoosterDropRateAdmin(admin.ModelAdmin):
    list_display = ('booster', 'slot', 'rarity', 'probability')
    search_fields = ('booster',)
    list_filter = ('booster__name', 'slot', 'rarity')

@admin.register(Set)
class SetAdmin(admin.ModelAdmin):
    list_display = ('name', 'tcg_id', 'card_count_official', 'card_count_total')
    search_fields = ('name', 'tcg_id')

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('name', 'tcg_id', 'type', 'rarity', 'category')
    search_fields = ('name', 'tcg_id')
    list_filter = ('rarity', 'type', 'card_set', 'boosters')

@admin.register(UserCollection)
class UserCollectionAdmin(admin.ModelAdmin):
    list_display = ('user', 'card', 'quantity', 'for_trade')
    search_fields = ('user__username', 'card__name', 'card__tcg_id')

@admin.register(UserWant)
class UserWantsAdmin(admin.ModelAdmin):
    list_display = ('user', 'card', 'desired_quantity')
    search_fields = ('user__username', 'card__name', 'card__tcg_id')

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'content', 'timestamp')
    search_fields = ('user',)
    list_filter = ('type',)

# Profile/Social Models

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'pic_config', 'is_trading_active', 'bio', 'share_token', 'theme')
    search_fields = ('user__username',)
    list_filter = ('is_trading_active',)

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('initiator', 'recipient', 'status', 'created_at', 'updated_at')
    search_fields = ('initiator__username', 'recipient__username')
    list_filter = ('status',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'content', 'timestamp', 'is_read')
    search_fields = ('sender__username', 'receiver__username', 'content')