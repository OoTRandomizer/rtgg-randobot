from asyncio import sleep
import datetime
import re
import random
from racetime_bot import RaceHandler, monitor_cmd, can_moderate, can_monitor, msg_actions


def natjoin(sequence, default):
    if len(sequence) == 0:
        return str(default)
    elif len(sequence) == 1:
        return str(sequence[0])
    elif len(sequence) == 2:
        return f'{sequence[0]} and {sequence[1]}'
    else:
        return ', '.join(sequence[:-1]) + f', and {sequence[-1]}'


def format_duration(duration):
    parts = []
    hours, duration = divmod(duration, datetime.timedelta(hours=1))
    if hours > 0:
        parts.append(f'{hours} hour{"" if hours == 1 else "s"}')
    minutes, duration = divmod(duration, datetime.timedelta(minutes=1))
    if minutes > 0:
        parts.append(f'{minutes} minute{"" if minutes == 1 else "s"}')
    if duration > datetime.timedelta():
        seconds = duration.total_seconds()
        parts.append(f'{seconds} second{"" if seconds == 1 else "s"}')
    return natjoin(parts, '0 seconds')


def parse_duration(args, default):
    if len(args) == 0:
        raise ValueError('Empty duration args')
    duration = datetime.timedelta()
    for arg in args:
        arg = arg.lower()
        while len(arg) > 0:
            match = re.match('([0-9]+)([smh:]?)', arg)
            if not match:
                raise ValueError('Unknown duration format')
            unit = {
                '': default,
                's': 'seconds',
                'm': 'minutes',
                'h': 'hours',
                ':': default
            }[match.group(2)]
            default = {
                'hours': 'minutes',
                'minutes': 'seconds',
                'seconds': 'seconds'
            }[unit]
            duration += datetime.timedelta(**{unit: float(match.group(1))})
            arg = arg[len(match.group(0)):]
    return duration

