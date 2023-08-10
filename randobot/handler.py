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

    def _is_tournament_match(self):
        if 'S7 Tournament' in self.data.get('info_user'):
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
            if self._is_tournament_match():
                await self.send_message(
                    'Tournament match detected. Use !draft on to enable Draft Mode.'
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

    async def ex_draft(self, args, message):
        """
        Handle !draft commands.

        Set up room for Draft Mode.
        """
        if self._race_in_progress() or not self._is_tournament_match():
            return
        elif self._is_tournament_match and self.data.get('entrants_count') < 2:
            await self.send_message(
                'Both runners must be present before enabling Draft Mode.'
            )
            return
        elif self._is_tournament_match and self.data.get('entrants_count') > 2:
            await self.send_message(
                'Draft Mode is only available for head-to-head matches.'
            )
            return
        if len(args) == 1 and args[0] in ('on', 'off'):
            if args[0] == 'on' and not self.state.get('draft_data').get('enabled'):
                self.state.get('draft_data').update({'enabled': True})
                await gather(
                    self.send_message(
                        'Welcome to OoTR Draft Mode! '
                        'You can disable Draft Mode at any time with !draft off.'
                    ),
                    self.ex_fpa(args, message)
                )
                
                entrants = await self._is_qualified()
                # If we can't verify qualification data, disable Draft Mode
                if len(entrants) < 2:
                    await gather(
                        self.send_message(
                            'Error fetching runner data. Please contact a tournament organizer.'
                        ),
                        self.ex_draft(['off'], message)
                    )
                
                await self.send_message(
                    f"{entrants[0].get('name')}, please select whether or not to ban first with !first or !second."
                )
                self.state.get('draft_data').update({
                    'racers': entrants,
                    'pick_order': False,
                    'num_bans': 0,
                    'num_picks': 0,
                    'confirmed': False,
                    'settings': {
                        'bans': []
                    },
                    'available_settings': self.zsr.load_draftable_settings()
                })
            
            elif args[0] == 'on' and self.state.get('draft_data').get('enabled'):
                await self.send_message(
                    'Draft Mode is already enabled.'
                )
                return
            
            elif args[0] == 'off':
                if self.state.get('draft_data').get('enabled'):
                    await gather(
                        self.ex_fpa(args, message),
                        self.send_message('Draft Mode has been disabled.')
                    )
                    self.state.get('draft_data').clear()
                    return
                await self.send_message(
                    'Draft Mode is not currently enabled.'
                )

    async def ex_first(self, args, message):
        if self._race_in_progress() or not self.state.get('draft_data').get('enabled') or self.state.get('draft_data').get('pick_order'):
            return
        
        # Compare sender to draft_data 
        user = message.get('user', {}).get('name')
        racer = self.state.get('draft_data').get('racers')
        if not racer[0].get('name') == user:
            return
        racer[0].update({'first_pick': True})
        await self.send_message(
            f'{user}, please select a setting to ban with !ban <setting>. '
            'You may use !settings to view a list of available settings to ban'
        )
        self.state.get('draft_data').update({'pick_order': True})

    async def ex_second(self, args, message):
        if self._race_in_progress() or not self.state.get('draft_data').get('enabled') or self.state.get('draft_data').get('draft_pick_order'):
            return
        
        # Compare sender to draft_data 
        user = message.get('user', {}).get('name')
        racer = self.state.get('draft_data').get('racers')
        if not racer[0].get('name') == user:
            return
        racer[1].update({'first_pick': True})
        await self.send_message(
            f"{racer[1].get('name')}, please select a setting to ban with !ban <setting>. "
            'You may use !settings to view a list of available settings to ban'
        )
        self.state.get('draft_data').update({'pick_order': True})
            
    async def ex_ban(self, args, message):
        if self._race_in_progress() or not self.state.get('draft_data').get('enabled') or not self.state.get('draft_data').get('pick_order'):
            return
        elif self.state.get('draft_data').get('num_bans') >= 4:
            return
       
        user = message.get('user', {}).get('name')
        racer = self.state.get('draft_data').get('racers')

        if user == racer[0].get('name') and 'first_pick' in racer[0].keys():
            if not self.state.get('draft_data').get('num_bans') % 2 == 0:
                return
            if len(args) == 1 and args[0] in self.state.get('draft_data').get('available_settings'):
                await self.send_message(
                    f"{racer[0].get('name')} has elected to ban {args[0]}"
                )
                self.state.get('draft_data').get('settings').get('bans').append(args[0])
                self.state.get('draft_data').get('available_settings').remove(args[0])
                self.state['draft_data']['num_bans'] += 1
        elif user == racer[0].get('name') and 'first_pick' not in racer[0].keys():
            if self.state.get('draft_data').get('num_bans') % 2 == 0:
                return
            if len(args) == 1 and args[0] in self.state.get('draft_data').get('available_settings'):
                await self.send_message(
                    f"{racer[0].get('name')} has elected to ban {args[0]}"
                )
                self.state.get('draft_data').get('settings').get('bans').append(args[0])
                self.state.get('draft_data').get('available_settings').remove(args[0])
                self.state['draft_data']['num_bans'] += 1
        elif user == racer[1].get('name') and 'first_pick' in racer[1].keys():
            if not self.state.get('draft_data').get('num_bans') % 2 == 0:
                return
            if len(args) == 1 and args[0] in self.state.get('draft_data').get('available_settings'):
                await self.send_message(
                    f"{racer[1].get('name')} has elected to ban {args[0]}"
                )
                self.state.get('draft_data').get('settings').get('bans').append(args[0])
                self.state.get('draft_data').get('available_settings').remove(args[0])
                self.state['draft_data']['num_bans'] += 1
        elif user == racer[1].get('name') and 'first_pick' not in racer[1].keys():
            if self.state.get('draft_data').get('num_bans') % 2 == 0:
                return
            if len(args) == 1 and args[0] in self.state.get('draft_data').get('available_settings'):
                await self.send_message(
                    f"{racer[1].get('name')} has elected to ban {args[0]}"
                )
                self.state.get('draft_data').get('settings').get('bans').append(args[0])
                self.state.get('draft_data').get('available_settings').remove(args[0])
                self.state['draft_data']['num_bans'] += 1

    async def ex_pick(self, args, message):
        pass

    async def ex_settings(self, args, message):
        if self._race_in_progress() or not self.state.get('draft_data').get('pick_order'):
            return
        await self.send_message(
            'The following settings are available to modify: '
            f"{', '.join(self.state.get('draft_data').get('available_settings'))}"
        )
        print(self.state.get('draft_data'))

    async def ex_confirm(self, args, message):
        pass

    @monitor_cmd
    async def ex_lock(self, args, message):
        """
        Handle !lock commands.

        Prevent seed rolling unless user is a race monitor.
        """
        if self.state.get('draft_data').get('state'):
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
        elif self.state.get('draft_data').get('state'):
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
        elif self.state.get('draft_data').get('state'):
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
        elif self.state.get('draft_data').get('state'):
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
        elif self.state.get('draft_data').get('state'):
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
        elif self.state.get('draft_data').get('state'):
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
        elif self.state.get('draft_data').get('state'):
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

    async def _is_qualified(self):
        entrants = []
        placements = self.zsr.load_qualifier_placements()
        for entrant in self.data.get('entrants'):
            for place in placements:
                if entrant['user']['name'] == place['name']:
                    entrants.append({'name': place['name'], 'rank': place['place']})
        return sorted(entrants, key=lambda entrant: entrant['rank'])

    def _race_in_progress(self):
        return self.data.get('status').get('value') in ('pending', 'in_progress')
