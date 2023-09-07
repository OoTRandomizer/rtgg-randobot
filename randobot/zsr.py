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
            key: {
                'full_name': value['fullName'],
                'settings': settings.get(value['fullName']),
            }
            for key, value in presets.items()
            if value['fullName'] in settings
        }

    def load_presets_dev(self):
        """
        Load and return available seed presets for dev.
        """
        presets_dev = requests.get(self.preset_dev_endpoint).json()
        settings_dev = requests.get(self.settings_dev_endpoint).json()
        return {
            key: {
                'full_name': value['fullName'],
                'settings': settings_dev.get(value['fullName']),
            }
            for key, value in presets_dev.items()
            if value['fullName'] in settings_dev
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

    def roll_seed(self, preset, encrypt, dev, settings):
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
                self.presets_dev.get('s6').get('settings').update(settings)
                req_body = json.dumps(self.presets_dev.get('s6').get('settings'))
        else:
            # Roll with provided preset for non-draft races.
            if preset is not None:
                req_body = json.dumps(self.presets[preset]['settings'])
            # Fetch tournament preset and patch with drafted settings.
            else:
                self.presets_dev.get('s6').get('settings').update(settings)
                req_body = json.dumps(self.presets_dev.get('s6').get('settings'))

        params = {
            'key': self.ootr_api_key,
        }
        if encrypt and not dev:
            params['encrypt'] = 'true'
        if encrypt and dev:
            params['locked'] = 'true'
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
        Hard-coded settings pool for Draft Mode.
        """
        return {
            'major': {
                'bridge': {
                    'meds': {
                        'bridge': 'medallions'
                    },
                    'open': {
                        'bridge': 'open',
                        'shuffle_ganon_bosskey': 'medallions'
                    }
                },
                'deku': {
                    'closed': {
                        'open_forest': 'closed_deku'
                    },
                    'open': {
                        'open_forest': 'open'
                    }
                },
                'interiors': {
                    'vanilla': {
                        'shuffle_interior_entrances': 'off'
                    },
                    'shuffled': {
                        'shuffle_interior_entrances': 'all'
                    }
                },
                'dungeons': {
                    'vanilla': {
                        'shuffle_dungeon_entrances': 'off'
                    },
                    'shuffled': {
                        'shuffle_dungeon_entrances': 'simple'
                    }
                },
                'grottos': {
                    'vanilla': {
                        'shuffle_grotto_entrances': False
                    },
                    'shuffled': {
                        'shuffle_grotto_entrances': True
                    }
                },
                'shops': {
                    'vanilla': {
                        'shopsanity': 'off'
                    },
                    '4': {
                        'shopsanity': 4,
                        'start_with_rupees': True
                    }
                },
                'tokens': {
                    'vanilla': {
                        'tokensanity': 'off'
                    },
                    'dungeons': {
                        'tokensanity': 'dungeons'
                    },
                    'overworld': {
                        'tokensanity': 'overworld'
                    }
                },
                'scrubs': {
                    'vanilla': {
                        'shuffle_scrubs': 'off'
                    },
                    'shuffled': {
                        'shuffle_scrubs': 'low'
                    }
                },
                'keys': {
                    'dungeon': {
                        'shuffle_smallkeys': 'dungeon',
                        'shuffle_bosskeys': 'dungeon'
                    },
                    'keysy': {
                        'shuffle_smallkeys': 'remove',
                        'shuffle_bosskeys': 'remove'
                    },
                    'anywhere': {
                        'shuffle_smallkeys': 'keysanity',
                        'key_rings_choice': 'all',
                        'keyring_give_bk': True
                    }
                },
                'required_only': {
                    'off': {
                        'reachable_locations': 'all'
                    },
                    'on': {
                        'reachable_locations': 'beatable'
                    }
                },
                'fountain': {
                    'closed': {
                        'zora_fountain': 'closed'
                    },
                    'open': {
                        'zora_fountain': 'open'
                    }
                },
                'cows': {
                    'vanilla': {
                        'shuffle_cows': False
                    },
                    'shuffled': {
                        'shuffle_cows': True
                    }
                },
                'gerudo_card': {
                    'vanilla': {
                        'shuffle_gerudo_card': False
                    },
                    'shuffled': {
                        'shuffle_gerudo_card': True
                    }
                },
                'trials': {
                    'off': {
                        'trials': 0
                    },
                    '3': {
                        'trials': 3
                    }
                }
            },
            'minor': {
                'starting_age': {
                    'random': {
                        'starting_age': 'random'
                    },
                    'child': {
                        'starting_age': 'child'
                    },
                    'adult': {
                        'starting_age': 'adult'
                    }
                },
                'spawns': {
                    'vanilla': {
                        'spawn_positions': []
                    },
                    'random': {
                        'spawn_positions': ['child', 'adult']
                    }
                },
                'consumables': {
                    'startwith': {
                        'start_with_consumables': True
                    },
                    'none': {
                        'start_with_consumables': False
                    }
                },
                'rupees': {
                    'none': {
                        'start_with_rupees': False
                    },
                    'startwith': {
                        'start_with_rupees': True
                    }
                },
                'cuccos': {
                    '7': {
                        'chicken_count': 7
                    },
                    '1': {
                        'chicken_count': 1
                    }
                },
                'scarecrow': {
                    'vanilla': {
                        'free_scarecrow': False
                    },
                    'free': {
                        'free_scarecrow': True
                    }
                },
                'camc': {
                    'on': {
                        'correct_chest_appearances': 'both'
                    },
                    'off': {
                        'correct_chest_appearances': 'off'
                    }
                },
                'mask_quest': {
                    'default': {
                        'complete_mask_quest': False
                    },
                    'complete': {
                        'complete_mask_quest': True,
                        'fast_bunny_hood': False
                    }
                },
                'blue_fire_arrows': {
                    'off': {
                        'blue_fire_arrows': False
                    },
                    'on': {
                        'blue_fire_arrows': True
                    }
                },
                'owl_warps': {
                    'vanilla': {
                        'owl_drops': False
                    },
                    'random': {
                        'owl_drops': True
                    }
                },
                'song_warps': {
                    'vanilla': {
                        'warp_songs': False
                    },
                    'random': {
                        'warp_songs': True
                    }
                },
                'beans': {
                    'vanilla': {
                        'shuffle_beans': False
                    },
                    'shuffled': {
                        'shuffle_beans': True
                    }
                },
                'expensive_merchants': {
                    'vanilla': {
                        'shuffle_expensive_merchants': False
                    },
                    'shuffled': {
                        'shuffle_expensive_merchants': True
                    }
                },
                'beans_planted': {
                    'off': {
                        'plant_beans': False
                    },
                    'on': {
                        'plant_beans': True
                    }
                },
                'door_of_time': {
                    'open': {
                        'open_door_of_time': True
                    },
                    'closed': {
                        'open_door_of_time': False
                    }
                },
                'bombchus_in_logic': {
                    'off': {
                        'free_bombchu_drops': False
                    },
                    'on': {
                        'free_bombchu_drops': True
                    }
                }
            }
        }