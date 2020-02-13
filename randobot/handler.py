from racetime_bot import RaceHandler


class RandoHandler(RaceHandler):
    """
    RandoBot race handler. Generates seeds, presets, and frustration.
    """
    stop_at = ['pending', 'in_progress', 'cancelled', 'finished']

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
            'Welcome to OoTR! Create a seed with !seed <preset>'
        )
        await self.send_message(
            'If no preset is selected, weekly settings will be used. '
            'Use !spoilerseed to generate a seed with a spoiler log.'
        )
        await self.send_message(
            'For a list of presets, use !presets'
        )

    async def ex_seed(self, args, message):
        """
        Handle !seed commands.
        """
        await self.roll_and_send(args, message, True)

    async def ex_spoilerseed(self, args, message):
        """
        Handle !race commands.
        """
        await self.roll_and_send(args, message, False)

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

        await self.roll(
            preset=args[0] if args else 'weekly',
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
