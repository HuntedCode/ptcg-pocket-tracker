from collections import Counter
from datetime import date, datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction
from django.contrib.auth.models import User, AbstractUser
from django.db.models.deletion import SET_NULL
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import json
import uuid
import logging
from .utils import ICON_CHOICES, COLOR_CHOICES, TRACKED_RARITIES
from storages.backends.s3boto3 import S3Boto3Storage

# Create your models here.

# User Model
class User(AbstractUser):
    email = models.EmailField(unique=True, null=False, blank=False)

# Card/Collection Models

class Booster(models.Model):
    tcg_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    local_image_small = models.ImageField(upload_to='media/boosters/', storage=S3Boto3Storage, blank=True, null=True)
    god_pack_prob = models.FloatField(default=0.0005, help_text='Base probability of god pack (e.g., 0.0005)')
    sixth_card_prob = models.FloatField(default=0.0, help_text="Base probability of 6th card (e.g., 0.05)")

    def __str__(self):
        return self.name

class BoosterDropRate(models.Model):
    booster = models.ForeignKey(Booster, on_delete=models.CASCADE)
    slot = models.CharField(max_length=50, choices=[
        ('1-3', 'Slots 1-3 (Always One Diamond)'),
        ('4', 'Slot 4 (Non-One Diamond, Weighted Low)'),
        ('5', 'Slot 5 (Non-One Diamond, Better Odds)'),
        ('god', 'God Pack (All One-Star+, Rare)'),
        ('6', '6th Card (5% Chance, Exclusives)')
    ])
    rarity = models.CharField(max_length=50)
    probability = models.FloatField(help_text='Probability (0.0 to 1.0)')

    class Meta:
        unique_together = ('booster', 'slot', 'rarity')

    def __str__(self):
        return f"{self.booster.name} - {self.slot}: {self.rarity} ({self.probability * 100}%)"

class Set(models.Model):
    tcg_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    release_date = models.DateField(null=True, blank=True)
    card_count_official = models.PositiveIntegerField(null=True, blank=True)
    card_count_total = models.PositiveIntegerField(null=True, blank=True)
    logo = models.ImageField(upload_to='media/set_logos/', storage=S3Boto3Storage(), blank=True, null=True)
    symbol = models.URLField(blank=True)
    boosters = models.ManyToManyField(Booster, related_name='sets', blank=True)

    def __str__(self):
        return self.name

class Card(models.Model):
    category = models.CharField(max_length=50)
    tcg_id = models.CharField(max_length=50, unique=True)
    illustrator = models.CharField(max_length=100, blank=True)
    image_base = models.CharField(max_length=200, blank=True)
    local_image_small = models.ImageField(upload_to='media/cards/', storage=S3Boto3Storage(), blank=True, null=True)
    name = models.CharField(max_length=100)
    rarity = models.CharField(max_length=50)
    card_set = models.ForeignKey(Set, on_delete=models.CASCADE, related_name='cards')
    boosters = models.ManyToManyField(Booster, related_name='cards', blank=True)
    manual_boosters_added = models.BooleanField(default=False, help_text="Set to True if boosters were manually assigned")
    is_sixth_exclusive = models.BooleanField(default=False, help_text="True if this card is exclusive to the 6th slot in packs")
    is_tradeable = models.BooleanField(default=False)

    # Pokemon Specific
    type = models.CharField(max_length=50, blank=True)
    stage = models.CharField(max_length=50, blank=True)
    hp = models.PositiveIntegerField(null=True, blank=True)
    suffix = models.CharField(max_length=50, blank=True)

    # Trainer Specific
    trainer_type = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.name} ({self.tcg_id})"
    
class UserCollection(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    is_seen = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'card')
        indexes = [
            models.Index(fields=['user', 'quantity']),
            models.Index(fields=['user', 'card'])
        ]
    
    def __str__(self):
        return f"{self.user.username}'s {self.card.name} (x{self.quantity})"

class UserWant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    desired_quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('user', 'card')

    def __str__(self):
        return f"{self.user.username} wants {self.card.name} (x{self.desired_quantity})"

