import json

import requests


class ZSR:
    """
    Class for interacting with ootrandomizer.com to generate seeds and available presets.
    """
    seed_public = 'https://ootrandomizer.com/seed/get?id=%(id)s'
    seed_endpoint = 'https://ootrandomizer.com/api/v2/seed/create'
    status_endpoint = 'https://ootrandomizer.com/api/v2/seed/status'
    details_endpoint = 'https://ootrandomizer.com/api/v2/seed/details'
    version_endpoint = 'https://ootrandomizer.com/api/version'
    preset_endpoint = 'https://ootrandomizer.com/rtgg/ootr_presets.json'
    preset_dev_endpoint = 'https://ootrandomizer.com/rtgg/ootr_presets_dev.json'
    settings_endpoint = 'https://raw.githubusercontent.com/TestRunnerSRL/OoT-Randomizer/release/data/presets_default.json'
    settings_dev_endpoint = 'https://raw.githubusercontent.com/TestRunnerSRL/OoT-Randomizer/Dev/data/presets_default.json'
    qualifier_placement_endpoint = 'https://ootrandomizer.com/tournament/seedsOnly'
    draft_settings_pool_endpoint = 'https://ootrandomizer.com/rtgg/draft_settings.json'

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
        self.presets_dev = self.load_presets_dev()
        self.last_known_dev_version = None
        self.get_latest_dev_version()

    def load_presets(self):
        """
        Load and return available seed presets.
        """
        presets = requests.get(self.preset_endpoint).json()
        settings = requests.get(self.settings_endpoint).json()
        return {
            preset: {
                'full_name': setting,
                'settings': settings.get(setting)
            }
            for preset in presets for setting in settings
            if preset in settings[setting]['aliases']
        }

    def load_presets_dev(self):
        """
        Load and return available seed presets for dev.
        """
        presets_dev = requests.get(self.preset_dev_endpoint).json()
        settings_dev = requests.get(self.settings_dev_endpoint).json()
        return {
            preset: {
                'full_name': setting,
                'settings': settings_dev.get(setting)
            }
            for preset in presets_dev for setting in settings_dev
            if preset in settings_dev[setting]['aliases']
        }

    def get_latest_dev_version(self):
        """
        Returns currently active dev version and a bool indicating if it's changed.
        """
        version_req = requests.get(self.version_endpoint, params={'branch': 'dev'}).json()
        latest_dev_version = version_req['currentlyActiveVersion']
        if latest_dev_version != self.last_known_dev_version:
            self.last_known_dev_version = latest_dev_version
            return latest_dev_version, True
        return latest_dev_version, False

    def roll_seed(self, preset, encrypt, dev, settings, race_type):
        """
        Generate a seed and return its public URL.
        """
        if dev:
            latest_dev_version, changed = self.get_latest_dev_version()
            if changed:
                self.presets_dev = self.load_presets_dev()
            # Roll with provided preset for non-draft races.
            if preset is not None:
                req_body = json.dumps(self.presets_dev[preset]['settings'])
            # Fetch tournament preset and patch with drafted settings.
            else:
                req_body = json.dumps(settings)
        else:
            # Roll with provided preset for non-draft races.
            if preset is not None:
                req_body = json.dumps(self.presets[preset]['settings'])
            # Fetch tournament preset and patch with drafted settings.
            else:
                req_body = json.dumps(settings)

        params = {
            'key': self.ootr_api_key,
        }
        if encrypt and not dev:
            params['encrypt'] = 'true'
        if encrypt and dev:
            params['locked'] = 'true'
        if race_type == 'qualifier':
            params['hideSettings'] = 'true'
        if dev:
            params['version'] = 'dev_' + latest_dev_version
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
    
    def load_qualifier_placements(self):
        """
        Returns qualifier placement data for Tournament matches.
        """
        placement = requests.get(self.qualifier_placement_endpoint).json()
        return placement
    
    def load_available_settings(self):
        """
        Settings pool for Draft Mode.
        """
        pool = requests.get(self.draft_settings_pool_endpoint).json()
        return pool
