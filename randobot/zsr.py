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
        # pool = requests.get(self.draft_settings_pool_endpoint).json()
        # return pool
        return {
            "major": {
                "bridge": {
                    "__setting": "Rainbow Bridge",
                    "default": "meds",
                    "options": {
                        "meds": {
                            "name": "6 meds - No GCBK",
                            "data": {
                                "bridge": "medallions"   
                            }
                        },
                        "open": {
                            "name": "Open - 6 med GCBK",
                            "data": {
                                "bridge": "medallions",
                                "shuffle_ganon_bosskey": "medallions"
                            }
                        }
                    }
                },
                "deku": {
                    "__setting": "Deku",
                    "default": "closed",
                    "options": {
                        "closed": {
                            "name": "Closed",
                            "data": {
                                "open_forest": "closed_deku"
                            }
                        },
                        "open": {
                            "name": "Open",
                            "data": {
                                "open_forest": "open"
                            }
                        }
                    }
                },
                "interiors": {
                    "__setting": "Interior ER",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "shuffle_interior_entrances": "off"
                            }
                        },
                        "on": {
                            "name": "On (all interiors)",
                            "data": {
                                "shuffle_interior_entrances": "all"
                            }
                        }
                    }
                },
                "dungeons": {
                    "__setting": "Dungeon ER",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "shuffle_dungeon_entrances": "off"
                            }                    
                        },
                        "on": {
                            "name": "Simple (excl. Ganon's Castle)",
                            "data": {
                                "shuffle_dungeon_entrances": "simple"
                            }
                        }
                    }
                },
                "grottos": {
                    "__setting": "Grotto ER",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "shuffle_grotto_entrances": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "shuffle_grotto_entrances": True
                            }
                        }
                    }
                },
                "shops": {
                    "__setting": "Shopsanity",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "shopsanity": "off"
                            }
                        },
                        "on": {
                            "name": "On (4)",
                            "data": {
                                "shopsanity": "4"
                            }
                        }
                    }
                },
                "ow_tokens": {
                    "__setting": "Overworld Tokens",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "tokensanity": "off"
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "tokensanity": "overworld"
                            }
                        }
                    }
                },
                "dungeon_tokens": {
                    "__setting": "Dungeon Tokens",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "tokensanity": "off"
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "tokensanity": "dungeons"
                            }
                        }
                    }
                },
                "scrubs": {
                    "__setting": "Scrub Shuffle",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "shuffle_scrubs": "off"
                            }
                        },
                        "on": {
                            "name": "On (affordable)",
                            "data": {
                                "shuffle_scrubs": "low"
                            }
                        }
                    }
                },
                "keys": {
                    "__setting": "Key Shuffle",
                    "default": "own_dungeon",
                    "options": {
                        "own_dungeon": {
                            "name": "Own Dungeon",
                            "data": {
                                "shuffle_smallkeys": "dungeon",
                                "shuffle_bosskeys": "dungeon"
                            }
                        },
                        "keysy": {
                            "name": "Keysy (inc. BK)",
                            "data": {
                                "shuffle_smallkeys": "remove",
                                "shuffle_bosskeys": "remove"
                            }
                        },
                        "anywhere": {
                            "name": "Keyrings Anywhere (inc. BK)",
                            "data": {
                                "shuffle_smallkeys": "keysanity",
                                "key_rings_choice": "all",
                                "keyring_give_bk": True
                            }
                        }
                    }
                },
                "required_only": {
                    "__setting": "Required Only (Beatable Only)",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "reachable_locations": "all"
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "reachable_locations": "beatable"
                            }
                        }
                    }
                },
                "zora_fountain": {
                    "__setting": "Zora Fountain",
                    "default": "closed",
                    "options": {
                        "closed": {
                            "name": "Closed",
                            "data": {
                                "zora_fountain": "closed"
                            }
                        },
                        "open": {
                            "name": "Open",
                            "data": {
                                "zora_fountain": "open"
                            }
                        }
                    }
                },
                "cows": {
                    "__setting": "Cow Shuffle",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "shuffle_cows": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "shuffle_cows": True
                            }
                        }
                    }
                },
                "gerudo_card": {
                    "__setting": "Shuffled Gerudo Card",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "shuffle_gerudo_card": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "shuffle_gerudo_card": True
                            }
                        }
                    }
                },
                "trials": {
                    "__setting": "Trials",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "trials": 0
                            }
                        },
                        "on": {
                            "name": "On (3 random)",
                            "data": {
                                "trials": 3
                            }
                        }
                    }
                }
            },
            "minor": {
                "starting_age": {
                    "__setting": "Starting Age",
                    "default": "random",
                    "options": {
                        "random": {
                            "name": "Random",
                            "data": {
                                "starting_age": "random"
                            }
                        },
                        "child": {
                            "name": "Child",
                            "data": {
                                "starting_age": "child"   
                            }
                        },
                        "adult": {
                            "name": "Adult",
                            "data": {
                                "starting_age": "adult"
                            }
                        }
                    }
                },
                "random_spawns": {
                    "__setting": "Random Spawns",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "spawn_positions": []
                            }
                        },
                        "on": {
                            "name": "On (both)",
                            "data": {
                                "spawn_positions": [
                                    "child",
                                    "adult"
                                ]
                            }
                        }
                    }
                },
                "consumables": {
                    "__setting": "Start with Consumables",
                    "default": "on",
                    "options": {
                        "on": {
                            "name": "On",
                            "data": {
                                "start_with_consumables": True
                            }
                        },
                        "off": {
                            "name": "Off",
                            "data": {
                                "start_with_consumables": False
                            }
                        }
                    }
                },
                "rupees": {
                    "__setting": "Start with Rupees",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "start_with_rupees": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "start_with_rupees": True
                            }
                        }
                    }
                },
                "cuccos": {
                    "__setting": "Chicken Count",
                    "default": "7",
                    "options": {
                        "7": {
                            "name": "7",
                            "data": {
                                "chicken_count": 7
                            }
                        },
                        "1": {
                            "name": "1",
                            "data": {
                                "chicken_count": 1
                            }
                        }
                    }
                },
                "free_scarecrow": {
                    "__setting": "Free Scarecrow",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "free_scarecrow": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "free_scarecrow": True
                            }
                        }
                    }
                },
                "camc": {
                    "__setting": "Chest Appearance Matches Contents",
                    "default": "on",
                    "options": {
                        "on": {
                            "name": "On (Size and Texture)",
                            "data": {
                                "correct_chest_appearances": "both"
                            }
                        },
                        "off": {
                            "name": "Off",
                            "data": {
                                "correct_chest_appearances": "off"   
                            }
                        }
                    }
                },
                "mask_quest": {
                    "__setting": "Completed Mask Quest",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "complete_mask_quest": False
                            }
                        },
                        "on": {
                            "name": "On (w/ slow Bunny Hood)",
                            "data": {
                                "complete_mask_quest": True,
                                "fast_bunny_hood": False
                            }
                        }
                    }
                },
                "bfa": {
                    "__setting": "Blue Fire Arrows",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "blue_fire_arrows": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "blue_fire_arrows": True
                            }
                        }
                    }
                },
                "owls": {
                    "__setting": "Random Owl Drops",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "owl_drops": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "owl_drops": True
                            }
                        }
                    }
                },
                "song_warps": {
                    "__setting": "Random Song Warps",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "warp_songs": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "warp_songs": True
                            }
                        }
                    }
                },
                "shuffle_beans": {
                    "__setting": "Shuffled Magic Beans",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "shuffle_beans": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "shuffle_beans": True
                            }
                        }
                    }
                },
                "expensive_merchants": {
                    "__setting": "Expensive Merchants",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "shuffle_expensive_merchants": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "shuffle_expensive_merchants": True
                            }
                        }
                    }
                },
                "beans_planted": {
                    "__setting": "Planted Magic Beans",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "plant_beans": False
                            }
                        },
                        "on": {
                            "name": "On",
                            "data": {
                                "plant_beans": True
                            }
                        }
                    }
                },
                "door_of_time": {
                    "__setting": "Door of Time",
                    "default": "open",
                    "options": {
                        "open": {
                            "name": "Open",
                            "data": {
                                "open_door_of_time": True
                            }
                        },
                        "closed": {
                            "name": "Closed",
                            "data": {
                                "open_door_of_time": False
                            }
                        }
                    }
                },
                "chus_in_logic": {
                    "__setting": "Bombchus in Logic",
                    "default": "off",
                    "options": {
                        "off": {
                            "name": "Off",
                            "data": {
                                "free_bombchu_drops": False
                            }
                        },
                        "on": {
                            "name": "On (adds Bombchu Bag)",
                            "data": {
                                "free_bombchu_drops": True
                            }
                        }
                    }
                }
            }
        }
