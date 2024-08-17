from asyncio import sleep
from copy import deepcopy
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

    async def should_stop(self):
        if self.data.get('opened_by') is None:
            # Ignore all rooms opened by bots, allowing Mido (https://github.com/midoshouse/midos.house) to open rooms in official goals.
            # This is okay because RandoBot does not open any rooms.
            return True
        goal_name = self.data.get('goal', {}).get('name')
        goal_is_custom = self.data.get('goal', {}).get('custom', False)
        if goal_is_custom:
            if await self.midos_house.handles_custom_goal(goal_name):
                return True # handled by Mido
        else:
            if goal_name in ('Random settings league', 'Triforce Blitz'):
                return True # handled by Mido
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
                        message='!seed ${preset} ${--withpassword}',
                        submit='Roll race seed',
                        survey=msg_actions.Survey(
                            msg_actions.SelectInput(
                                name='preset',
                                label='Preset',
                                options={key: value['full_name'] for key, value in self.zsr.presets.items()},
                                default='weekly',
                            ),
                            msg_actions.BoolInput(
                                name='--withpassword',
                                label='Password',
                                help_text='Locks file creation behind a 5 ocarina notes password provided at countdown start',
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
                            msg_actions.BoolInput(
                                name='--withpassword',
                                label='Password',
                                help_text='Locks file creation behind a 5 ocarina notes password provided at countdown start',
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
            self.state.setdefault('draft_data', {})
            self.state['intro_sent'] = True
        if 'locked' not in self.state:
            self.state['locked'] = False
        if 'fpa' not in self.state:
            self.state['fpa'] = False
        if 'password_active' not in self.state:
            self.state['password_active'] = False
        if 'password_published' not in self.state:
            self.state['password_published'] = False
        if 'password_retry' not in self.state:
            self.state['password_retry'] = 0


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
        if self._race_pending() and self.state.get('password_active') and not self.state['password_published']:
            await self.set_bot_raceinfo('%(seed_hash)s | Password: %(seed_password)s\n%(seed_url)s' % {
                'seed_password': self.state['seed_password'],
                'seed_hash': self.state['seed_hash'],
                'seed_url': self.seed_url % self.state['seed_id'],
            })
            await self.send_message(
                    'This seed is password protected. To start a file, enter this password on the file select screen:\n'
                    '%(seed_password)s\nYou are allowed to enter the password before the race starts.'
                    % {'seed_password': self.state['seed_password']}
                )
            self.state['password_published'] = True
        if self._race_in_progress() and self.state.get('pinned_msg'):
            await self.unpin_message(self.state['pinned_msg'])
            del self.state['pinned_msg']

    @monitor_cmd
    async def ex_s7(self, args, message):
        """
        Handle !s7 commands.

        Set up room for Draft Mode.
        """
        if self._race_in_progress():
            return
        
        draft = self.state.get('draft_data')

        # Handle valid arguments.
        if len(args) == 0:
            await self.send_message(
                'Invalid format. Use !s7 <tournament|draft|random|cancel>.'
            )
            return
        elif len(args) == 1 and args[0] in ('tournament', 'draft', 'random', 'qualifier', 'cancel'):
            if args[0] in ('tournament', 'draft', 'random') and not draft.get('enabled'):
                # Requires more than one user to enable Draft Mode.
                if self.data.get('entrants_count') < 2:
                    await self.send_message(
                        'At least two runners must be present before enabling Draft Mode.'
                    )
                    return
                draft.update({
                    'enabled': True,
                    'race_type': args[0]
                    })
                await self.send_message(
                    'Welcome to OoTR Draft Mode! '
                    'You can disable Draft Mode with !s7 cancel.'
                ),
                await self.send_message(
                    f'This is a "{args[0]}" race.'
                )
                # Always enable FPA for official matches.
                if draft.get('race_type') == 'tournament':
                    await self.ex_fpa(['on'], message)
                # Add necessary property for random practice races and exit draft function
                elif draft.get('race_type') == 'random':
                    draft.update({
                        'auto_draft': True,
                        'status': 'seed_rolled',
                        'available_settings': self.zsr.load_available_settings(),
                        'drafted_settings': {
                            'picks': {},
                            'data': {}
                        }
                    })
                    await self.send_message(
                        f'Use !seed 15 minutes prior to race start for a seed.'
                    )
                    return
                    
                entrants = await self.determine_higher_seed()

                # If we can't seed players, exit Draft Mode.
                if len(entrants) < 2:
                    await self.send_message(
                            'Error fetching racer data. Exiting Draft Mode...'
                        ),
                    await self.ex_s7(['cancel'], message)
                    return
                await self.send_message(
                    f"{entrants[0].get('name')}, please select whether or not to ban first with !first or !second."
                )
                draft.update({
                    'racers': entrants,
                    'status': 'select_order',
                    'current_selector': None,
                    'ban_count': 0,
                    'pick_count': 0,
                    'available_settings': self.zsr.load_available_settings(),
                    'drafted_settings': {
                        'picks': {},
                        'data': {}
                    },
                })
            elif args[0] == 'qualifier' and not draft.get('enabled'):
                # Restrict qualifier argument to Race Moderators.
                if not can_moderate(message):
                    return
                draft.update({
                    'enabled': True,
                    'race_type': args[0],
                    'status': 'seed_rolled',
                    'available_settings': self.zsr.load_available_settings(),
                    'drafted_settings': {
                        'picks': {},
                        'data': {}
                    }
                })
                await self.send_message(
                    'Welcome to OoTR Draft Mode! '
                    'You can disable Draft Mode with !s7 cancel.'
                ),
                await self.send_message(
                    f'This is a "{args[0]}" race. Race monitors, use !seed 15 minutes prior to race start for a seed.'
                )
            elif args[0] in ('tournament', 'draft', 'random', 'qualifier') and draft.get('enabled'):
                await self.send_message(
                    'Draft Mode is already enabled.'
                )
            elif args[0] == 'cancel':
                if draft.get('enabled'):
                    if self.state.get('seed_id') and not can_moderate(message):
                        await self.send_message(
                            'You may not exit Draft Mode once the seed is rolled.'
                        )
                        return
                    if draft.get('race_type') == 'tournament':
                        # Only allow Race Moderators to cancel once drafting is complete.
                        if draft.get('status') == 'complete' and not can_moderate(message):
                            await self.send_message(
                                'Drafting already complete. Contact a Race Moderator for assistance.'
                            )
                            return
                        await self.ex_fpa(['off'], message),
                    # Only allow Race Moderators to cancel qualifier races.
                    elif draft.get('race_type') == 'qualifier':
                        if not can_moderate(message):
                            return
                    await self.send_message(
                        'Draft Mode has been disabled.'
                    )
                    draft.clear()
                    return
                await self.send_message(
                    'Draft Mode is currently disabled.'
                )
            return
        await self.send_message(
            'Invalid option. Available options are: tournament, draft, random, cancel.'
        )

    async def ex_first(self, args, message):
        """
        Handle !first commands.

        Allow higher-seeded player to pick first.
        """
        draft = self.state.get('draft_data')
        if self._race_in_progress() or not draft.get('status') == 'select_order':
            return
        
        reply_to = message.get('user', {}).get('name')
        racer = draft.get('racers')

        # Compare sender to draft_data 
        if racer[0].get('name') != reply_to:
            return
        draft.update({'current_selector': racer[0].get('name')})
        await self.send_message(
            f'{reply_to}, remove a setting with !ban <setting>.'
        )
        await self.send_message(
            'Use !settings for available options.'
        )
        await self.send_message(
            'Use !skip to avoid removing a setting.'
        )
        draft.update({'status': 'ban'})

    async def ex_second(self, args, message):
        """
        Handle !second commands.

        Allow higher-seeded player to pick second.
        """
        draft = self.state.get('draft_data')
        if self._race_in_progress() or not draft.get('status') == 'select_order':
            return
        
        reply_to = message.get('user', {}).get('name')
        racer = draft.get('racers')

        # Compare sender to draft_data 
        if racer[0].get('name') != reply_to:
            return
        draft.update({'current_selector': racer[1].get('name')})
        await self.send_message(
            f"{draft.get('current_selector')}, remove a setting with !ban <setting>."
        )
        await self.send_message(
            'Use !settings for available options.'
        )
        await self.send_message(
            'Use !skip to avoid removing a setting.'
        )
        draft.update({'status': 'ban'})
            
    async def ex_ban(self, args, message):
        """
        Handles !ban commands.

        Force setting to default value.
        """
        draft = self.state.get('draft_data')
        if self._race_in_progress() or draft.get('status') != 'ban':
            return
        
        reply_to = message.get('user', {}).get('name')
        racer = draft.get('racers')
        major_pool = draft.get('available_settings').get('major')
        minor_pool = draft.get('available_settings').get('minor')

        if reply_to == draft.get('current_selector'):
            if len(args) == 1 and (args[0] in major_pool.keys() or args[0] in minor_pool.keys()):
                await self.send_message(
                    f'{args[0].capitalize()} will be removed from the pool.'
                )
                # Remove setting from available settings pool
                major_pool.pop(args[0]) if args[0] in major_pool.keys() else minor_pool.pop(args[0])
                # Advance draft state.
                draft['ban_count'] += 1
                # Change player turn post setting selection.
                if reply_to == racer[0].get('name'):
                    draft.update({'current_selector': racer[1].get('name')})
                elif reply_to == racer[1].get('name'):
                    draft.update({'current_selector': racer[0].get('name')})
                # Move to pick phase once each player has banned.
                if draft.get('ban_count') == 2:
                    draft.update({'status': 'major_pick'})
                    await self.send_message(
                        'All bans have been recorded.'
                    )
                    await self.send_message(
                        f"{draft.get('current_selector')}, modify a major setting with !pick <setting> <value>."
                    )
                    await self.send_message(
                        'Use !settings for of available options.'
                    )
                    return
                await self.send_message(
                    f"{draft.get('current_selector')}, remove a setting with !ban <setting>."
                )
                await self.send_message(
                    'Use !settings for available options.'
                )
                await self.send_message(
                    'Use !skip to avoid removing a setting.'
                )
                return
            # Handle invalid format and unknown arguments
            await self.send_message(
                'Invalid option. Use !settings for available options.'
            )

    async def ex_skip(self, args, message):
        draft = self.state.get('draft_data')
        if self._race_in_progress() or draft.get('status') != 'ban':
            return
        
        reply_to = message.get('user', {}).get('name')
        racer = draft.get('racers')

        if reply_to == draft.get('current_selector'):
            await self.send_message(
                f'{reply_to} has chosen to skip removing a setting.'
            )
            # Advance draft state.
            draft['ban_count'] += 1
            # Change player turn post setting selection.
            if reply_to == racer[0].get('name'):
                draft.update({'current_selector': racer[1].get('name')})
            elif reply_to == racer[1].get('name'):
                draft.update({'current_selector': racer[0].get('name')})
            if draft.get('ban_count') < 2:
                await self.send_message(
                    f"{draft.get('current_selector')}, remove a setting with !ban <setting>."
                )
                await self.send_message(
                    'Use !skip to avoid removing a setting.'
                )
                await self.send_message(
                    'Use !settings for available options.'
                )
            elif draft.get('ban_count') == 2:
                draft.update({'status': 'major_pick'})
                await self.send_message(
                    'All bans have been recorded.'
                )
                await self.send_message(
                    f"{draft.get('current_selector')}, modify a major setting with !pick <setting> <value>."
                )
                await self.send_message(
                    'Use !settings for of available options.'
                )

    async def ex_pick(self, args, message):
        """
        Handles !pick commands.

        Change setting to specified value.
        """
        draft = self.state.get('draft_data')
        if self._race_in_progress() or not draft.get('enabled') or not draft.get('status') in ['major_pick', 'minor_pick']:
            return
        elif len(args) < 2:
            await self.send_message(
                'Invalid format. Use !pick <setting> <value>.'
            )
            return

        reply_to = message.get('user', {}).get('name')
        racer = draft.get('racers')
        major_pool = draft.get('available_settings').get('major')
        minor_pool = draft.get('available_settings').get('minor')
        picks = draft.get('drafted_settings').get('picks')
        data = draft.get('drafted_settings').get('data')

        if reply_to == draft.get('current_selector') and draft.get('status') == 'major_pick':
            # Handle setting from different pool
            if len(args) == 2 and args[0] in minor_pool.keys():
                await self.send_message(
                    'Invalid pool. Use !settings for available options.'
                )
                return
            elif len(args) == 2 and args[0] in major_pool.keys():
                if args[1] in major_pool.get(args[0]).keys():
                    await self.send_message(
                        f'{args[0].capitalize()} will be set to: {args[1].capitalize()}'
                    )
                    # Move setting keyword from available pool to picks pool. Add literal setting to data pool.
                    picks.update({args[0]: args[1]})
                    data.update({
                        setting[0]: setting[1] for setting in major_pool.get(args[0]).get(args[1]).items()
                    })
                    major_pool.pop(args[0])
                    # Advance draft state. Maintain ABABBA pick order.
                    draft['pick_count'] += 1
                else:
                    await self.send_message(
                        f'Invalid option for {args[0].capitalize()}. Available options are: {", ".join(value for value in major_pool.get(args[0]).keys())}'
                    )
                    return
                if draft.get('pick_count') == 2:
                    draft.update({
                        'status': 'minor_pick'
                    })
                    await self.send_message(
                        f"{draft.get('current_selector')}, modify a minor setting with !pick <setting> <value>."
                    )
                    await self.send_message(
                        'Use !settings for available options.'
                    )
                    return
                # Change player turn post setting selection.
                if reply_to == racer[0].get('name'):
                    draft.update({'current_selector': racer[1].get('name')})
                elif reply_to == racer[1].get('name'):
                    draft.update({'current_selector': racer[0].get('name')})
                await self.send_message(
                    f"{draft.get('current_selector')}, modify a major setting with !pick <setting> <value>."
                )
                await self.send_message(
                    'Use !settings for available options.'
                )
                return
            # Handle invalid format and unknown arguments
            await self.send_message(
                'Invalid option. Use !settings for available options.'
            )
        elif reply_to == draft.get('current_selector') and draft.get('status') == 'minor_pick':
            # Handle selecting setting from different pool.
            if len(args) == 2 and args[0] in major_pool.keys():
                await self.send_message(
                    'Invalid pool. Use !settings for available options.'
                )
                return
            elif len(args) == 2 and args[0] in minor_pool.keys():
                if args[1] in minor_pool.get(args[0]).keys():
                    await self.send_message(
                        f'{args[0].capitalize()} will be set to: {args[1].capitalize()}'
                    )
                    # Move setting keyword from available pool to picks pool. Add literal setting to data pool.
                    picks.update({args[0]: args[1]})
                    data.update({
                        setting[0]: setting[1] for setting in minor_pool.get(args[0]).get(args[1]).items()
                    })
                    minor_pool.pop(args[0])
                    # Advance draft state. Update status after final pick.
                    draft['pick_count'] += 1
                else:
                    await self.send_message(
                        f'Invalid option for {args[0].capitalize()}. Available options are: {", ".join(value for value in minor_pool.get(args[0]).keys())}'
                    )
                    return
                if draft.get('pick_count') == 4:
                    draft.update({
                        'status': 'complete',
                        'current_selector': None
                    })
                    await self.send_message(
                        'All picks have been recorded.'
                    )
                    await self.send_message(
                        'Use !seed 15 minutes prior to race start to roll the seed.'
                    )
                    return
                # Change player turn post setting selection.
                if reply_to == racer[0].get('name'):
                    draft.update({'current_selector': racer[1].get('name')})
                elif reply_to == racer[1].get('name'):
                    draft.update({'current_selector': racer[0].get('name')})
                await self.send_message(
                    f"{draft.get('current_selector')}, modify a minor setting with !pick <setting> <value>."
                )
                await self.send_message(
                    'Use !settings for available options.'
                )
                return
            # Handle invalid format and unknown arguments.
            await self.send_message(
                'Invalid option. Use !settings for available options.'
            )

    async def ex_settings(self, args, message):
        """
        Handle !settings commands.

        List available settings and values.
        """
        draft = self.state.get('draft_data')
        if not draft.get('enabled'):
            return
        
        major_pool = draft.get('available_settings').get('major')
        minor_pool = draft.get('available_settings').get('minor')
        combined_pool = {**major_pool, **minor_pool}
        picks = draft.get('drafted_settings').get('picks')

        if self._race_in_progress() or not draft.get('status') in ['ban', 'major_pick', 'minor_pick', 'complete', 'seed_rolled', 'settings_posted']:
            return
        if draft.get('status') == 'settings_posted':
            await self.send_message(
                'The settings have already been pinned above.'
            )
            return
        elif draft.get('status') == 'ban' and len(args) == 0:
            await self.send_message(
                'The following settings are available: '
                f"{' | '.join(combined_pool.keys())}"
            )
        elif draft.get('status') == 'major_pick':
            # List available settings to select from
            if len(args) == 0:
                await self.send_message(
                    'The following settings are available: '
                    f"{' | '.join(major_pool.keys())}"
                )
                await self.send_message(
                    'Use !settings <setting> to view available values.'
                )
            # List available values for specific setting
            elif len(args) == 1 and args[0] in major_pool.keys():
                setting = major_pool.get(args[0])
                await self.send_message(
                    f'Available values for {args[0].capitalize()}: {", ".join(value for value in setting.keys())}'
                )
                return
        elif draft.get('status') == 'minor_pick':
            # List available settings to select from
            if len(args) == 0:
                await self.send_message(
                    'The following settings are available: '
                    f"{' | '.join(minor_pool.keys())}"
                )
                await self.send_message(
                    'Use !settings <setting> to view available values.'
                )
            # List available values for specific setting
            elif len(args) == 1 and args[0] in minor_pool.keys():
                setting = minor_pool.get(args[0])
                await self.send_message(
                    f'Available values for {args[0].capitalize()}: {", ".join(value for value in setting.keys())}'
                )
        elif draft.get('status') == 'complete':
            if len(args) == 0:
                await self.send_message(
                    'Picks for this race: ' + ', '.join(f"{key.capitalize()}: {value.capitalize()}" for key, value in picks.items()),
                    pinned=True
                )
                await self.send_message(
                    '@entrants, Picks for the race are pinned above.'
                )
                draft.update({
                    'status': 'settings_posted'
                })
        elif draft.get('status') == 'seed_rolled' and draft.get('auto_draft'):
            await self.send_message(
                'Picks for this race: ' + ', '.join(f"{key.capitalize()}: {value.capitalize()}" for key, value in picks.items()),
                pinned=True
            )
            await self.send_message(
                '@entrants - Picks for the race are pinned above.'
            )
            draft.update({
                'status': 'settings_posted'
            })
            return
        # Delay settings reveal for 10 minutes after rolling the seed for qualifier races
        if draft.get('race_type') == 'qualifier':
            if datetime.datetime.now() - draft.get('rolled_at') > datetime.timedelta(minutes=10):
                await self.send_message(
                    'Picks for this race: ' + ', '.join(f"{key.capitalize()}: {value.capitalize()}" for key, value in picks.items()),
                    pinned=True
                )
                await self.send_message(
                    '@entrants - Picks for the race are pinned above.'
                )
                if self.data.get('status').get('value') == 'open':
                    await self.set_invitational()
                await self.send_message(
                    'Leaving the race at this point will result in a forfeit towards your qualification score.'
                )
                draft.update({
                    'status': 'settings_posted'
                })
                return
            await self.send_message(
                'Ha, nice try bud. Settings are revealed 5 minutes before race start.'
            )

    @monitor_cmd
    async def ex_lock(self, args, message):
        """
        Handle !lock commands.

        Prevent seed rolling unless user is a race monitor.
        """
        if self._race_in_progress():
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

    @monitor_cmd
    async def ex_password(self, args, message): 
        if len(args) == 1 and args[0] in ('on', 'off', 'get'):
            if args[0] == 'on':
                if self.state['password_active']:
                    resp = 'Password protection in file select is already activated'
                else:
                    self.state['password_active'] = True
                    resp = (
                        'Password protection in file select is now active. '
                        'Every runner will have to enter a 5 ocarina note password before '
                        'being able to start a file. The password will be announced in '
                        'the race room info up top as the countdown starts.'
                    )
            elif args[0] == 'get':
                if self.state['password_retry'] > 2:
                    seed_password_acquired = await self.load_seed_password(manual=True)            
                    if seed_password_acquired == False:
                        resp = 'Sorry, password could not be retrieved. Please try again in a few minutes.'
                    else:
                        resp = 'The password has been acquired successfully. You may start the race now.'
                else: 
                    resp = 'Manual password retrieval is only available if automated retrieval has not been successful before.'
            else:  # args[0] == 'off'
                if not self.state['password_active']:
                    resp = 'Password protection in file select is not active.'
                else:
                    self.state['password_active'] = False
                    resp = 'Password protection in file select is now deactivated.'
        elif self.state['password_active']:
            resp = (
                'Password protection in file select is currently active. Every runner will have to enter a 5 ocarina note password before '
                'being able to start a file. The password will be announced in the race room info up top as the countdown starts.'
            )
        else:
            resp = 'Password protection is not active. You may enable it with !password on'
        if resp:
            reply_to = message.get('user', {}).get('name', 'friend')
            await self.send_message(resp % {'reply_to': reply_to})

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
        preset = 'weekly'

        if len(args) > 0:
            preset = args[0]
            
            if len(args) == 2 and args[1] == "--withpassword":
                self.state['password_active'] = True
            else: 
                await self.send_message(
                    'Sorry %(reply_to)s, that is not the correct syntax. '
                    'The syntax is "!seed presetName {--withpassword}'
                    % {'reply_to': reply_to or 'friend'}
                )
                return
        
        draft = self.state.get('draft_data')
        password = self.state.get('password_active')

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
        if draft.get('enabled'):
            if draft.get('race_type') == 'qualifier' or draft.get('auto_draft'):
                if draft.get('race_type') == 'qualifier':
                    draft.update({'rolled_at': datetime.datetime.now()})
                await self.handle_random_seed(encrypt, dev, reply_to)
                return
            else:
                if draft.get('status') != 'complete':
                    await self.send_message(
                        f'Sorry {reply_to}, drafting must be completed before rolling the seed.'
                    )
                    return
            if draft.get('race_type') in ('draft', 'random', 'tournament'):
                await self.ex_settings('', '')
            await self.roll(
                preset=None,
                encrypt=encrypt,
                dev=dev,
                reply_to=reply_to,
                settings=self.patch_settings(),
                password=password
            )
            return 
        await self.roll(
            preset=preset,
            encrypt=encrypt,
            dev=dev,
            reply_to=reply_to,
            password=password
        )

    async def roll(self, preset, encrypt, dev, reply_to, settings=None, password=False):
        """
        Generate a seed and send it to the race room.
        """
        if not self.state.get('draft_data').get('enabled'):
            if (dev and preset not in self.zsr.presets_dev) or (not dev and preset not in self.zsr.presets):
                res_cmd = '!presetsdev' if dev else '!presets'
                await self.send_message(
                    'Sorry %(reply_to)s, I don\'t recognise that preset. Use '
                    '%(res_cmd)s to see what is available.'
                    % {'res_cmd': res_cmd, 'reply_to': reply_to or 'friend'}
                )
                return

        seed_id, seed_uri = self.zsr.roll_seed(preset, encrypt, dev, settings, self.state.get('draft_data').get('race_type'), password)

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
            await self.load_seed_password()            
        elif status >= 2:
            self.state['seed_id'] = None
            await self.send_message(
                'Sorry, but it looks like the seed failed to generate. Use '
                '!seed to try again.'
            )
            

    async def load_seed_password(self, manual=False):
        seed_password = self.zsr.get_password(self.state['seed_id'])
        if seed_password == None:
            if manual:
                return False
            elif self.state['password_retry'] > 2:
                await self.send_message(
                    'Sorry, but it looks like the password for this seed cannot be retrieved.'
                    'Please wait a few minutes and try manually before race start using !password get'
                )
            else: 
                self.state['password_retry'] +=1
                await sleep(120)
                await self.load_seed_password()
        else:
            self.state['seed_password'] = seed_password
            if manual:
                return True


    async def load_seed_hash(self):
        seed_hash = self.zsr.get_hash(self.state['seed_id'])
        self.state['seed_hash'] = seed_hash
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
        # Return list sorted by Qualifier ranking
        if self.state.get('draft_data').get('race_type') == 'tournament':
            placements = self.zsr.load_qualifier_placements()
            for entrant in self.data.get('entrants'):
                for place in placements:
                    if entrant.get('user').get('id') == place.get('id'):
                        entrants.append({'name': entrant.get('user').get('name'), 'rank': place.get('place')})
            return sorted(entrants, key=lambda entrant: entrant.get('rank'))    
        # Return list sorted by RaceTime points
        elif self.state.get('draft_data').get('race_type') == 'draft':
            for entrant in self.data.get('entrants'):
                entrants.append({'name': entrant.get('user').get('name'), 'score': (entrant.get('score') if entrant.get('score') else 0)})
            return sorted(entrants, key=lambda entrant: entrant.get('score'), reverse=True)

    async def handle_random_seed(self, encrypt, dev, reply_to):
        draft = self.state.get('draft_data')
        available_settings = draft.get('available_settings')
        drafted_settings = draft.get('drafted_settings')
        count = 0

        while count < 4:
            # Major pick
            if count < 2:
                pool = available_settings.get('major')
            # Minor pick
            else:
                pool = available_settings.get('minor')
            name = random.choice(list(pool.keys()))
            setting = random.choice(list(pool.get(name).keys()))
            for key, value in pool.get(name).get(setting).items():
                drafted_settings.get('data').update({
                    key: value
                })
            pool.pop(name)
            drafted_settings.get('picks').update({
                name: setting
            })
            count += 1

        await self.roll(
            preset=None,
            encrypt=encrypt,
            dev=dev,
            reply_to=reply_to,
            settings=self.patch_settings()
        )
        if draft.get('race_type') == 'qualifier':
            await self.send_message(
                f'Race Monitors, use !settings 5 minutes before race start to reveal the selected settings.'
            )
            await self.send_message(
                'Once revealed, the room will be locked from joining.'
            )
            return
        await self.ex_settings('', '')

    def patch_settings(self):
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

    def _race_pending(self):
        return self.data.get('status').get('value') == 'pending'
    
    def _race_in_progress(self):
        return self.data.get('status').get('value') in ('pending', 'in_progress')
