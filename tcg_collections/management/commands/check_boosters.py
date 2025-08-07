from django.core.management.base import BaseCommand
import requests

class Command(BaseCommand):
    help = 'Check if boosters are available in TCGdex API for specified set'

    def add_arguments(self, parser):
        parser.add_argument('--set_id', type=str, required=True, help='Set ID to check (e.g., A1)')

    def handle(self, *args, **options):
        lang = 'en'
        set_id = options['set_id']

        try:
            url = f"https://api.tcgdex.net/v2/{lang}/cards/{set_id+'-001'}"
            response = requests.get(url)
            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code}")
            
            card_data = response.json()
            boosters = card_data.get('boosters', [])

            if boosters:
                self.stdout.write(self.style.SUCCESS(f"Boosters are now available for set {card_data['set']['name']}! Sample: {boosters}"))
            else:
                self.stdout.write(self.style.WARNING(f"No boosters yet found for {card_data['set']['name']}. Check again later."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error checking card {set_id}: {e}"))