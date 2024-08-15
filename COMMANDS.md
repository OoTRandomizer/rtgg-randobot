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

When enabled, the seed is generated with a random 5 digit password consisting of
ocarina notes. This password is required to start a file in the generated seed.

Once this setting is enabled, Randobot will publish the password at the start of the
race countdown next to the seed hash in the race room information.

If the automated password acquiry after rolling the seed fails multiple times, manual acquiry 
can be attempted using `!password get`. Note that a race with a password activated seed can 
not be started without a password.


## !s7

Usable by: **race monitor/room opener**

Make use of a new Draft Mode fully integrated into the RaceTime room. Being
designed for the Season 7 Main Tournament, you may supply a number of arguments.

NOTE: When Draft Mode is active, commands such as !preset, !presetsdev, !lock,
etc. will be disabled. When Draft Mode is disabled, their functionality is
restored.

`!s7 tournament` - Used for S7 Bracket matches only. Randobot will check ZSR
for each runner's qualification status. If unqualified, Draft Mode will
automatically be disabled. Enables FPA and provides a full walkthrough for 
the draft process.

`!s7 <draft|random>` - Used for practice races. The `draft` argument will allow Randobot to assign 
the two runners with the most racetime.gg points as drafters and will walk them through the draft
process. The `random` argument will "simulate" a draft seed by randomly selecting a setting from each settings pool.
Runners will then use `!seed` to roll the seed and post the selected settings into the race room.

`!s7 qualifier` - Restricted to Race Moderators. Enables a special function
needed specificially for S7 Qualifier races. Similar to `!s7 random`, Randobot will "simulate" a draft seed
by randomly selecting a setting from each settings pool. Once invoked, race monitors
will be able to roll the seed with `!seed`. The race monitor will then use `!settings` to post the settings in
the race room 5 minutes before race start and lock the race room to prevent anyone else from joining.

`!s7 cancel` - Used to cancel the draft process with the ability to start over. If the
race is a bracket match and the settings have already been drafted, this will be limited 
to Race Moderators. FPA will automatically be disabled if enabled.

## !first

Usable by: **varies**

After enabling Draft Mode, RandoBot will assign a player as the higher-seeded player whether
based on qualifier placements or RaceTime points. This command allows that player the option
to pick first in the draft process.

## !second

Usable by: **varies**

Like `!first`, after enabling Draft Mode, RandoBot will assign a player as the higher-seeded player 
whether based on qualifier placements or RaceTime points. This command allows that player the option
to pick second in the draft process.

## !ban

Usable by: **varies**

Effectively "ban" a setting or force it to it's default value in the base S7 preset. RandoBot logically
handles player-turns through this command. Players each ban a single setting from "Major" setting group.
Available options can be viewed with `!settings`.

## !skip

Usable by: **varies**

Allows a player to skip removing a setting from the available settings pool during the banning phase.

## !pick

Usable by: **varies**

Effectively "pick" a setting and it's value following the format `!pick <setting> <value>`. Available 
options can be viewed with `!settings`. Values for a specific setting can be viewed with `!settings <setting>`.
Like with `!ban`, RandoBot logically handles player-turns. Each player picks a single setting from both the
"Major" and "Minor" settings pools, totally to two picks per player.

## !settings

Usable by: anyone

This command will have different return values depending on the state of the draft. During the banning phase,
it will provide players with a list of available options to select from. Players can view the default value of
a setting with `!settings <setting>`. During the pick phase, it will provide players with a list of options from
either the "Major" pool if picking a major setting, or the "Minor" pool if picking a minor setting. Players can
view specific values of a setting with `!settings <setting>`. If the draft process has already been completed,
it will return a list of all bans/picks made during the draft process.