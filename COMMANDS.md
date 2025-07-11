# RandoBot commands

These are the commands currently supported by OoTR's RandoBot.

## !seed

Usable by: anyone (unless lock is present)

Roll a race seed on ootrandomizer.com using the specified preset (if given) and
post a link to the generated seed in the race information.

Available presets can be checked using the `!presets` command. If no preset is
given then "weekly" is assumed.

If seed rolling has been locked with the `!lock` command then `!seed` will not
generate a seed unless it's used by a race monitor or moderator.

Once a seed has been generated using `!seed` (or `!spoilerseed`), subsequent
calls to `!seed` will not work unless used by a moderator.

## !spoilerseed

Usable by: anyone (unless lock is present)

Roll a non-race seed (i.e. seed with spoiler log). This is identical to
`!seed`, except for the addition of the spoiler log. The patch file will also
not be encrypted.

## !presets

Usable by: anyone

The bot will print out a list of available presets for use with the `!seed` or
`!spoilerseed` commands. Each preset is usually a single word, e.g. "s4" or
"weekly".

Presets are set by ootrandomizer.com and are not controlled by the bot itself.

## !lock

Usable by: **race monitor/moderators only**

Locks the ability to roll seeds in this race room, meaning that the `!seed` and
`!spoilerseed` commands may only be used by race monitors and moderators.

## !unlock

Usable by: **race monitor/moderators only**

Unlocks the ability to roll seeds, allowing anyone to use the `!seed` and
`!spoilerseed` commands. This is the default behaviour, so you only need to use
`!unlock` to cancel a previous `!lock`.

## !fpa

Usable by: **varies**

Enable, disable or invoke the fair-play agreement notifier. By default the FPA
system is disabled, it can be toggled on by a race monitor or moderator with
`!fpa on`. It can be toggled off again with `!fpa off`.

When enabled, any user in the race room may use `!fpa` (with no
arguments) to invoke the FPA while the race is in progress. This will generate
an **@everyone** notification, so that all participants are made aware. FPA can
be invoked multiple times.

It is recommended to enable desktop notifications using the bell icon in
racetime.gg chat when using FPA. This way your browser will notify you
immediately if there is a ping.

To prevent spam or misuse, it is also recommended that the **"Allow non-entrant
chat"** race setting is disabled when conducting a race using FPA.

## !password

Usable by: **varies**

Enable or disable the password functionality. By default, this is disabled, but it 
can be toggled on by a race monitor or moderator with `!password on`. 
It can be toggled off again with `!password off`.

When enabled, the seed is generated with a random 6 digit password consisting of
ocarina notes. This password is required to start a file in the generated seed.

Once this setting is enabled, Randobot will publish the password at the start of the
race countdown next to the seed hash in the race room information.

If the automated password retrieval after rolling the seed, manual acquiry can be attempted using `!password get`. 
Note that a race with a password activated seed can not be started without a password.