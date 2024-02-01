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
    def __init__(self, settings_pool, args):
        super().__init__(settings_pool)
        self.race_type, *self.draftees, self.is_tournament_race, self.bans_each, self.major_picks_each, self.minor_picks_each = args
        self.player_bans = []
        self.player_picks = []
        self.current_selector = None

    def determine_higher_seed(self, entrants, qual_data):
        _draftees = []
        # Sort by qualifier placement
        if self.is_tournament_race:
            for draftee in self.draftees:
                for racer in qual_data:
                    if draftee == racer['name'].lower():
                        _draftees.append({'name': draftee.capitalize(), 'place': racer['place']})
            self.draftees = sorted(_draftees, key=lambda draftee: draftee['place'])
        # Sort by racetime.gg points
        else:
            for draftee in self.draftees:
                for entrant in entrants:
                    if draftee == entrant['user']['name'].lower():
                        _draftees.append({'name': draftee.capitalize(), 'score': entrant['score'] if entrant.get('score') else 0})
            self.draftees = sorted(_draftees, key=lambda draftee: draftee['score'], reverse=True)

    def assign_draft_order(self, args, message):
        if len(self.draftees) == 2:
            user = message.get('user', {}).get('name')
            if user == self.draftees[0]['name']:
                if message.get('message_plain', '').startswith('!first'):
                    self.current_selector = self.draftees[0]['name']
                elif message.get('message_plain', '').startswith('!second'):
                    self.current_selector = self.draftees[1]['name']

    def skip_ban(self, message):
        user = message.get('user', {}).get('name')
        _draftees = list(enumerate(self.draftees))
        for index, draftee in _draftees:
            if user == draftee['name'] and user == self.current_selector:
                self.player_bans.append({
                    user: 'Skipped'
                })
                self.current_selector = self.draftees[index + 1 if index < len(_draftees) - 1 else 0]['name']
                if len(self.player_bans) >= int(self.bans_each) * len(self.draftees):
                    return
                return True

    def ban_setting(self, args, message):
        user = message.get('user', {}).get('name')
        pool = self.settings_pool['major'] | self.settings_pool['minor']
        _draftees = list(enumerate(self.draftees))
        for index, draftee in _draftees:
            if user == draftee['name'] and user == self.current_selector:
                if len(args) == 1 and args[0] in pool:
                    self.player_bans.append({
                        user: pool[args[0]]['_setting']
                    })
                    pool.pop(args[0])
                    self.current_selector = self.draftees[index + 1 if index < len(_draftees) - 1 else 0]['name']
                    if len(self.player_bans) >= int(self.bans_each) * len(self.draftees):
                        return
                    return True
            return

    def pick_setting(self, args, message):
        pass

    def send_available_settings(self, state):
        if state == 'player_bans':
            pool = self.settings_pool['major'] | self.settings_pool['minor']
            return {
                f"{setting}": f"{pool[setting]['_setting']}: {pool[setting]['options'][pool[setting]['default']]['name']}"
                for setting in pool
            }
        elif state == 'player_picks':
            if len(self.player_picks) < int(self.major_picks_each):
                pool = self.settings_pool['major']
            else:
                pool = self.settings_pool['minor']
            return {
                f"{setting} {option}": f"{pool[setting]['_setting']}: {pool[setting]['options'][option]['name']}"
                for setting in pool for option in pool[setting]['options'] if option != pool[setting]['default']
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
            if count < _num_major_settings:
                pool = self.settings_pool['major']
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
                pool[setting]['_setting']: pool[setting]['options'][option]['name']
            })
            pool.pop(setting)
            count += 1
            