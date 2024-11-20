from asyncio import sleep
from copy import deepcopy
import datetime
import re
import random
from racetime_bot import RaceHandler, monitor_cmd, can_moderate, can_monitor, msg_actions
from .draft import configure_draft, DraftData


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
                return True  # handled by Mido
        else:
            if goal_name in ('Random settings league', 'Triforce Blitz'):
                return True  # handled by Mido
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
                                default='s8',
                            ),
                            msg_actions.BoolInput(
                                name='--withpassword',
                                label='Password',
                                help_text='Locks file creation behind a 6 ocarina notes password provided at countdown start',
                            ),
                        ),
                    ),
                    msg_actions.Action(
                        label='Dev seed',
                        help_text='Create a seed using the latest dev branch',
                        message='!seeddev ${preset} ${--withpassword}',
                        submit='Roll dev seed',
                        survey=msg_actions.Survey(
                            msg_actions.SelectInput(
                                name='preset',
                                label='Preset',
                                options={key: value['full_name'] for key, value in self.zsr.presets_dev.items()},
                                default='s8',
                            ),
                            msg_actions.BoolInput(
                                name='--withpassword',
                                label='Password',
                                help_text='Locks file creation behind a 6 ocarina notes password provided at countdown start',
                            ),
                        ),
                    ),
                    msg_actions.Action(
                        label='Start draft',
                        help_text='Begin a settings draft',
                        message='!draft on'
                    ),
                    msg_actions.ActionLink(
                        label='Help',
                        url='https://github.com/OoTRandomizer/rtgg-randobot/blob/master/COMMANDS.md',
                    ),
                ],
                pinned=True,
            )
            self.state['intro_sent'] = True
        if 'locked' not in self.state:
            self.state['locked'] = False
        if 'fpa' not in self.state:
            self.state['fpa'] = False
        if 'password_active' not in self.state:
            self.state['password_active'] = False
        if 'password_published' not in self.state:
            self.state['password_published'] = False
        if 'password_retrieval_failed' not in self.state:
            self.state['password_retrieval_failed'] = False
        if 'draft_race' not in self.state:
            self.state['draft_race'] = False

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
        if self.state.get('draft_race'):
            await self.send_message('This command is disabled for draft races.')
            return
        await self.roll_and_send(args, message, encrypt=True, dev=False)

    async def ex_seeddev(self, args, message):
        """
        Handle !seeddev commands.
        """
        if self._race_in_progress():
            return
        if self.state.get('draft_race'):
            await self.send_message('This command is disabled for draft races.')
            return
        await self.roll_and_send(args, message, encrypt=True, dev=True)

    async def ex_spoilerseed(self, args, message):
        """
        Handle !spoilerseed commands.
        """
        if self._race_in_progress():
            return
        if self.state.get('draft_race'):
            await self.send_message('This command is disabled for draft races.')
            return
        await self.roll_and_send(args, message, encrypt=False, dev=False)

    async def ex_presets(self, args, message):
        """
        Handle !presets commands.
        """
        if self._race_in_progress():
            return
        if self.state.get('draft_race'):
            await self.send_message('This command is disabled for draft races.')
            return
        await self.send_presets(False)

    async def ex_presetsdev(self, args, message):
        """
        Handle !presetsdev commands.
        """
        if self._race_in_progress():
            return
        if self.state.get('draft_race'):
            await self.send_message('This command is disabled for draft races.')
            return
        await self.send_presets(True)

    async def ex_draft(self, args, message):
        if len(args) == 1 and args[0] in ('on', 'off'):
            if args[0] == 'on' and not self.state.get('draft_race'):
                if self.state.get('pinned_msg'):
                    await self.unpin_message(self.state['pinned_msg'])
                self.state['draft_race'] = True
                await self.send_message(
                    'Welcome to the draft! Use the buttons below to set the configuration.',
                    actions=[
                        msg_actions.Action(
                            label='Configure draft',
                            help_text='Configure a draft race',
                            message='!draft config ${drafter1} ${drafter2} ${num_bans} ${num_picks} ${base_preset} ${--allow_default_picks} ${--sort}',
                            submit='Begin Draft',
                            survey=msg_actions.Survey(
                                msg_actions.SelectInput(
                                    name='drafter1',
                                    label='Drafter 1',
                                    options={entrant['user']['full_name']: entrant['user']['full_name'] for entrant in self.data['entrants']},
                                ),
                                msg_actions.SelectInput(
                                    name='drafter2',
                                    label='Drafter 2',
                                    options={entrant['user']['full_name']: entrant['user']['full_name'] for entrant in self.data['entrants']},
                                ),
                                msg_actions.SelectInput(
                                    name='num_bans',
                                    label='Bans per drafter',
                                    options={num: num for num in range(1, 10)},
                                ),
                                msg_actions.SelectInput(
                                    name='num_picks',
                                    label='Picks per drafter',
                                    options={num: num for num in range(1, 10)},
                                    default=2,
                                ),
                                msg_actions.SelectInput(
                                    name='base_preset',
                                    label='Base Preset',
                                    options={key: value['full_name'] for key, value in self.zsr.presets.items()},
                                    default='s8',
                                ),
                                msg_actions.BoolInput(
                                    name='--allow_default_picks',
                                    label='Allow default picks',
                                    help_text='Choose whether or not to allow the selection of a preset\'s default value',
                                    default=True,
                                ),
                                msg_actions.BoolInput(
                                    name='--sort',
                                    label='Sort by racetime.gg score',
                                    help_text='Sorts the drafters by their racetime.gg scores to determine who decides the draft order',
                                    default=True,
                                ),
                            ),
                        ),
                        msg_actions.Action(
                            label='Cancel draft',
                            message='!draft off'
                        )
                    ],
                )
            elif args[0] == 'off' and self.state.get('draft_race'):
                if self.state.get('pinned_msg'):
                    await self.pin_message(self.state['pinned_msg'])
                self.state['draft_race'] = False
                if self.state.get('draft_data'):
                    del self.state['draft_data']
                await self.send_message('The draft has been canceled')
        if args[0] == 'config' and self.state.get('draft_race'):
            draft_config, resp = configure_draft(self.data['entrants'], self.zsr.presets, args[1:])
            if draft_config:
                self.state['draft_data'] = DraftData(*draft_config)
            await self.send_message(resp)

    async def ex_first(self, args, message):
        pass

    async def ex_second(self, args, message):
        pass

    async def ex_ban(self, args, message):
        pass

    async def ex_pick(self, args, message):
        pass

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
                        'Every runner will have to enter a 6 ocarina note password before '
                        'being able to start a file. The password will be announced in '
                        'the race room info up top as the countdown starts.'
                    )
            elif args[0] == 'get':
                if self.state['password_retrieval_failed']:
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
                'Password protection in file select is currently active. Every runner will have to enter a 6 ocarina note password before '
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
        preset = 's8'

        if len(args) > 0:
            preset = args[0]

            if len(args) == 2:
                if args[1] == '--withpassword':
                    self.state['password_active'] = True
                else:
                    await self.send_message(
                        'Sorry %(reply_to)s, that is not the correct syntax. '
                        'The syntax is "!seed presetName {--withpassword}"'
                        % {'reply_to': reply_to or 'friend'}
                    )
                    return

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
        await self.roll(
            preset=preset,
            encrypt=encrypt,
            dev=dev,
            reply_to=reply_to,
            password=password
        )

    async def roll(self, preset, encrypt, dev, reply_to, password=False):
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

        seed_id, seed_uri = self.zsr.roll_seed(preset, encrypt, dev, password)

        await self.send_message(
            '%(reply_to)s, here is your seed: %(seed_uri)s'
            % {'reply_to': reply_to or 'Okay', 'seed_uri': seed_uri}
        )
        if self.state.get('password_active'):
            await self.send_message(
                'Please note that this seed is password protected. You will receive the password to start a file ingame as soon as the countdown starts.'
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
            if self.state.get('password_active'):
                await self.load_seed_password()
        elif status >= 2:
            self.state['seed_id'] = None
            await self.send_message(
                'Sorry, but it looks like the seed failed to generate. Use '
                '!seed to try again.'
            )

    async def load_seed_password(self, manual=False):
        seed_password = self.zsr.get_password(self.state['seed_id'])
        if seed_password is None:
            if manual:
                return False
            else:
                self.state['password_retrieval_failed'] = True
                await self.send_message(
                    'Sorry, but it looks like the password for this seed cannot be retrieved.'
                    'Please wait a few minutes and try manually before race start using !password get'
                )
        else:
            self.state['seed_password'] = seed_password
            self.state['password_retrieval_failed'] = False
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

    def _race_pending(self):
        return self.data.get('status').get('value') == 'pending'

    def _race_in_progress(self):
        return self.data.get('status').get('value') in ('pending', 'in_progress')
