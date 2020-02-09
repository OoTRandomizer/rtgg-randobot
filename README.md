# ootr-randobot

A [racetime.gg](https://racetime.gg) chat bot application for automatically 
generating [OoT Randomizer](https://ootrandomizer.com/) seeds in race rooms.

## How to get started

**Note:** This bot is intended for private use only. The code is provided here
for example purposes and transparency, however you may only use the APIs this
bot connects to if you are a trusted enough to be given the keys. It is not
possible to use this bot without suitable API access.

### Requirements

* Python 3.7 or greater.

### Installation

1. Clone the repo
1. Install the package using `pip install -e .` (from the repo's base
   directory).
   
### Usage

Run `randobot <ootr_api_key> <category_slug> <client_id> <client_secret>`,
where:

* `<ootr_api_key>` is a valid API key for ootrandomizer.com (note: this is
  a private API, access is limited to trusted individuals).
* `<category_slug>` is the slug of the racetime.gg category the bot should
  operate in, i.e. `ootr`
* `<client_id>` is the OAuth2 client ID for this bot on racetime.gg
* `<client_secret>` is the OAuth2 client secret for this bot on racetime.gg
