import random
from copy import deepcopy

class Handler:
    """
    Base class for handling draft data
    """
    def __init__(self, settings_pool):
        self.settings_pool = settings_pool
        self.generator_data = {}

    def handle_conditional_settings(self, selections, preset):
        patched_settings = deepcopy(preset)
        _data = self.generator_data

        # Handled seperated tokensanity settings
        if 'Overworld Tokens' in selections and 'Dungeon Tokens' in selections:
            _data.update({'tokensanity': 'all'})

        patched_settings.update(_data)

        # If dungeon er is on, add logic_dc_scarecrow_gs to trick list
        for setting in _data:
            if setting == 'shuffle_dungeon_entrances' and _data[setting] == 'simple':
                patched_settings['allowed_tricks'].append('logic_dc_scarecrow_gs')
        return patched_settings
    
class PlayerDraft(Handler):
    """
    Class for handling draft-style races
    """
    def __init__(self, entrants, settings_pool, config, qual_data):
        super().__init__(settings_pool)
        self.race_type, *self.draftees, self.is_tournament_race, self.bans_each, self.major_picks_each, self.minor_picks_each = config
        self.player_bans = {}
        self.player_picks = {}
        self.current_selector = None
        self.determine_higher_seed(entrants, qual_data)

    def determine_higher_seed(self, entrants, qual_data):
        _draftees = []
        # Sort by qualifier placement
        if self.is_tournament_race:
            for draftee in self.draftees:
                for racer in qual_data:
                    if draftee == racer['name'].lower():
                        _draftees.append({'name': draftee, 'place': racer['place']})
            self.draftees = sorted(_draftees, key=lambda draftee: draftee['place'])
        # Sort by racetime.gg points
        else:
            for draftee in self.draftees:
                for entrant in entrants:
                    if draftee == entrant['user']['name'].lower():
                        _draftees.append({'name': draftee, 'score': entrant['score'] if entrant.get('score') else 0})
            self.draftees = sorted(_draftees, key=lambda draftee: draftee['score'], reverse=True)

    def assign_draft_order(self, message, config):
        if len(self.draftees) == 2:
            user = message.get('user', {}).get('name')
            if user == self.draftees[0]['name']:
                if message.get('message_plain', '') == '!first':
                    self.current_selector = self.draftees[0]['name']
                elif message.get('message_plain', '') == '!second':
                    self.current_selector = self.draftees[1]['name']
            return
        self.draftees = config
        self.current_selector = self.draftees[0]

    def skip_ban(self):
        pass

    def ban_setting(self):
        pass

    def pick_setting(self):
        pass

    def send_available_settings(self):
        pool = self.settings_pool
        return {
            setting: f"{pool[setting]['__setting']}: {pool[setting]['options'][pool[setting]['default']]['name']}"
            for setting in pool
        }

class RandomDraft(Handler):
    """
    Class for handling auto-select-style races
    """
    def __init__(self, settings_pool, config):
        super().__init__(settings_pool)
        self.race_type, self.num_major_settings, self.num_minor_settings = config
        self.selected_settings = {}

    def select_random_settings(self):
        _num_major_settings = int(self.num_major_settings)
        _num_minor_settings = int(self.num_minor_settings)
        count = 0
        while count < _num_major_settings + _num_minor_settings:
            # Select from major pool
            if count < _num_major_settings:
                pool = self.settings_pool['major']
            # Select from minor pool
            else:
                pool = self.settings_pool['minor']
            setting = random.choice(list(pool))
            option = random.choice(list(pool[setting]['options']))
            if option == pool[setting]['default']:
                continue
            for key, value in pool[setting]['options'][option]['data'].items():
                self.generator_data.update({
                    key: value
                })
            self.selected_settings.update({
                pool[setting]['__setting']: pool[setting]['options'][option]['name']
            })
            pool.pop(setting)
            count += 1
            