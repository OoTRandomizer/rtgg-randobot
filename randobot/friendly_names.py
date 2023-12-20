class FriendlyNames:
    draftables = {
        "bridge": {
            "__setting": "Rainbow Bridge",
            "open": "Open bridge, 6 med GCBK"
        },
        "deku": {
            "__setting":"Kokiri Forest",
            "open": "Open Forest",
        },
        "interiors": {
            "__setting":"Indoor Entrance Randomizer",
            "on": "Enabled",
        },
        "dungeons": {
            "__setting":"Dungeon Entrance Randomizer",
            "on": "Simple (no Ganon's Castle)",
        },
        "grottos": {
            "__setting":"Grotto Entrance Randomizer",
            "on": "Enabled",
        },
        "shops": {
            "__setting":"Shopsanity",
            "on": "4 items, random prices",
        },
        "ow_tokens": {
            "__setting":"Overworld Tokens",
            "on": "Shuffled",
        },
        "dungeon_tokens": {
            "__setting":"Dungeon Tokens",
            "on": "Shuffled",
        },
        "scrubs": {
            "__setting":"Scrub shuffle",
            "on": "Enabled, affordable prices",
        },
        "keys": {
            "__setting":"Small Keys",
            "keysy": "Keysy (dungeon small keys and boss keys removed)",
            "anywhere": "Keyrings anywhere (include Boss Keys)",
        },
        "required_only": {
            "__setting":"Reachable Locations",
            "on": "Required Only (aka Beatable Only)",
        },
        "fountain": {
            "__setting":"Zora's Fountain",
            "open": "Open Fountain",
        },
        "cows": {
            "__setting":"Cowsanity",
            "on": "Enabled",
        },
        "gerudo_card": {
            "__setting":"Shuffle Gerudo Card",
            "on": "Enabled",
        },
        "trials": {
            "__setting":"Ganon's Trials",
            "on": "3 Trials",
        },
        "door_of_time": {
            "__setting":"Door of Time",
            "closed": "Closed",
        },
        "starting_age": {
            "__setting":"Starting Age",
            "child": "Child",
            "adult": "Adult",
        },
        "random_spawns": {
            "__setting":"Random Spawns",
            "on": "Enabled",
        },
        "consumables": {
            "__setting":"Start with Consumables",
            "none": "Disabled",
        },
        "rupees": {
            "__setting":"Start with max Rupees",
            "startwith": "Enabled",
        },
        "cuccos": {
            "__setting":"Anju's Chickens",
            "1": "1 Cucco",
        },
        "free_scarecrow": {
            "__setting":"Free Scarecrow",
            "on": "Enabled",
        },
        "camc": {
            "__setting":"Chest Appearance Matches Contents",
            "off": "Disabled",
        },
        "mask_quest": {
            "__setting":"Mask Quest",
            "complete": "Complete, fast Bunny Hood disabled",
        },
        "blue_fire_arrows": {
            "__setting":"Blue Fire Arrows",
            "on": "Enabled",
        },
        "owl_warps": {
            "__setting":"Random Owl Warps",
            "random": "Enabled",
        },
        "song_warps": {
            "__setting":"Random Warp Song Destinations",
            "random": "Enabled",
        },
        "shuffle_beans": {
            "__setting":"Shuffle Magic Beans",
            "on": "Enabled",
        },
        "expensive_merchants": {
            "__setting":"Shuffle Expensive Merchants",
            "on": "Enabled",
        },
        "beans_planted": {
            "__setting":"Pre-planted Magic Beans",
            "on": "Enabled",
        },
        "bombchus_in_logic": {
            "__setting":"Bombchu Bag and Drops",
            "on": "Enabled (Bombchus in logic)",
        },
    }

    def __init__(self):
        pass

    def setting(self, setting):
        return self.draftables.get(setting).get("__setting") if setting in self.draftables else setting.capitalize()

    def option(self, setting, option):
        return self.draftables.get(setting).get(option) \
            if setting in self.draftables and option in self.draftables[setting] else option.capitalize()
