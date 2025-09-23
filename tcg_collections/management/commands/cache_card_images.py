import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from tcg_collections.models import Card
import os

class Command(BaseCommand):
    help = 'Download and cache small images for cards from TCGdex API'

    def add_arguments(self, parser):
        parser.add_argument('--set_id', type=str, help='Cache only for this set ID (e.g., A1)')

    def handle(self, *args, **options):
        set_id = options['set_id']
        cards = Card.objects.all()
        if set_id:
            cards = cards.filter(card_set__tcg_id=set_id)
        
        os.makedirs(os.path.join(settings.STATIC_ROOT, 'cards'), exist_ok=True)

        for card in cards:
            if card.local_image_small:
                self.stdout.write(self.style.NOTICE(f"Skipping cache card {card.tcg_id}"))
                continue
            if not card.image_base:
                self.stdout.write(self.style.NOTICE(f"Card {card.tcg_id} has no image link! Skipping.."))
                continue
            url = f"{card.image_base}/low.png"
            file_path = os.path.join(settings.STATIC_ROOT, 'cards', f"{card.tcg_id}_low.png")
            if os.path.exists(file_path):
                card.local_image_small = f"cards/{card.tcg_id}_low.png"
                card.save()
                print("Image already in cache! Updated DB row with path.")
                continue
            response = requests.get(url, headers={}, timeout=0.5)
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                card.local_image_small = f"cards/{card.tcg_id}_low.png"
                card.save()
                self.stdout.write(self.style.SUCCESS(f"Cached image for {card.tcg_id}"))
            else:
                self.stdout.write(self.style.WARNING(f"Failed to fetch image for {card.tcg_id}: {response.status_code}"))
        
        self.stdout.write(self.style.SUCCESS('Image caching complete!'))