class Activity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activities')
    type = models.CharField(max_length=50, choices=[
        ('collection_add', 'Collection Add'),
        ('pack_open', 'Pack Open')
    ])
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp'])
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.type} at {self.timestamp}"

class PackPickerData(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    last_refresh = models.DateTimeField(default=date(2025, 1, 1), help_text="Timestamp of last sim run")
    refresh_count = models.PositiveIntegerField(default=1, help_text="Count for current period (e.g., reset daily/hourly)")

    def __str__(self):
        return f"{self.user.username}'s Pack Picker Data"

class PackPickerBooster(models.Model):
    data = models.ForeignKey(PackPickerData, on_delete=models.CASCADE, related_name='boosters')
    booster = models.ForeignKey(Booster, on_delete=models.CASCADE)
    chance_new = models.FloatField(default=0.0)
    expected_new = models.FloatField(default=0.0)
    missing_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    base_missing_count = models.PositiveIntegerField(default=0)
    base_total_count = models.PositiveIntegerField(default=0)
    base_chance_new = models.FloatField(default=0.0)
    rare_missing_count = models.PositiveIntegerField(default=0)
    rare_total_count = models.PositiveIntegerField(default=0)
    rare_chance_new = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('data', 'booster')
        ordering = ['-chance_new']
        indexes = [
            models.Index(fields=['data', 'chance_new'])
        ]
    
    def to_dict(self):
        rarity_chances = {r.rarity: r.to_dict() for r in self.rarities.all()}
        return {
            'booster_name': self.booster.name,
            'booster_id': self.booster.tcg_id,
            'chance_new': self.chance_new,
            'expected_new': self.expected_new,
            'missing_count': self.missing_count,
            'total_count': self.total_count,
            'base_missing_count': self.base_missing_count,
            'base_total_count': self.base_total_count,
            'base_chance_new': self.base_chance_new,
            'rare_missing_count': self.rare_missing_count,
            'rare_total_count': self.rare_total_count,
            'rare_chance_new': self.rare_chance_new,
            'rarity_chances': rarity_chances
        }

    def __str__(self):
        return f"{self.booster.name} for {self.data.user.username}"

class PackPickerRarity(models.Model):
    booster = models.ForeignKey(PackPickerBooster, on_delete=models.CASCADE, related_name='rarities')
    rarity = models.CharField(max_length=50)
    chance_new = models.FloatField(default=0.0)
    expected_new = models.FloatField(default=0.0)
    missing_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('booster', 'rarity')
        indexes = [
            models.Index(fields=['booster', 'rarity'])
        ]

    def to_dict(self):
        return {
            'chance_new': self.chance_new,
            'expected_new': self.expected_new,
            'missing_count': self.missing_count,
            'total_count': self.total_count
        }

    def __str__(self):
        return f"{self.rarity} for {self.booster.booster.name}"

# Profile/Social Models

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    share_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True)
    pic_config = models.JSONField(default=dict)
    is_trading_active = models.BooleanField(default=False, help_text="Enable to appear in matches and receive messages.")
    trade_threshold = models.PositiveSmallIntegerField(default=2, choices=[(1, 'Trade down to 1'), (2, 'Keep 2 for decks')])
    bio = models.TextField(blank=True, help_text="Share trading preferences (e.g., 'Only A1 sets').")
    theme = models.CharField(max_length=20, default='default')
    dark_mode = models.BooleanField(default=False, help_text="Enable dark mode theme")
    last_active = models.DateTimeField(auto_now=True)
    is_premium = models.BooleanField(default=False, help_text="Premium subscriber status.")
    accepted_trades_this_month = models.PositiveIntegerField(default=0, help_text="Count of accepted trades in current month.")
    last_trade_month = models.DateField(null=True, blank=True, help_text="Last month trades were reset.")

    def __str__(self):
        return f"{self.user.username}'s profile"

