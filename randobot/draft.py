import os
import json
from copy import deepcopy


script_path = os.path.dirname(os.path.abspath(__file__))
settings_path = os.path.join(script_path, 'settings.json')
with open(settings_path, 'r') as f:
    settings_pool = json.load(f)


def configure_draft(entrants, presets, args):
    if len(args) < 5:
        return (None, 'Invalid syntax. Please use the buttons for assistance.')

    if check_for_duplicates(args[:2]):
        return (None, 'You may not assign the same drafter more than once. Please try again.')
    
    drafters = get_drafters(entrants, args[:2])
    if len(drafters) < 2:
        return (None, 'Unable to locate all drafters in the room. Please try again.')
    
    num_bans, num_picks = convert_to_int(args[2], args[3])
    if not isinstance(num_bans, int) or not isinstance(num_picks, int):
        return (None, 'Only integer values may be given for ban/pick count. Please try again.')
    
    base_settings = get_base_settings(args[4], presets)
    if not base_settings:
        return (None, 'Invalid preset given for base settings. Valid presets are: ' + ', '.join(preset for preset in presets))

    if '--sort' in args and drafters:
        drafters = sort_by_rtgg_score(drafters)
    if '--allow_default_picks' not in args:
        filter_available_settings(base_settings, settings_pool)
    
    return ([drafters, num_bans, num_picks, base_settings, settings_pool], 'Configuration successful. Advancing state...')


def get_drafters(entrants, drafters):
    valid_drafters = []

    for entrant in entrants:
        for drafter in drafters:
            if entrant['user']['full_name'].lower() == drafter:
                valid_drafters.append({
                    'user': entrant['user'],
                    'score': entrant['score'] if entrant.get('score') else 0
                })

    return valid_drafters


def check_for_duplicates(lst):
    for item in lst:
        if lst.count(item) > 1:
            return True
    return False


def sort_by_rtgg_score(drafters):
    return sorted(drafters, key=lambda drafter: drafter['score'], reverse=True)


def get_base_settings(preset_alias, presets):
    try:
        settings = presets[preset_alias]['settings']
    except:
        return
    return settings


def convert_to_int(num_bans, num_picks):
    try:
        num_bans, num_picks = int(num_bans), int(num_picks)
    except:
        return (None, None)
    
    return (num_bans, num_picks)


def filter_available_settings(base_settings, settings_pool):
    settings_pool_copy = deepcopy(settings_pool)

    for setting in settings_pool_copy:
        options = settings_pool_copy[setting]['options']
        for option in options:
            gui_settings = options[option]['gui_setting']
            for key, value in gui_settings.items():
                if (key, value) in base_settings.items():
                    settings_pool[setting]['options'].pop(option)


def patch_settings():
    pass


class DraftData:
    def __init__(self, drafters, num_bans, num_picks, base_settings, settings_pool):
        self.drafters = drafters
        self.num_bans = num_bans
        self.num_picks = num_picks
        self.base_settings = base_settings
        self.settings_pool = settings_pool
        self.bans = {}
        self.picks = {}
        self.state = 'awaiting_bans'
    
    def ban_setting(self):
        pass

    def pick_setting(self):
        pass
