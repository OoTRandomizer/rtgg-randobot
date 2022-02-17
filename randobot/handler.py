from asyncio import sleep
from racetime_bot import RaceHandler, monitor_cmd, can_moderate, can_monitor


class RandoHandler(RaceHandler):
    """
    RandoBot race handler. Generates seeds, presets, and frustration.
    """
    seed_url = 'https://ootrandomizer.com/seed/get?id=%s'
    stop_at = ['cancelled', 'finished']
    max_status_checks = 50

    def __init__(self, zsr, **kwargs):
        super().__init__(**kwargs)
        self.zsr = zsr

    async def begin(self):
        """
        Send introduction messages.
        """
        if not self.state.get('intro_sent') and not self._race_in_progress():
            await self.send_message(
                'Welcome to OoTR! Create a seed with !seed <preset>'
            )
            await self.send_message(
                'If no preset is selected, weekly settings will be used. '
                'Use !spoilerseed to generate a seed with a spoiler log.'
            )
            await self.send_message(
                'For a list of presets, use !presets'
            )
            self.state['intro_sent'] = True
        if 'locked' not in self.state:
            self.state['locked'] = False
        if 'fpa' not in self.state:
            self.state['fpa'] = False

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
        await self.roll_and_send(args, message, True)

    async def ex_spoilerseed(self, args, message):
        """
        Handle !race commands.
        """
        if self._race_in_progress():
            return
        await self.roll_and_send(args, message, False)

    async def ex_presets(self, args, message):
        """
        Handle !presets commands.
        """
        if self._race_in_progress():
            return
        await self.send_presets()

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

    async def roll_and_send(self, args, message, encrypt):
        """
        Read an incoming !seed or !race command, and generate a new seed if
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
            reply_to=reply_to,
        )

    async def roll(self, preset, encrypt, reply_to):
        """
        Generate a seed and send it to the race room.
        """
        if preset not in self.zsr.presets:
            await self.send_message(
                'Sorry %(reply_to)s, I don\'t recognise that preset. Use '
                '!presets to see what is available.'
                % {'reply_to': reply_to or 'friend'}
            )
            return

        seed_id, seed_uri = self.zsr.roll_seed(preset, encrypt)

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

    async def send_presets(self):
        """
        Send a list of known presets to the race room.
        """
        await self.send_message('Available presets:')
        for name, preset in self.zsr.presets.items():
            await self.send_message('%s – %s' % (name, preset['full_name']))

    def _race_in_progress(self):
        return self.data.get('status').get('value') in ('pending', 'in_progress')
