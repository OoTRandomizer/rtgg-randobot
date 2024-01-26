import random
from copy import deepcopy

class Handler:
    """
    Base class for handling draft data
    """
    def __init__(self, settings_pool):
        self.major_settings_pool = settings_pool['major']
        self.minor_settings_pool = settings_pool['minor']
        self.generator_data = {}

    def handle_conditional_settings(self):
        settings = self.zsr.presets.get('s7').get('settings')
        preset = deepcopy(settings)
        picks = self.state.get('draft_data').get('drafted_settings').get('picks')
        data = self.state.get('draft_data').get('drafted_settings').get('data')

        # Handled seperated tokensanity settings
        if 'ow_tokens' in picks.keys() and 'dungeon_tokens' in picks.keys():
            data.update({'tokensanity': 'all'})

        preset.update(data)

        # If dungeon er is on, add logic_dc_scarecrow_gs to trick list
        for setting in data.keys():
            if setting == 'shuffle_dungeon_entrances' and data[setting] == 'simple':
                preset['allowed_tricks'].append('logic_dc_scarecrow_gs')
        return preset
    
class PlayerDraft(Handler):
    """
    Class for handling draft-style races
    """
    def __init__(self, entrants, settings_pool, config, qual_data):
        super().__init__(settings_pool)
        _, *self.draftees, self.is_tournament_race, self.max_bans, self.max_picks = config
        self.complete_settings_pool = self.major_settings_pool | self.minor_settings_pool
        self.ban_count = 0
        self.pick_count = 0
        self.player_bans = {}
        self.player_picks = {}
        self.current_selector = None
        self.determine_higher_seed(entrants, qual_data)

    def determine_higher_seed(self, entrants, qual_data):
        _draftees = []
        # Sort by qualifier placement
        if self.is_tournament_race:
            placements = qual_data
            for draftee in self.draftees:
                for place in placements:
                    if draftee == place['name'].lower():
                        _draftees.append({'name': draftee, 'place': place['place']})
            self.draftees = sorted(_draftees, key=lambda draftee: draftee['place'])
        # Sort by racetime.gg points
        else:
            for draftee in self.draftees:
                for entrant in entrants:
                    if draftee == entrant['user']['name'].lower():
                        _draftees.append({'name': draftee, 'score': entrant['score'] if entrant.get('score') else 0})
            self.draftees = sorted(_draftees, key=lambda draftee: draftee['score'], reverse=True)

    def assign_draft_order(self, reply_to):
        pass

    def skip_ban(self):
        pass

    def ban_setting(self):
        pass

    def pick_setting(self):
        pass

    def send_available_settings(self):
        pass

class RandomDraft(Handler):
    """
    Class for handling auto-select-style races
    """
    def __init__(self, settings_pool, config):
        super().__init__(settings_pool)
        _, self.is_tournament_race, self.num_settings = config
        self.selected_settings = {}

    def select_random_settings(self):
        _num_settings = int(self.num_settings)
        _generator_data = deepcopy(self.generator_data)
        count = 0
        while count < _num_settings:
            # Select from major pool
            if count < (_num_settings / 2):
                pool = deepcopy(self.major_settings_pool)
            # Select from minor pool
            else:
                pool = deepcopy(self.minor_settings_pool)
            name = random.choice(list(pool))
            setting = random.choice(list(pool[name]))
            for key, value in pool[name][setting].items():
                _generator_data.update({
                    key: value
                })
            pool.pop(name)
            self.selected_settings.update({
                name: setting
            })
            count += 1
