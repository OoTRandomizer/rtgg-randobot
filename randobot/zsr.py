import json

import requests


class ZSR:
    """
    Class for interacting with ootrandomizer.com to generate seeds, and
    zeldaspeedruns.com to get available presets.
    """
    seed_public = 'https://ootrandomizer.com/seed/get?id=%(id)s'
    seed_endpoint = 'https://ootrandomizer.com/api/v2/seed/create'
    status_endpoint = 'https://ootrandomizer.com/api/v2/seed/status'
    details_endpoint = 'https://ootrandomizer.com/api/v2/seed/details'
    preset_endpoint = 'https://www.zeldaspeedruns.com/assets/ootr_presets.json'
    settings_endpoint = 'https://raw.githubusercontent.com/TestRunnerSRL/OoT-Randomizer/release/data/presets_default.json'

    hash_map = {
        'Beans': 'HashBeans',
        'Big Magic': 'HashBigMagic',
        'Bombchu': 'HashBombchu',
        'Boomerang': 'HashBoomerang',
        'Boss Key': 'HashBossKey',
        'Bottled Fish': 'HashBottledFish',
        'Bottled Milk': 'HashBottledMilk',
        'Bow': 'HashBow',
        'Compass': 'HashCompass',
        'Cucco': 'HashCucco',
        'Deku Nut': 'HashDekuNut',
        'Deku Stick': 'HashDekuStick',
        'Fairy Ocarina': 'HashFairyOcarina',
        'Frog': 'HashFrog',
        'Gold Scale': 'HashGoldScale',
        'Heart Container': 'HashHeart',
        'Hover Boots': 'HashHoverBoots',
        'Kokiri Tunic': 'HashKokiriTunic',
        'Lens of Truth': 'HashLensOfTruth',
        'Longshot': 'HashLongshot',
        'Map': 'HashMap',
        'Mask of Truth': 'HashMaskOfTruth',
        'Master Sword': 'HashMasterSword',
        'Megaton Hammer': 'HashHammer',
        'Mirror Shield': 'HashMirrorShield',
        'Mushroom': 'HashMushroom',
        'Saw': 'HashSaw',
        'Silver Gauntlets': 'HashSilvers',
        'Skull Token': 'HashSkullToken',
        'Slingshot': 'HashSlingshot',
        'SOLD OUT': 'HashSoldOut',
        'Stone of Agony': 'HashStoneOfAgony',
    }

    def __init__(self, ootr_api_key):
        self.ootr_api_key = ootr_api_key
        self.presets = self.load_presets()

    def load_presets(self):
        """
        Load and return available seed presets.
        """
        presets = requests.get(self.preset_endpoint).json()
        settings = requests.get(self.settings_endpoint).json()
        return {
            key: {
                'full_name': value['fullName'],
                'settings': settings.get(value['fullName']),
            }
            for key, value in presets.items()
            if value['fullName'] in settings
        }

    def roll_seed(self, preset, encrypt):
        """
        Generate a seed and return its public URL.
        """
        req_body = json.dumps(self.presets[preset]['settings'])
        params = {
            'key': self.ootr_api_key,
        }
        if encrypt:
            params['encrypt'] = 'true'
        data = requests.post(self.seed_endpoint, req_body, params=params,
                             headers={'Content-Type': 'application/json'}).json()
        return data['id'], self.seed_public % data

    def get_status(self, seed_id):
        data = requests.get(self.status_endpoint, params={
            'id': seed_id,
            'key': self.ootr_api_key,
        }).json()
        return data['status']

    def get_hash(self, seed_id):
        data = requests.get(self.details_endpoint, params={
            'id': seed_id,
            'key': self.ootr_api_key,
        }).json()
        try:
            settings = json.loads(data.get('settingsLog'))
        except ValueError:
            return None
        return ' '.join(
            self.hash_map.get(item, item)
            for item in settings['file_hash']
        )
