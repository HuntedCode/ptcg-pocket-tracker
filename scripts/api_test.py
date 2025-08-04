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


try:
    #sets = get_tcgp_sets()
    #print("TCG Pocket Sets:")
    #print(json.dumps(sets, indent=4))

    #cards = get_cards_from_set('A1')
    #print("TCGP Genetic Apex Cards:")
    #print(json.dumps(cards, indent=4))

    #for card in cards.get('cards', [])[:5]:
        #print(f"Card ID: {card['id']}, Name: {card['name']}")
    
    card_ids = ["A1-001", "A1-002", "A1-003", "A1-004", "A1-005"]
    for id in card_ids:
        print(json.dumps(get_card_by_id(id), indent=4))

except Exception as e:
    print(f"Error: {e}")