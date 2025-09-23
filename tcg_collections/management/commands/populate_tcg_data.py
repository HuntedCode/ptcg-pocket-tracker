from datetime import datetime
from django.core.management.base import BaseCommand
import requests
from tcg_collections.models import Booster, Set, Card
import time

class Command(BaseCommand):
    help = 'Populate DB with PTCG Pocket data from TCGdex API'

    def add_arguments(self, parser):
        parser.add_argument('--set_id', type=str, help='Populate only this specific set ID (e.g., A1)')
        parser.add_argument('--new_only', action='store_true', help='Process only new sets not already in the DB')
        parser.add_argument('--refresh_full', action='store_true', help='Refresh and update all cards/sets, even if they exist in the DB already')
        parser.add_argument('--booster_refresh', action='store_true', help='Refresh boosters of any cards processed')

    def handle(self, *args, **options):
        lang = 'en'
        set_id = options['set_id']
        new_only = options['new_only']
        refresh_full = options['refresh_full']
        booster_refresh = options['booster_refresh']

        sets_data = self.get_tcgp_sets(lang)
        last_set_id = sets_data.get('lastSet', {}).get('id')
        if not last_set_id:
            self.stdout.write(self.style.WARNING('No lastSet found in API response; trading flags may not update correctly'))

        if set_id:
            try:
                cards_data = self.get_cards_from_set(set_id, lang)
                set_info = {
                    'id': cards_data['id'],
                    'name': cards_data['name'],
                    'cardCount': cards_data.get('cardCount', {}),
                    'logo_path': f"images/set_logos/{cards_data['id']}_logo.png",
                    'symbol': cards_data.get('symbol', '')
                }
                self.create_or_update_set(set_info, lang, cards_data=cards_data, last_set_id=last_set_id, refresh_full=refresh_full, booster_refresh=booster_refresh)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error fetching set {set_id}: {e}"))
                return
        else:
            for cards_data in sets_data.get('sets', []):
                if not refresh_full and new_only and Set.objects.filter(tcg_id=cards_data['id']).exists():
                    self.stdout.write(self.style.NOTICE(f"Skipping existing set {cards_data['id']}"))
                    continue
                
                set_info = {
                    'id': cards_data['id'],
                    'name': cards_data['name'],
                    'cardCount': cards_data.get('cardCount', {}),
                    'logo_path': f"images/set_logos/{cards_data['id']}_logo.png",
                    'symbol': cards_data.get('symbol', '')
                }

                self.create_or_update_set(set_info, lang, last_set_id=last_set_id, refresh_full=refresh_full, booster_refresh=booster_refresh)

        self.stdout.write(self.style.SUCCESS('DB population complete!'))

    # API Functions
    def call_api(self, url, headers={}):
        response = requests.get(url, headers=headers, timeout=0.5)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API error: {response.status_code} - {response.text}")
        
    def get_tcgp_sets(self, lang='en'):
        url = f"https://api.tcgdex.net/v2/{lang}/series/tcgp"
        return self.call_api(url)

    def get_cards_from_set(self, set_id, lang='en'):
        url = f"https://api.tcgdex.net/v2/{lang}/sets/{set_id}"
        return self.call_api(url)
    
    def get_card_by_id(self, card_id, lang='en'):
        url = f"https://api.tcgdex.net/v2/{lang}/cards/{card_id}"
        return self.call_api(url)

    # DB Functions
    def create_or_update_set(self, set_info, lang='en', cards_data=None, last_set_id=None, refresh_full=False, booster_refresh=False):
        try:
            defaults = {
                        'name': set_info['name'],
                        'card_count_official': set_info.get('cardCount', {}).get('official'),
                        'card_count_total': set_info.get('cardCount', {}).get('total'),
                        'logo_path': set_info.get('logo_path'),
                        'symbol': set_info.get('symbol'),
            }
            
            if refresh_full:
                set_obj, _ = Set.objects.update_or_create(
                    tcg_id=set_info['id'],
                    defaults=defaults
                )
            else:
                set_obj, _ = Set.objects.get_or_create(
                    tcg_id=set_info['id'],
                    defaults=defaults
                )

            if cards_data is None:
                cards_data = self.get_cards_from_set(set_info['id'], lang)

            if cards_data.get('releaseDate'):
                try:
                    set_obj.release_date = datetime.strptime(cards_data['releaseDate'], '%Y-%m-%d').date()
                except ValueError:
                    self.stdout.write(self.style.WARNING(f"Invalid release_date format for set {set_info['id']}"))

            # Prefer to get set data from the set endpoint instead of series endpoint if possible.
            set_obj.card_count_official = cards_data.get('cardCount', {}).get('official', set_obj.card_count_official)
            set_obj.card_count_total = cards_data.get('cardCount', {}).get('total', set_obj.card_count_total)
            set_obj.symbol = cards_data.get('symbol', set_obj.symbol)
            set_obj.save()

            card_objs = []
            has_boosters = False

            for card_info in cards_data.get('cards', []):
                if not refresh_full and Card.objects.filter(tcg_id=card_info['id']).exists():
                    self.stdout.write(self.style.NOTICE(f"Skipping existing card {card_info['id']}"))
                    continue
                try:
                    card = self.get_card_by_id(card_info['id'], lang)
                    card_obj = self.create_or_update_card(card, set_obj, last_set_id, refresh_full, booster_refresh)
                    if card_obj:
                        card_objs.append(card_obj)
                    if card.get('boosters', []):
                        has_boosters = True
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Skipped card {card_info['id']}: {e}"))
            
            if not has_boosters:
                default_booster_id = f"boo_{set_obj.tcg_id}-{set_obj.name.replace(' ', '_')}"
                default_booster, _ = Booster.objects.get_or_create(
                    tcg_id=default_booster_id,
                    defaults={'name': f"{set_obj.name} Booster"}
                )
                set_obj.boosters.add(default_booster)
                for card_obj in card_objs:
                    card_obj.boosters.add(default_booster)
                    card_obj.save()

            self.stdout.write(self.style.SUCCESS(f"Set {set_obj.name} ({set_obj.tcg_id}) Created Successfully!"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Error creating set {set_info.get('id')}: {e}"))

    def create_or_update_card(self, card_info, set_obj: Set, last_set_id=None, refresh_full=False, booster_refresh=False) -> Card:
        try:
            tradeable_rarities = ['One Diamond', 'Two Diamond', 'Three Diamond', 'Four Diamond', 'One Star']
            is_tradeable = False if set_obj.tcg_id == last_set_id else (card_info['rarity'] in tradeable_rarities)
            type_list = card_info.get('types', [])
            if type_list:
                ptype = type_list[0]
            else:
                ptype = ''

            defaults = {
                    'category': card_info['category'],
                    'illustrator': card_info.get('illustrator', ''),
                    'image_base': card_info.get('image', ''),
                    'name': card_info['name'],
                    'rarity': card_info['rarity'],
                    'card_set': set_obj,
                    'is_tradeable': is_tradeable,

                    # Pokemon Specific
                    'type': ptype,
                    'stage': card_info.get('stage', ''),
                    'hp': card_info.get('hp'),
                    'suffix': card_info.get('suffix', ''),

                    # Trainer Specific
                    'trainer_type': card_info.get('trainerType', '')
            }

            if refresh_full:
                card_obj, created = Card.objects.update_or_create(
                    tcg_id=card_info['id'],
                    defaults=defaults
                )
            else:
                card_obj, created = Card.objects.get_or_create(
                    tcg_id=card_info['id'],
                    defaults=defaults
                )

            if created or booster_refresh:
                for booster in card_info.get('boosters', []):
                    booster_obj = self.create_or_update_booster(booster)
                    card_obj.boosters.add(booster_obj)
                    set_obj.boosters.add(booster_obj)
            
            self.stdout.write(self.style.SUCCESS(f"Card {card_obj.name} ({card_obj.tcg_id}) Created Successfully!"))
            return card_obj
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Error creating card {card_info.get('id')}: {e}"))
            return None

    def create_or_update_booster(self, booster_info) -> Booster:
        try:
            booster_obj, _ = Booster.objects.get_or_create(
                tcg_id=booster_info['id'],
                defaults={'name': booster_info['name']}
            )
            return booster_obj
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Error creating booster {booster_info.get('id')}: {e}"))
            return None
