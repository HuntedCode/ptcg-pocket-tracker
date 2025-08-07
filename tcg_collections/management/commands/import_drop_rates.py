import csv
from django.core.management.base import BaseCommand
from tcg_collections.models import Booster, BoosterDropRate

class Command(BaseCommand):
    help = 'Bulk import BoosterDropRate from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('--csv_file', type=str, required=True, help='Path to the CSV file')
    
    def handle(self, *args, **options):
        csv_file = options['csv_file']
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    booster = Booster.objects.get(tcg_id=row['booster_tcg_id'])
                    BoosterDropRate.objects.update_or_create(
                        booster=booster,
                        slot=row['slot'],
                        rarity=row['rarity'],
                        defaults={'probability': float(row['probability'])}
                    )
            self.stdout.write(self.style.SUCCESS('Import complete!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))