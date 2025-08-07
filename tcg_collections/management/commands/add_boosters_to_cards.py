import csv
from django.core.management.base import BaseCommand
from tcg_collections.models import Card, Booster

class Command(BaseCommand):
    help = 'Add boosters to specific cards from a CSV file and add manual_boosters_added flag'

    def add_arguments(self, parser):
        parser.add_argument('--csv_file', type=str, required=True, help='Path to CSV file.')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    card_tcg_id = row['card_tcg_id'].strip()
                    booster_tcg_id = row['booster_tcg_id'].strip()

                    try:
                        card = Card.objects.get(tcg_id=card_tcg_id)
                        booster = Booster.objects.get(tcg_id=booster_tcg_id)

                        if booster not in card.boosters.all():
                            card.boosters.add(booster)
                            self.stdout.write(self.style.SUCCESS(f"Added booser {booster.name} to card {card.name} ({card_tcg_id})"))
                        
                        card.manual_boosters_added = True
                        card.save()

                    except Card.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Card {card_tcg_id} not found--skipped"))
                    except Booster.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Booster {booster_tcg_id} not found--skipped"))
            self.stdout.write(self.style.SUCCESS('Booster addition complete!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing CSV: {e}"))