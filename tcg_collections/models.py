from django.db import models
from django.contrib.auth.models import User
from django.db.models import JSONField

# Create your models here.
class Booster(models.Model):
    tcg_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Set(models.Model):
    tcg_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    release_date = models.DateField(null=True, blank=True)
    card_count = models.PositiveIntegerField(null=True, blank=True)
    logo = models.URLField(blank=True)
    symbol = models.URLField(blank=True)
    boosters = models.ManyToManyField(Booster, related_name='sets', blank=True)

    def __str__(self):
        return self.name

class Card(models.Model):
    category = models.CharField(max_length=50)
    tcg_id = models.CharField(max_length=50, unique=True)
    illustrator = models.CharField(max_length=100, blank=True)
    image_base = models.CharField(max_length=200, blank=True)
    name = models.CharField(max_length=100)
    rarity = models.CharField(max_length=50)
    card_set = models.ForeignKey(Set, on_delete=models.CASCADE, related_name='cards')
    boosters = models.ManyToManyField(Booster, related_name='cards', blank=True)

    # Pokemon Specific
    types = JSONField(default=list, blank=True)
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

    class Meta:
        unique_together = ('user', 'card')
    
    def __str__(self):
        return f"{self.user.username}'s {self.card.name} (x{self.quantity})"
    