class Match(models.Model):
    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='initiated_matches', on_delete=models.CASCADE)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_matches', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('ignored', 'Ignored')
    ], default='pending')
    offered_card = models.ForeignKey(Card, related_name='offered_in_matches', on_delete=SET_NULL, null=True)
    received_card = models.ForeignKey(Card, related_name='received_in_matches', on_delete=SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('initiator', 'recipient')
    
    def __str__(self):
        return f"{self.initiator.username} -> {self.recipient.username}: {self.status}"

class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"From {self.sender} to {self.receiver} at {self.timestamp}"

# Aggregate Stats Model

class DailyStat(models.Model):
    date = models.DateField(default=timezone.now, unique=True)
    packs_opened = models.PositiveIntegerField(default=0)
    rare_cards_found = models.PositiveIntegerField(default=0)
    new_users = models.PositiveIntegerField(default=0)

    four_diamond_found = models.PositiveIntegerField(default=0)
    one_star_found = models.PositiveIntegerField(default=0)
    two_star_found = models.PositiveIntegerField(default=0)
    three_star_found = models.PositiveIntegerField(default=0)
    one_shiny_found = models.PositiveIntegerField(default=0)
    two_shiny_found = models.PositiveIntegerField(default=0)
    crown_found = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Stats for {self.date}"
    
# Receivers

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        import random
        pic_config = {
            'icon': ICON_CHOICES[random.randint(0, len(ICON_CHOICES)-1)][0],
            'bg_color': COLOR_CHOICES[random.randint(0, len(COLOR_CHOICES)-1)][0]
        }
        Profile.objects.create(user=instance, pic_config=pic_config)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()

@receiver(post_save, sender=UserCollection)
def log_new_collection_add(sender, instance, created, **kwargs):
    TRACKED_RARITIES = ['Four Diamond', 'One Star', 'Two Star', 'Three Star', 'One Shiny', 'Two Shiny', 'Crown']
    if created and instance.quantity > 0 and instance.card.rarity in TRACKED_RARITIES:
        content = json.dumps({'message': f"({instance.card.tcg_id}) {instance.card.name} - {instance.card.rarity}", 'card_id': instance.card.id})
        Activity.objects.create(user=instance.user, type='collection_add', content=content)

logger = logging.getLogger(__name__)
@receiver(post_save, sender=UserCollection)
def log_collection_stats(sender, instance, **kwargs):
    count = sender.objects.filter(user=instance.user).count()
    logger.info(f"User {instance.user.username} collection size: {count}")

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_pack_picker(sender, instance, created, **kwargs):
    if created:
        PackPickerData.objects.create(user=instance)

# Cache Receivers

@receiver(post_save, sender=UserCollection)
def invalidate_user_cache(sender, instance, **kwargs):
    user_id = instance.user.id
    cache.delete_many([
        f"user:{user_id}:stats",
        f"user:{user_id}:breakdown"
    ])

# Stats Receivers

@transaction.atomic
@receiver(post_save, sender=Activity)
def update_stats_on_activity(sender, instance, created, **kwargs):
    if created and instance.type == 'pack_open':
        today = timezone.now().date()
        stats, _ = DailyStat.objects.get_or_create(date=today)

        card_details = json.loads(instance.content)['details']
        rarity_found = []
        for detail in card_details:
            card = Card.objects.filter(id=detail[0]).first()
            if card and card.rarity in TRACKED_RARITIES:
                rarity_str = card.rarity.lower().replace(" ", "_") + '_found'
                rarity_found.append(rarity_str)

        counter = Counter(rarity_found)

        changed_fields = ['packs_opened']
        stats.packs_opened = models.F('packs_opened') + 1
        if len(rarity_found) > 0:
            stats.rare_cards_found = models.F('rare_cards_found') + len(rarity_found)
            changed_fields.append('rare_cards_found')

        for rarity_str, count in counter.items():
            setattr(stats, rarity_str, models.F(rarity_str) + count)
            changed_fields.append(rarity_str)

        stats.save(update_fields=changed_fields)

@transaction.atomic
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def update_stats_on_new_user(sender, instance, created, **kwargs):
    if created:
        today = timezone.now().date()
        stats, _ = DailyStat.objects.get_or_create(date=today)
        stats.new_users = models.F('new_users') + 1
        stats.save(update_fields=['new_users'])