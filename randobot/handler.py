from asyncio import create_task, gather, sleep
import contextlib
import datetime
import json
import re
import isodate
from racetime_bot import RaceHandler, monitor_cmd, can_moderate, can_monitor

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

def format_breaks(duration, interval):
    return f'{format_duration(duration)} every {format_duration(interval)}'

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

    def __init__(self, zsr, midos_house, **kwargs):
        super().__init__(**kwargs)
        self.zsr = zsr
        self.midos_house = midos_house

    def should_stop(self):
        goal_name = self.data.get('goal', {}).get('name')
        goal_is_custom = self.data.get('goal', {}).get('custom', False)
        if goal_is_custom:
            if self.midos_house.handles_custom_goal(goal_name):
                return True # handled by https://github.com/midoshouse/midos.house
        else:
            if goal_name == 'Random settings league':
                return True # handled by https://github.com/fenhl/rslbot
        return super().should_stop()

    async def begin(self):
        """
        Send introduction messages.
        """
        if self.should_stop():
            return
        self.heartbeat_task = create_task(self.heartbeat(), name=f'heartbeat for {self.data.get("name")}')
        if not self.state.get('intro_sent') and not self._race_in_progress():
            await self.send_message(
                'Welcome to OoTR! Create a release seed with !seed <preset> or a latest dev seed with !seeddev <preset>'
            )
            await self.send_message(
                'If no preset is selected, weekly settings will be used. '
                'Use !race to generate a release seed with a spoiler log.'
            )
            await self.send_message(
                'For a list of presets, use !presets for release and !presetsdev for dev'
            )
            self.state['intro_sent'] = True
        if 'locked' not in self.state:
            self.state['locked'] = False
        if 'fpa' not in self.state:
            self.state['fpa'] = False
        if 'breaks' not in self.state:
            self.state['breaks'] = None

    async def race_data(self, data):
        await super().race_data(data)
        if self.data.get('started_at') is not None:
            if not self.state.get('break_notifications_started') and self.state.get('breaks') is not None:
                self.state['break_notifications_started'] = True
                self.break_notifications_task = create_task(self.break_notifications(), name=f'break notifications for {self.data.get("name")}')

    async def heartbeat(self):
        while not self.should_stop():
            await sleep(20)
            await self.ws.send(json.dumps({'action': 'ping'}))

    async def break_notifications(self):
        duration, interval = self.state['breaks']
        await sleep((interval + isodate.parse_duration(self.data.get('start_delay', 'P0DT00H00M00S')) - datetime.timedelta(minutes=5)).total_seconds())
        while not self.should_stop():
            await gather(
                self.send_message('@entrants Reminder: Next break in 5 minutes.'),
                sleep(datetime.timedelta(minutes=5).total_seconds()),
            )
            if self.should_stop():
                break
            await gather(
                self.send_message(f'@entrants Break time! Please pause for {format_duration(duration)}.'),
                sleep(duration.total_seconds()),
            )
            if self.should_stop():
                break
            await gather(
                self.send_message('@entrants Break ended. You may resume playing.'),
                sleep((interval - duration - datetime.timedelta(minutes=5)).total_seconds()),
            )

    @monitor_cmd
    async def ex_lock(self, args, message):
        """
        Handle !lock commands.

        Prevent seed rolling unless user is a race monitor.
        """
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
        await self.roll_and_send(args, message, encrypt=True, dev=True)

    async def ex_spoilerseed(self, args, message):
        """
        Handle !spoilerseed commands.
        """
        if self._race_in_progress():
            return
        await self.roll_and_send(args, message, encrypt=False, dev=False)

    async def ex_presets(self, args, message):
        """
        Handle !presets commands.
        """
        if self._race_in_progress():
            return
        await self.send_presets(False)

    async def ex_presetsdev(self, args, message):
        """
        Handle !presetsdev commands.
        """
        if self._race_in_progress():
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

    async def ex_breaks(self, args, message):
        if self._race_in_progress():
            return
        if len(args) == 0:
            if self.state['breaks'] is None:
                await self.send_message('Breaks are currently disabled. Example command to enable: !breaks 5m every 2h30')
            else:
                await self.send_message(f'Breaks are currently set to {format_breaks(*self.state["breaks"])}. Disable with !breaks off')
        elif len(args) == 1 and args[0] == 'off':
            self.state['breaks'] = None
            await self.send_message('Breaks are now disabled.')
        else:
            reply_to = message.get('user', {}).get('name')
            try:
                sep_idx = args.index('every')
                duration = parse_duration(args[:sep_idx], default='minutes')
                interval = parse_duration(args[sep_idx + 1:], default='hours')
            except ValueError:
                await self.send_message(f'Sorry {reply_to or "friend"}, I don\'t recognise that format for breaks. Example commands: !breaks 5m every 2h30, !breaks off')
            else:
                if duration < datetime.timedelta(minutes=1):
                    await self.send_message(f'Sorry {reply_to or "friend"}, minimum break time (if enabled at all) is 1 minute. You can disable breaks entirely with !breaks off')
                elif interval < duration + datetime.timedelta(minutes=5):
                    await self.send_message(f'Sorry {reply_to or "friend"}, there must be a minimum of 5 minutes between breaks since I notify runners 5 minutes in advance.')
                elif duration + interval >= datetime.timedelta(hours=24):
                    await self.send_message(f'Sorry {reply_to or "friend"}, race rooms are automatically closed after 24 hours so these breaks wouldn\'t work.')
                else:
                    self.state['breaks'] = duration, interval
                    await self.send_message(f'Breaks set to {format_breaks(duration, interval)}.')

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

    def _race_in_progress(self):
        return self.data.get('status').get('value') in ('pending', 'in_progress')
