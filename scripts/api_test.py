import requests
import json

def call_api(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API error: {response.status_code} - {response.text}")

def get_tcgp_sets(language='en'):
    url = f"https://api.tcgdex.net/v2/{language}/series/tcgp"
    return call_api(url)

def get_cards_from_set(set, language='en'):
    url = f"https://api.tcgdex.net/v2/{language}/sets/{set}"
    return call_api(url)

def get_card_by_id(id, language='en'):
    url = f"https://api.tcgdex.net/v2/{language}/cards/{id}"
    return call_api(url)

def print_card(card_json):
    card_data = json.loads(card_json)
    card = {
        'category': card_data['category'],
        'id': card_data['id'],
        'illustrator': card_data['illustrator'],
        'image': card_data['image'],
        'name': card_data['name'],
        'rarity': card_data['rarity'],
        'set_data': {'id': card_data['set']['id'], 'name': card_data['set']['name']}
    }
    
    boosters = []
    for b in card_data['boosters']:
        b_dict = {'id': b['id'], 'name': b['name']}
        boosters.append(b_dict)
    card['boosters'] = boosters

    if card['category'] == "Pokemon":
        card['types'] = card_data['types']
        card['stage'] = card_data['stage']
        card['hp'] = card_data['hp']
        if 'suffix' in card_data:
            card['suffix'] = card_data['suffix']
    elif card['category'] == "Trainer":
        card['trainer_type'] = card_data['trainerType']
    

    print(card)


#try:
    #sets = get_tcgp_sets()
    #print("TCG Pocket Sets:")
    #print(json.dumps(sets, indent=4))

    #cards = get_cards_from_set('A1')
    #print("TCGP Genetic Apex Cards:")
    #print(json.dumps(cards, indent=4))

    #for card in cards.get('cards', [])[:5]:
        #print(f"Card ID: {card['id']}, Name: {card['name']}")
    
card_ids = ["A1-001", "A1-002", "A1-216", "A1-219", "A1-259"]
for id in card_ids:
    print_card(json.dumps(get_card_by_id(id)))

#except Exception as e:
 #   print(f"Error: {e}")