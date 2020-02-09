import json

import requests


class ZSR:
    """
    Class for interacting with ootrandomizer.com to generate seeds, and
    zeldaspeedruns.com to get available presets.
    """
    seed_public = 'https://ootrandomizer.com/seed/get?id=%(seedID)s'
    seed_endpoint = 'https://ootrandomizer.com/api/seed/preset'
    preset_endpoint = 'https://www.zeldaspeedruns.com/assets/ootr_presets.json'

    def __init__(self, ootr_api_key):
        self.ootr_api_key = ootr_api_key

    def load_presets(self):
        """
        Load and return available seed presets.
        """
        resp = requests.get(self.preset_endpoint)
        data = json.loads(resp.content)
        return {
            key: value['fullName']
            for key, value in data.items()
        }

    def roll_seed(self, preset, encrypt):
        """
        Generate a seed and return its public URL.
        """
        resp = requests.post(self.seed_endpoint, preset, params={
            'key': self.ootr_api_key,
            'encrypt': 'true' if encrypt else 'false',
        }, headers={'Content-Type': 'text/plain'})
        data = json.loads(resp.content)
        return self.seed_public % data
