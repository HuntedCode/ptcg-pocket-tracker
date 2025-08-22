from django.db import models
from django.contrib.auth.models import User
from django.db.models.deletion import SET_NULL
from django.db.models.signals import post_save
from django.dispatch import receiver
import json
import uuid

# Create your models here.
# Card/Collection Models

class Booster(models.Model):
    tcg_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    local_image_small = models.CharField(max_length=200, blank=True, default='')
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
    logo_path = models.CharField(max_length=50, blank=True)
    symbol = models.URLField(blank=True)
    boosters = models.ManyToManyField(Booster, related_name='sets', blank=True)

    def __str__(self):
        return self.name

class Card(models.Model):
    category = models.CharField(max_length=50)
    tcg_id = models.CharField(max_length=50, unique=True)
    illustrator = models.CharField(max_length=100, blank=True)
    image_base = models.CharField(max_length=200, blank=True)
    local_image_small = models.CharField(max_length=200, blank=True, default='')
    name = models.CharField(max_length=100)
    rarity = models.CharField(max_length=50)
    card_set = models.ForeignKey(Set, on_delete=models.CASCADE, related_name='cards')
    boosters = models.ManyToManyField(Booster, related_name='cards', blank=True)
    manual_boosters_added = models.BooleanField(default=False, help_text="Set to True if boosters were manually assigned")
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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    for_trade = models.BooleanField(default=False)
    is_seen = models.BooleanField(default=False)
    is_favorite = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'card')
    
    def __str__(self):
        return f"{self.user.username}'s {self.card.name} (x{self.quantity})"

class UserWant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    desired_quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('user', 'card')

    def __str__(self):
        return f"{self.user.username} wants {self.card.name} (x{self.desired_quantity})"

class Activity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    type = models.CharField(max_length=50, choices=[
        ('collection_add', 'Collection Add'),
        ('pack_open', 'Pack Open')
    ])
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.username} - {self.type} at {self.timestamp}"

# Profile/Social Models

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    share_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True)
    pic_config = models.JSONField(default=dict)
    is_trading_active = models.BooleanField(default=False, help_text="Enable to appear in matches and receive messages.")
    bio = models.TextField(blank=True, help_text="Share trading preferences (e.g., 'Only A1 sets').")
    favorite_set = models.ForeignKey(Set, on_delete=SET_NULL, null=True, blank=True, help_text="Your favorite TCG Pocket set.")
    display_favorites = models.JSONField(default=list, blank=True)
    theme = models.CharField(max_length=20, default='default')
    dark_mode = models.BooleanField(default=False, help_text="Enable dark mode theme")
    last_active = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

class Match(models.Model):
    initiator = models.ForeignKey(User, related_name='initiated_matches', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_matches', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('ignored', 'Ignored')
    ], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('initiator', 'recipient')
    
    def __str__(self):
        return f"{self.initiator.username} -> {self.recipient.username}: {self.status}"

class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"From {self.sender} to {self.receiver} at {self.timestamp}"

# Receivers

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()

@receiver(post_save, sender=UserCollection)
def log_new_collection_add(sender, instance, created, **kwargs):
    TRACKED_RARITIES = ['Four Diamond', 'One Star', 'Two Star', 'Three Star', 'One Shiny', 'Two Shiny', 'Crown']
    if created and instance.quantity > 0 and instance.card.rarity in TRACKED_RARITIES:
        content = json.dumps({'message': f"({instance.card.tcg_id}) {instance.card.name} - {instance.card.rarity}", 'card_id': instance.card.id})
        Activity.objects.create(user=instance.user, type='collection_add', content=content)