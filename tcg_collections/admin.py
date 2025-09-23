from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Booster, Card, Set, UserCollection, UserWant, Profile, Message, BoosterDropRate, Activity, Match, PackPickerData, PackPickerBooster, PackPickerRarity, DailyStat, User

# Register your models here.
# Card/Collection Models

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)

    fieldsets = UserAdmin.fieldsets

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
    list_display = ('user', 'card', 'quantity')
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
    list_display = ('user', 'last_active', 'pic_config', 'is_trading_active', 'bio', 'share_token', 'theme')
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

@admin.register(PackPickerData)
class PackPickerDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_refresh', 'refresh_count')
    search_fields = ('user',)

@admin.register(PackPickerBooster)
class PackPickerBoosterAdmin(admin.ModelAdmin):
    list_display = ('data', 'booster', 'chance_new', 'expected_new', 'missing_count', 'total_count')
    search_fields = ('booster',)
    list_filter = ('booster',)

@admin.register(PackPickerRarity)
class PackPickerRarityAdmin(admin.ModelAdmin):
    list_display = ('booster', 'rarity', 'chance_new', 'expected_new', 'missing_count', 'total_count')
    search_fields = ('booster', 'rarity')
    list_filter = ('booster', 'rarity')

# Daily Stats Model

@admin.register(DailyStat)
class DailyStatAdmin(admin.ModelAdmin):
    list_display = ('date', 'packs_opened', 'rare_cards_found', 'new_users', 'four_diamond_found', 'one_star_found', 'two_star_found', 'three_star_found', 'one_shiny_found', 'two_shiny_found', 'crown_found')
    search_fields = ('date',)