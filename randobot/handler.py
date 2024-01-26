from asyncio import sleep
from copy import deepcopy
import datetime
import re
import random
from racetime_bot import RaceHandler, monitor_cmd, can_moderate, can_monitor, msg_actions
from .draft import PlayerDraft, RandomDraft


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
                    msg_actions.Action(
                        label='Draft seed',
                        help_text='Initialize a draft',
                        message='!draft ${race_type}',
                        submit='Begin',
                        survey=msg_actions.Survey(
                            msg_actions.RadioInput(
                                name='race_type',
                                label='Race type',
                                options={'normal': 'Player draft', 'random': 'Auto-select settings'},
                                default='normal'
                            )
                        )
                    ),
                    msg_actions.ActionLink(
                        label='Help',
                        url='https://github.com/deains/ootr-randobot/blob/master/COMMANDS.md',
                    ),
                ],
                pinned=True,
            )
            self.state['intro_sent'] = True
        if 'locked' not in self.state:
            self.state['locked'] = False
        if 'fpa' not in self.state:
            self.state['fpa'] = False
        if 'draft_status' not in self.state:
            self.state['draft_status'] = None

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
    async def ex_draft(self, args, message):
        """
        Handle !draft commands.

        Set up room for Draft Mode.
        """
        if self._race_in_progress() or len(args) == 0 or len(args) > 2:
            return
        elif len(self.data.get('entrants')) < 2:
            await self.send_message(
                'At least two entrants must be present before beginning a draft.'
            )
            return
        if len(args) == 1:
            if args[0] in ('normal', 'random') and not self.state.get('draft_data'):
                self.state['draft_status'] = 'setup'
                await self.unpin_message(self.state['pinned_msg'])
                await self.send_message(
                    'Welcome to OoTR Draft Mode!'
                )
                if args[0] == 'normal':
                    await self.send_message(
                        'Configure the draft settings with the buttons below.',
                        actions=[
                            msg_actions.Action(
                                label='Configure draft',
                                help_text='Configure draft settings',
                                submit='Confirm',
                                message='!config draft ${draftees} ${is_tournament_race} ${total_bans} ${total_picks}',
                                survey=msg_actions.Survey(
                                    msg_actions.SelectInput(
                                        name='total_bans',
                                        label='Total bans',
                                        options={'2': '2', '4': '4', '6': '6'},
                                        default='2'
                                    ),
                                    msg_actions.SelectInput(
                                        name='total_picks',
                                        label='Total picks',
                                        options={'2': '2', '4': '4', '6': '6'},
                                        default='4'
                                    ),
                                    msg_actions.BoolInput(
                                        name='is_tournament_race',
                                        label='Tournament race'
                                    ),
                                    msg_actions.TextInput(
                                        name='draftees',
                                        label='Draftees (separated with a space)',
                                        placeholder='ex: Player1 Player2 Player3'
                                    )
                                )
                            ),
                            msg_actions.Action(
                                label='Cancel draft',
                                message='!draft cancel',
                            )
                        ]
                    )
                elif args[0] == 'random':
                    await self.send_message(
                        'Configure the amount of settings to change with the buttons below.',
                        actions=[
                            msg_actions.Action(
                                label='Configure seed',
                                help_text='Configure seed settings',
                                submit='Confirm',
                                message='!config random ${is_tournament_race} ${total_settings}',
                                survey=msg_actions.Survey(
                                    msg_actions.SelectInput(
                                        name='total_settings',
                                        label='Total # of random settings',
                                        options={'2': '2', '4': '4', '6': '6'},
                                        default='4'
                                    ),
                                    msg_actions.BoolInput(
                                        name='is_tournament_race',
                                        label='Qualifier race'
                                    )
                                )
                            ),
                            msg_actions.Action(
                                label='Cancel draft',
                                message='!draft cancel',
                            )
                        ]
                    )
            elif args[0] == 'cancel':
                if self.state['draft_status'] is not None:
                    if self.state.get('draft_data'):
                        if self.state.get('seed_id') and not can_moderate(message):
                            await self.send_message(
                                'Only a race moderator can cancel the draft once the seed is rolled.'
                            )
                            return
                        await self.ex_fpa(['off'], message)
                        del self.state['draft_data']
                    await self.pin_message(self.state['pinned_msg'])
                    await self.send_message(
                        'The draft has been canceled.'
                    )
                    self.state['draft_status'] = None
                    return
                await self.send_message(
                    'The draft has not been initialized.'
                )

    @monitor_cmd
    async def ex_config(self, args, message):
        """
        Helper function for !draft
        """
        if self._race_in_progress() or len(args) == 0 or self.state['draft_status'] != 'setup':
            return
        if not await self.logic_draft_instance(args):
            return
        if args[0] == 'draft':
            self.state['draft_data'] = PlayerDraft(self.data['entrants'], self.zsr.load_available_settings(), args, self.zsr.load_qualifier_placements())
            if self.state['draft_data'].is_tournament_race:
                await self.ex_fpa(['on'], message)
            await self.send_message(
                f"@{self.state['draft_data'].draftees[0]['name'].capitalize()}, would you like to ban first or second?",
                actions=[
                    msg_actions.Action(
                        label='First',
                        message='!first'
                    ),
                    msg_actions.Action(
                        label='Second',
                        message='!second'
                    ),
                    msg_actions.Action(
                        label='Cancel draft',
                        message='!draft cancel'
                    )
                ]
            )
        elif args[0] == 'random':
            self.state['draft_data'] = RandomDraft(self.zsr.load_available_settings(), args)
        self.state['draft_status'] = 'drafting_order'

    async def ex_first(self, args, message):
        """
        Handle !first commands.

        Allow higher-seeded player to pick first.
        """
        if self._race_in_progress() or self.state['draft_status'] != 'drafting_order':
            return
        reply_to = message.get('user', {}).get('name')
        if self.state['draft_data'].assign_first_pick(reply_to):
            await self.send_message(
                f"{reply_to} has elected to go first. Select a setting to lock in or skip.",
                actions=[
                    msg_actions.Action(
                        label='Select setting',
                        message='!ban {setting}',
                        submit='Select',
                        survey=msg_actions.Survey(
                            msg_actions.SelectInput(
                                name='setting',
                                label='Setting to lock in',
                                options={setting: setting for setting in self.state['draft_data'].complete_settings_pool}
                            )
                        )
                    ),
                    msg_actions.Action(
                        label='Skip',
                        message='!skip',
                    ),
                    msg_actions.Action(
                        label='Cancel draft',
                        message='!draft cancel'
                    )
                ]
            )
            self.state['draft_status'] = 'player_bans'

    async def ex_second(self, args, message):
        """
        Handle !second commands.

        Allow higher-seeded player to pick second.
        """
        if self._race_in_progress() or self.state['draft_status'] != 'drafting_order':
            return
        self.state['']
        # reply_to = message.get('user', {}).get('name')
        # racer = draft.get('racers')

        # # Compare sender to draft_data 
        # if racer[0].get('name') != reply_to:
        #     return
        # draft.update({'current_selector': racer[1].get('name')})
        # await self.send_message(
        #     f"{draft.get('current_selector')}, remove a setting with !ban <setting>."
        # )
        # await self.send_message(
        #     'Use !settings for available options.'
        # )
        # await self.send_message(
        #     'Use !skip to avoid removing a setting.'
        # )
        # draft.update({'status': 'ban'})
            
    async def ex_ban(self, args, message):
        """
        Handles !ban commands.

        Force setting to default value.
        """
        if self._race_in_progress() or self.state['draft_status'] != 'player_bans':
            return
        draft = self.state['draft_data']
        draft.ban_setting(args, message)

    #     reply_to = message.get('user', {}).get('name')
    #     racer = draft.get('racers')
    #     major_pool = draft.get('available_settings').get('major')
    #     minor_pool = draft.get('available_settings').get('minor')

    #     if reply_to == draft.get('current_selector'):
    #         if len(args) == 1 and (args[0] in major_pool.keys() or args[0] in minor_pool.keys()):
    #             await self.send_message(
    #                 f'{args[0].capitalize()} will be removed from the pool.'
    #             )
    #             # Remove setting from available settings pool
    #             major_pool.pop(args[0]) if args[0] in major_pool.keys() else minor_pool.pop(args[0])
    #             # Advance draft state.
    #             draft['ban_count'] += 1
    #             # Change player turn post setting selection.
    #             if reply_to == racer[0].get('name'):
    #                 draft.update({'current_selector': racer[1].get('name')})
    #             elif reply_to == racer[1].get('name'):
    #                 draft.update({'current_selector': racer[0].get('name')})
    #             # Move to pick phase once each player has banned.
    #             if draft.get('ban_count') == 2:
    #                 draft.update({'status': 'major_pick'})
    #                 await self.send_message(
    #                     'All bans have been recorded.'
    #                 )
    #                 await self.send_message(
    #                     f"{draft.get('current_selector')}, modify a major setting with !pick <setting> <value>."
    #                 )
    #                 await self.send_message(
    #                     'Use !settings for of available options.'
    #                 )
    #                 return
    #             await self.send_message(
    #                 f"{draft.get('current_selector')}, remove a setting with !ban <setting>."
    #             )
    #             await self.send_message(
    #                 'Use !settings for available options.'
    #             )
    #             await self.send_message(
    #                 'Use !skip to avoid removing a setting.'
    #             )
    #             return
    #         # Handle invalid format and unknown arguments
    #         await self.send_message(
    #             'Invalid option. Use !settings for available options.'
    #         )

    async def ex_skip(self, args, message):
        if self._race_in_progress() or self.state['draft_status'] != 'player_bans':
            return
        draft = self.state['draft_data']
        draft.skip_ban(args, message)
        # reply_to = message.get('user', {}).get('name')
        # racer = draft.get('racers')

        # if reply_to == draft.get('current_selector'):
        #     await self.send_message(
        #         f'{reply_to} has chosen to skip removing a setting.'
        #     )
        #     # Advance draft state.
        #     draft['ban_count'] += 1
        #     # Change player turn post setting selection.
        #     if reply_to == racer[0].get('name'):
        #         draft.update({'current_selector': racer[1].get('name')})
        #     elif reply_to == racer[1].get('name'):
        #         draft.update({'current_selector': racer[0].get('name')})
        #     if draft.get('ban_count') < 2:
        #         await self.send_message(
        #             f"{draft.get('current_selector')}, remove a setting with !ban <setting>."
        #         )
        #         await self.send_message(
        #             'Use !skip to avoid removing a setting.'
        #         )
        #         await self.send_message(
        #             'Use !settings for available options.'
        #         )
        #     elif draft.get('ban_count') == 2:
        #         draft.update({'status': 'major_pick'})
        #         await self.send_message(
        #             'All bans have been recorded.'
        #         )
        #         await self.send_message(
        #             f"{draft.get('current_selector')}, modify a major setting with !pick <setting> <value>."
        #         )
        #         await self.send_message(
        #             'Use !settings for of available options.'
        #         )

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
        draft = self.state.get('draft_data')

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
                settings=self.patch_settings()
            )
            return 
        await self.roll(
            preset=args[0] if args else 'weekly',
            encrypt=encrypt,
            dev=dev,
            reply_to=reply_to
        )

    async def roll(self, preset, encrypt, dev, reply_to, settings=None):
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

        seed_id, seed_uri = self.zsr.roll_seed(preset, encrypt, dev, settings, self.state.get('draft_data').get('race_type'))

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

    async def logic_draft_instance(self, args):
        if args[0] == 'draft':
            if len(args) < 6:
                await self.send_message(
                    'Invalid syntax. Use the buttons for assistance.'
                )
                return False
            _, *draftees, is_tournament_race, max_bans, max_picks = args
            for entrant in self.data['entrants']:
                if entrant['user']['name'].lower() not in draftees:
                    await self.send_message(
                        'One or more supplied draftees are not in the room.'
                    )
                    return False
            if is_tournament_race:
                if max_bans != '2' or max_picks != '4':
                    await self.send_message(
                        'Draftees may only ban 2 settings and pick 4 settings for tournament races.'
                    )
                    return False
                elif len(draftees) != 2:
                    await self.send_message(
                        'Only 2 draftees may participate in tournament races.'
                    )
                    return False
            if len(draftees) < 2:
                await self.send_message(
                    'At least 2 draftees must be selected to draft settings.'
                )
                return False
        elif args[0] == 'random':
            if len(args) != 3:
                await self.send_message(
                    'Invalid syntax. Use the buttons for assistance.'
                )
                return False
            _, is_tournament_race, num_settings = args
            if is_tournament_race and num_settings != '2':
                await self.send_message(
                    'Only 2 settings may be changed in tournament races'
                )
                return False
        return True

    def _race_in_progress(self):
        return self.data.get('status').get('value') in ('pending', 'in_progress')