class RandoHandler(RaceHandler):
    """
    RandoBot race handler. Generates seeds, presets, and frustration.
    """
    seed_url = 'https://ootrandomizer.com/seed/get?id=%s'
    stop_at = ['cancelled', 'finished']
    max_status_checks = 50
    greetings = (
        'Let me roll a seed for you. I promise it won\'t hurt.',
        'It\'s dangerous to go alone. Take this?',
        'I promise that today\'s seed will be nice.',
        'I can roll a race seed for you. If you dare.',
        'All rolled seeds comply with the laws of thermodynamics.',
    )

    def __init__(self, zsr, midos_house, **kwargs):
        super().__init__(**kwargs)
        self.zsr = zsr
        self.midos_house = midos_house

    def _is_s7_race(self):
        if 'S7' in self.data.get('info_user'):
            return True
        return False

    async def should_stop(self):
        goal_name = self.data.get('goal', {}).get('name')
        goal_is_custom = self.data.get('goal', {}).get('custom', False)
        if goal_is_custom:
            if await self.midos_house.handles_custom_goal(goal_name):
                return True # handled by Mido (https://github.com/midoshouse/midos.house)
        else:
            if goal_name == 'Random settings league':
                return True # handled by RSLBot (https://github.com/midoshouse/midos.house)
            elif goal_name == 'Triforce Blitz':
                return True # handled by Mido (https://github.com/midoshouse/midos.house)
        return await super().should_stop()

    async def begin(self):
        """
        Send introduction messages.
        """
        if await self.should_stop():
            return
        if not self.state.get('intro_sent') and not self._race_in_progress():
            await self.send_message(
                'Welcome to OoTR! ' + random.choice(self.greetings),
                actions=[
                    msg_actions.Action(
                        label='Roll seed',
                        help_text='Create a seed using the latest release',
                        message='!seed ${preset}',
                        submit='Roll race seed',
                        survey=msg_actions.Survey(
                            msg_actions.SelectInput(
                                name='preset',
                                label='Preset',
                                options={key: value['full_name'] for key, value in self.zsr.presets.items()},
                                default='weekly',
                            ),
                        ),
                    ),
                    msg_actions.Action(
                        label='Dev seed',
                        help_text='Create a seed using the latest dev branch',
                        message='!seeddev ${preset}',
                        submit='Roll dev seed',
                        survey=msg_actions.Survey(
                            msg_actions.SelectInput(
                                name='preset',
                                label='Preset',
                                options={key: value['full_name'] for key, value in self.zsr.presets_dev.items()},
                                default='weekly',
                            ),
                        ),
                    ),
                    msg_actions.ActionLink(
                        label='Help',
                        url='https://github.com/deains/ootr-randobot/blob/master/COMMANDS.md',
                    ),
                ],
                pinned=True,
            )
            if self._is_s7_race():
                await self.send_message(
                    'If this is a draft race, use !s7 tournament for official matches or '
                    '!s7 practice for practice races.'
                )
                self.state.setdefault('draft_data', {})
            self.state['intro_sent'] = True
        if 'locked' not in self.state:
            self.state['locked'] = False
        if 'fpa' not in self.state:
            self.state['fpa'] = False

    async def end(self):
        if self.state.get('pinned_msg'):
            await self.unpin_message(self.state['pinned_msg'])

    async def chat_message(self, data):
        message = data.get('message', {})
        if (
            message.get('is_bot')
            and message.get('bot') == 'RandoBot'
            and message.get('is_pinned')
            and message.get('message_plain', '').startswith('Welcome to OoTR!')
        ):
            self.state['pinned_msg'] = message.get('id')
        return await super().chat_message(data)

    async def race_data(self, data):
        await super().race_data(data)
        if self._race_in_progress() and self.state.get('pinned_msg'):
            await self.unpin_message(self.state['pinned_msg'])
            del self.state['pinned_msg']

    @monitor_cmd
    async def ex_s7(self, args, message):
        """
        Handle !s7 commands.

        Set up room for Draft Mode.
        """
        if self._race_in_progress() or not self._is_s7_race():
            return
        elif self._is_s7_race and self.data.get('entrants_count') < 2:
            await self.send_message(
                'At least two runners must be present before enabling Draft Mode.'
            )
            return
        
        draft = self.state.get('draft_data')

        if len(args) == 1 and args[0] in ('tournament', 'practice', 'qualifier', 'cancel'):
            if args[0] in ('tournament', 'practice') and not draft.get('enabled'):
                if args[0] == 'tournament' and self.data.get('entrants_count') > 2:
                    await self.send_message(
                        'Tournament Draft Mode is only available for head-to-head matches. Please use !s7 practice instead.'
                    )
                    return
                draft.update({
                    'enabled': True,
                    'race_type': args[0]
                    })
                await self.send_message(
                    'Welcome to OoTR Draft Mode! '
                    'You can disable Draft Mode at any time with !s7 cancel.'
                ),
                await self.send_message(
                    f'You have indicated that this is a {args[0]} race.'
                )
                if draft.get('race_type') == 'tournament':
                    await self.ex_fpa(['on'], message),
                
                entrants = await self.determine_higher_seed()

                # If we can't verify qualification data, disable Draft Mode
                if len(entrants) < 2:
                    await self.send_message(
                            'Error fetching racer data. Exiting Draft Mode...'
                        ),
                    await self.ex_s7(['cancel'], message)
                await self.send_message(
                    f"{entrants[0].get('name')}, please select whether or not to ban first with !first or !second."
                )
                draft.update({
                    'racers': entrants,
                    'status': 'select_order',
                    'current_selector': None,
                    'ban_count': 0,
                    'pick_count': 0,
                    'available_settings': self.zsr.load_draft_settings(),
                    'drafted_settings': {
                        'bans': {},
                        'picks': {},
                        'data': {}
                    },
                })

            elif args[0] == 'qualifier' and not draft.get('enabled'):
                if not can_moderate(message):
                    return
                draft.update({
                    'enabled': True,
                    'race_type': args[0]
                    })
                await self.send_message(
                    f"You have indicated that this is a {args[0]} race. Race monitors, use !roll 15 minutes prior to race start for a seed."
                )
            
            elif args[0] in ('tournament', 'practice', 'qualifier') and draft.get('enabled'):
                await self.send_message(
                    'Draft Mode is already enabled.'
                )
            
            elif args[0] == 'cancel':
                if draft.get('enabled'):
                    if draft.get('race_type') == 'tournament':
                        if draft.get('status') == 'complete' and not can_moderate(message):
                            await self.send_message(
                                'Draft process has already been completed. Please contact an organizer to cancel this race.'
                            )
                            return
                        await self.ex_fpa(['off'], message),
                    await self.send_message(
                        'Draft Mode has been disabled.'
                    )
                    draft.clear()
                    return
                await self.send_message(
                    'Draft Mode is not currently enabled.'
                )

    async def ex_first(self, args, message):
        draft = self.state.get('draft_data')
        if self._race_in_progress() or not draft.get('status') == 'select_order':
            return
        
        reply_to = message.get('user', {}).get('name')
        racer = draft.get('racers')

        # Compare sender to draft_data 
        if not racer[0].get('name') == reply_to:
            return
        draft.update({'current_selector': racer[0].get('name')})
        await self.send_message(
            f'{reply_to}, please prevent a major setting from changing with !ban <setting>.'
        )
        await self.send_message(
            'Use !settings to view a list of available options.'
        )
        draft.update({'status': 'major_ban'})

    async def ex_second(self, args, message):
        draft = self.state.get('draft_data')
        if self._race_in_progress() or not draft.get('status') == 'select_order':
            return
        
        reply_to = message.get('user', {}).get('name')
        racer = draft.get('racers')

        # Compare sender to draft_data 
        if not racer[0].get('name') == reply_to:
            return
        draft.update({'current_selector': racer[1].get('name')})
        await self.send_message(
            f"{draft.get('current_selector')}, please prevent a major setting from changing with !ban <setting>."
        )
        await self.send_message(
            'Use !settings to view a list of available options.'
        )
        draft.update({'status': 'major_ban'})
            
    async def ex_ban(self, args, message):
        draft = self.state.get('draft_data')
        if self._race_in_progress() or draft.get('status') != 'major_ban':
            return
        
        reply_to = message.get('user', {}).get('name')
        racer = draft.get('racers')

        if reply_to == draft.get('current_selector'):
            if len(args) == 1 and args[0] in draft.get('available_settings').get('major').keys():
                settings = draft.get('available_settings').get('major').get(args[0])
                await self.send_message(
                    f'{args[0]} will be forced to "{list(settings.keys())[0]}".'
                )
                draft.get('drafted_settings').get('bans').update({args[0]: list(settings.keys())[0]})
                draft.get('drafted_settings').get('data').update(list(settings.values())[0])
                draft.get('available_settings').get('major').pop(args[0])
                draft['ban_count'] += 1
                if reply_to == racer[0].get('name'):
                    draft.update({'current_selector': racer[1].get('name')})
                elif reply_to == racer[1].get('name'):
                    draft.update({'current_selector': racer[0].get('name')})
                if draft.get('ban_count') == 2:
                    draft.update({'status': 'major_pick'})
                    await self.send_message(
                            'All bans have been recorded.'
                        ),
                    await self.send_message(
                            f"{draft.get('current_selector')}, please modify a major setting with !pick <setting> <value>."
                        )
                    await self.send_message(
                        'Use !settings to view a list of available options.'
                    )
                    return
                await self.send_message(
                    f"{draft.get('current_selector')}, please prevent a major setting from changing with !ban <setting>."
                )
                await self.send_message(
                    'Use !settings to view a list of available options.'
                )

    async def ex_pick(self, args, message):
        draft = self.state.get('draft_data')
        if self._race_in_progress() or not draft.get('enabled') or not draft.get('status') in ['major_pick', 'minor_pick']:
            return
        elif len(args) < 2:
            await self.send_message(
                'Invalid format. Please use !pick <setting> <value>.'
            )
            return

        reply_to = message.get('user', {}).get('name')
        racer = draft.get('racers')

        if reply_to == draft.get('current_selector'):
            if draft.get('status') == 'major_pick':
                if len(args) == 2 and args[0] in draft.get('available_settings').get('minor').keys():
                    await self.send_message(
                        'Invalid pool. Use !settings to view available options.'
                    )
                    return
                elif len(args) == 2 and args[0] in draft.get('available_settings').get('major').keys() \
                and args[1] in draft.get('available_settings').get('major').get(args[0]).keys():
                    settings = draft.get('available_settings').get('major').get(args[0])
                    await self.send_message(
                        f'{reply_to} has elected to set "{args[0]}" to "{args[1]}".'
                    )
                    draft.get('drafted_settings').get('picks').update({args[0]: args[1]})
                    draft.get('drafted_settings').get('data').update({
                        setting for setting in settings.get(args[1]).items()
                    })
                    draft.get('available_settings').get('major').pop(args[0])
                    draft['pick_count'] += 1
                    if draft.get('pick_count') == 2:
                        draft.update({
                            'status': 'minor_pick',
                            'current_selector': racer[1].get('name')
                        })
                        await self.send_message(
                            f"{draft.get('current_selector')}, please modify a minor setting with !pick <setting> <value>."
                        )
                        await self.send_message(
                            'Use !settings to view a list of available options.'
                        )
                        return
                    if reply_to == racer[0].get('name'):
                        draft.update({'current_selector': racer[1].get('name')})
                    elif reply_to == racer[1].get('name'):
                        draft.update({'current_selector': racer[0].get('name')})
                    await self.send_message(
                        f"{draft.get('current_selector')}, please modify a major setting with !pick <setting> <value>."
                    )
                    await self.send_message(
                        'Use !settings to view a list of available options.'
                    )
                    return
                await self.send_message(
                    f'Invalid option. Use !settings to view available options.'
                )
            elif draft.get('status') == 'minor_pick':
                if len(args) == 2 and args[0] in draft.get('available_settings').get('major').keys():
                    await self.send_message(
                        'Invalid pool. Use !settings to view available options.'
                    )
                    return
                elif len(args) == 2 and args[0] in draft.get('available_settings').get('minor').keys() \
                and args[1] in draft.get('available_settings').get('minor').get(args[0]).keys():
                    settings = draft.get('available_settings').get('minor').get(args[0])
                    await self.send_message(
                        f'{args[0]} will be set to "{args[1]}".'
                    )
                    draft.get('drafted_settings').get('picks').update({args[0]: args[1]})
                    draft.get('drafted_settings').get('data').update({
                        setting for setting in settings.get(args[1]).items()
                    })
                    draft.get('available_settings').get('minor').pop(args[0])
                    draft['pick_count'] += 1
                    if draft.get('pick_count') == 4:
                        draft.update({
                            'status': 'complete',
                            'current_selector': None
                        })
                        await self.send_message(
                            'All picks have been recorded.'
                        )
                        await self.send_message(
                            'Race monitors may roll a seed with the drafted settings using !roll. '
                            'Use !settings to view what was selected.'
                        )
                        return
                    if reply_to == racer[0].get('name'):
                        draft.update({'current_selector': racer[1].get('name')})
                    elif reply_to == racer[1].get('name'):
                        draft.update({'current_selector': racer[0].get('name')})
                    await self.send_message(
                        f"{draft.get('current_selector')}, please modify a minor setting with !pick <setting> <value>."
                    )
                    await self.send_message(
                        'Use !settings to view a list of available options.'
                    )
                    return
                await self.send_message(
                    f'Invalid pool. Use !settings to view available options.'
                )

    async def ex_settings(self, args, message):
        draft = self.state.get('draft_data')
        if self._race_in_progress() or not draft.get('status') in ['major_ban', 'major_pick', 'minor_pick', 'complete']:
            return
        if draft.get('status') in ['major_ban', 'major_pick']:
            if len(args) == 0:
                await self.send_message(
                    'The following settings are available: '
                    f"{' | '.join(draft.get('available_settings').get('major').keys())}"
                )
                if draft.get('status') == 'major_ban':
                    await self.send_message(
                        'Use !settings <setting> to view its default value.'
                    )
                    return
                await self.send_message(
                    'Use !settings <setting> to view its available values.'
                )
                
            elif len(args) == 1 and args[0] in draft.get('available_settings').get('major').keys():
                setting = draft.get('available_settings').get('major').get(args[0])
                if draft.get('status') == 'major_ban':
                    await self.send_message(
                        f'The default value for "{args[0]}" is "{list(setting.keys())[0]}".'
                    )
                    return
                await self.send_message(
                    f'Available values for "{args[0]}": {", ".join(value for value in setting.keys())}'
                )
        elif draft.get('status') == 'minor_pick':
            if len(args) == 0:
                await self.send_message(
                    'The following settings are available: '
                    f"{' | '.join(draft.get('available_settings').get('minor').keys())}"
                )
                await self.send_message(
                    'Use !settings <setting> to view its available values.'
                )
            elif len(args) == 1 and args[0] in draft.get('available_settings').get('minor').keys():
                setting = draft.get('available_settings').get('minor').get(args[0])
                await self.send_message(
                    f'Available values for "{args[0]}": {", ".join(value for value in setting.keys())}'
                )

    @monitor_cmd
    async def ex_lock(self, args, message):
        """
        Handle !lock commands.

        Prevent seed rolling unless user is a race monitor.
        """
        if self.state.get('draft_data').get('enabled'):
            await self.send_message(
                'Sorry, this command is disabled for Draft Mode.'
            )
            return
        self.state['locked'] = True
        await self.send_message(
            'Lock initiated. I will now only roll seeds for race monitors.'
        )

    @monitor_cmd
    async def ex_unlock(self, args, message):
        """
        Handle !unlock commands.

        Remove lock preventing seed rolling unless user is a race monitor.
        """
        if self._race_in_progress():
            return
        elif self.state.get('draft_data').get('enabled'):
            await self.send_message(
                'Sorry, this command is disabled for Draft Mode.'
            )
            return
        self.state['locked'] = False
        await self.send_message(
            'Lock released. Anyone may now roll a seed.'
        )

    async def ex_seed(self, args, message):
        """
        Handle !seed commands.
        """
        if self._race_in_progress():
            return
        elif self.state.get('draft_data').get('enabled'):
            await self.send_message(
                'Sorry, this command is disabled for Draft Mode.'
            )
            return
        await self.roll_and_send(args, message, encrypt=True, dev=False)

    async def ex_seeddev(self, args, message):
        """
        Handle !seeddev commands.
        """
        if self._race_in_progress():
            return
        elif self.state.get('draft_data').get('enabled'):
            await self.send_message(
                'Sorry, this command is disabled for Draft Mode.'
            )
            return
        await self.roll_and_send(args, message, encrypt=True, dev=True)

    async def ex_spoilerseed(self, args, message):
        """
        Handle !spoilerseed commands.
        """
        if self._race_in_progress():
            return
        elif self.state.get('draft_data').get('enabled'):
            await self.send_message(
                'Sorry, this command is disabled for Draft Mode.'
            )
            return
        await self.roll_and_send(args, message, encrypt=False, dev=False)

    async def ex_presets(self, args, message):
        """
        Handle !presets commands.
        """
        if self._race_in_progress():
            return
        elif self.state.get('draft_data').get('enabled'):
            await self.send_message(
                'Sorry, this command is disabled for Draft Mode.'
            )
            return
        await self.send_presets(False)

    async def ex_presetsdev(self, args, message):
        """
        Handle !presetsdev commands.
        """
        if self._race_in_progress():
            return
        elif self.state.get('draft_data').get('enabled'):
            await self.send_message(
                'Sorry, this command is disabled for Draft Mode.'
            )
            return
        await self.send_presets(True)

    async def ex_fpa(self, args, message):
        if len(args) == 1 and args[0] in ('on', 'off'):
            if not can_monitor(message):
                resp = 'Sorry %(reply_to)s, only race monitors can do that.'
            elif args[0] == 'on':
                if self.state['fpa']:
                    resp = 'Fair play agreement is already activated.'
                else:
                    self.state['fpa'] = True
                    resp = (
                        'Fair play agreement is now active. @entrants may '
                        'use the !fpa command during the race to notify of a '
                        'crash. Race monitors should enable notifications '
                        'using the bell 🔔 icon below chat.'
                    )
            else:  # args[0] == 'off'
                if not self.state['fpa']:
                    resp = 'Fair play agreement is not active.'
                else:
                    self.state['fpa'] = False
                    resp = 'Fair play agreement is now deactivated.'
        elif self.state['fpa']:
            if self._race_in_progress():
                resp = '@everyone FPA has been invoked by @%(reply_to)s.'
            else:
                resp = 'FPA cannot be invoked before the race starts.'
        else:
            resp = (
                'Fair play agreement is not active. Race monitors may enable '
                'FPA for this race with !fpa on'
            )
        if resp:
            reply_to = message.get('user', {}).get('name', 'friend')
            await self.send_message(resp % {'reply_to': reply_to})

    async def roll_and_send(self, args, message, encrypt, dev):
        """
        Read an incoming !seed, !seeddev or !race command, and generate a new seed if
        valid.
        """
        reply_to = message.get('user', {}).get('name')

        if self.state.get('locked') and not can_monitor(message):
            await self.send_message(
                'Sorry %(reply_to)s, seed rolling is locked. Only race '
                'monitors may roll a seed for this race.'
                % {'reply_to': reply_to or 'friend'}
            )
            return
        if self.state.get('seed_id') and not can_moderate(message):
            await self.send_message(
                'Well excuuuuuse me princess, but I already rolled a seed. '
                'Don\'t get greedy!'
            )
            return

        await self.roll(
            preset=args[0] if args else 'weekly',
            encrypt=encrypt,
            dev=dev,
            reply_to=reply_to,
        )

    async def roll(self, preset, encrypt, dev, reply_to):
        """
        Generate a seed and send it to the race room.
        """
        if (dev and preset not in self.zsr.presets_dev) or (not dev and preset not in self.zsr.presets):
            res_cmd = '!presetsdev' if dev else '!presets'
            await self.send_message(
                'Sorry %(reply_to)s, I don\'t recognise that preset. Use '
                '%(res_cmd)s to see what is available.'
                % {'res_cmd': res_cmd, 'reply_to': reply_to or 'friend'}
            )
            return

        seed_id, seed_uri = self.zsr.roll_seed(preset, encrypt, dev)

        await self.send_message(
            '%(reply_to)s, here is your seed: %(seed_uri)s'
            % {'reply_to': reply_to or 'Okay', 'seed_uri': seed_uri}
        )
        await self.set_bot_raceinfo(seed_uri)
        if self.state.get('pinned_msg'):
            await self.unpin_message(self.state['pinned_msg'])
            del self.state['pinned_msg']

        self.state['seed_id'] = seed_id
        self.state['status_checks'] = 0

        await self.check_seed_status()

    async def check_seed_status(self):
        await sleep(1)
        status = self.zsr.get_status(self.state['seed_id'])
        if status == 0:
            self.state['status_checks'] += 1
            if self.state['status_checks'] < self.max_status_checks:
                await self.check_seed_status()
        elif status == 1:
            await self.load_seed_hash()
        elif status >= 2:
            self.state['seed_id'] = None
            await self.send_message(
                'Sorry, but it looks like the seed failed to generate. Use '
                '!seed to try again.'
            )

    async def load_seed_hash(self):
        seed_hash = self.zsr.get_hash(self.state['seed_id'])
        await self.set_bot_raceinfo('%(seed_hash)s\n%(seed_url)s' % {
            'seed_hash': seed_hash,
            'seed_url': self.seed_url % self.state['seed_id'],
        })

    async def send_presets(self, dev):
        """
        Send a list of known presets to the race room.
        """
        await self.send_message('Available presets:')
        if dev:
            for name, preset in self.zsr.presets_dev.items():
                await self.send_message('%s – %s' % (name, preset['full_name']))
        else:
            for name, preset in self.zsr.presets.items():
                await self.send_message('%s – %s' % (name, preset['full_name']))

    async def determine_higher_seed(self):
        entrants = []
        if self.state.get('draft_data').get('race_type') == 'tournament':
            placements = self.zsr.load_qualifier_placements()
            for entrant in self.data.get('entrants'):
                for place in placements:
                    if entrant.get('user').get('name') == place.get('name'):
                        entrants.append({'name': place.get('name'), 'rank': place.get('place')})
            return sorted(entrants, key=lambda entrant: entrant.get('rank'))    
        elif self.state.get('draft_data').get('race_type') == 'practice':
            for entrant in self.data.get('entrants'):
                entrants.append({'name': entrant.get('user').get('name'), 'score': (entrant.get('score') if entrant.get('score') else 0)})
            return sorted(entrants, key=lambda entrant: entrant.get('score'), reverse=True)

    def _race_in_progress(self):
        return self.data.get('status').get('value') in ('pending', 'in_progress')
