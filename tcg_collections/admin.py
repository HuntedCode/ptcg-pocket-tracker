from django.contrib import admin
from .models import Booster, Card, Set, UserCollection

# Register your models here.
@admin.register(Booster)
class BoosterAdmin(admin.ModelAdmin):
    list_display = ('name', 'tcg_id')
    search_fields = ('name',)

@admin.register(Set)
class SetAdmin(admin.ModelAdmin):
    list_display = ('name', 'tcg_id', 'card_count_official', 'card_count_total')
    search_fields = ('name', 'tcg_id')

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('name', 'tcg_id', 'rarity', 'category')
    search_fields = ('name', 'tcg_id')
    list_filter = ('rarity', 'category', 'card_set')

@admin.register(UserCollection)
class UserCollectionAdmin(admin.ModelAdmin):
    list_display = ('user', 'card', 'quantity', 'for_trade')
    search_fields = ('user__username', 'card__name')