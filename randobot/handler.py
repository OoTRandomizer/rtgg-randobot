from racetime_bot import RaceHandler


class RandoHandler(RaceHandler):
    """
    RandoBot race handler. Generates seeds, presets, and frustration.
    """
    def __init__(self, zsr, **kwargs):
        super().__init__(**kwargs)

        self.zsr = zsr
        self.presets = zsr.load_presets()
        self.seed_rolled = False

    async def begin(self):
        """
        Send introduction messages.
        """
        await self.send_message(
            'Need a seed generated? Use !seed <preset> as soon as you\'re '
            'ready (e.g. !seed weekly). Use !race <preset> to generate a race '
            'seed.'
        )
        await self.send_message(
            'For a list of presets, use !presets'
        )

    async def ex_seed(self, args, message):
        """
        Handle !seed commands.
        """
        await self.roll_and_send(args, message, False)

    async def ex_race(self, args, message):
        """
        Handle !race commands.
        """
        await self.roll_and_send(args, message, True)

    async def ex_presets(self, args, message):
        """
        Handle !presets commands.
        """
        await self.send_presets()

    async def roll_and_send(self, args, message, encrypt):
        """
        Read an incoming !seed or !race command, and generate a new seed if
        valid.
        """
        if self.seed_rolled:
            await self.send_message(
                'I already rolled a seed. Don\'t get greedy!'
            )
            return

        if len(args) == 0:
            await self.send_message('Please specify a preset.')
            return

        await self.roll(
            preset=args[0],
            encrypt=encrypt,
            reply_to=message.get('user', {}).get('name', 'Okay'),
        )

    async def roll(self, preset, encrypt, reply_to):
        """
        Generate a seed and send it to the race room.
        """
        if preset not in self.presets:
            await self.send_message(
                'Sorry, I don\'t recognise that preset. Use !presets to see '
                'what is available.'
            )
            return

        seed_uri = self.zsr.roll_seed(self.presets[preset], encrypt)

        await self.send_message(
            '%(reply_to)s, here is your seed: %(seed_uri)s'
            % {'reply_to': reply_to, 'seed_uri': seed_uri}
        )
        await self.set_raceinfo(seed_uri)

        self.seed_rolled = True

    async def send_presets(self):
        """
        Send a list of known presets to the race room.
        """
        await self.send_message('Available presets:')
        for name, full_name in self.presets.items():
            await self.send_message(f'{name} – {full_name}')
