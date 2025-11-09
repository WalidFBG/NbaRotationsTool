ARCHETYPES = {
    "archetypes": [
        {
            "id": "StarterCloserThreeStints",
            "name": "Starter, 3 on-stints, closer-capable",
            "starter": True,
            "stint_pattern": ["on", "off", "on", "off", "on"],
        },
        {
            "id": "StarterCloserFourStints",
            "name": "Starter, 4 on-stints, closer-capable",
            "starter": True,
            "stint_pattern": ["on", "off", "on", "off", "on", "off", "on"],
        },
        {
            "id": "StarterCloserFiveStints",
            "name": "Starter, 5 on-stints, closer-capable",
            "starter": True,
            "stint_pattern": ["on", "off", "on", "off", "on", "off", "on", "off", "on"],
        },
        {
            "id": "NonStarterNonCloserOneStint",
            "name": "Bench, single on-stint, non-closer",
            "starter": False,
            "stint_pattern": ["off", "on", "off"],
        },
        {
            "id": "NonStarterNonCloserTwoStints",
            "name": "Bench, 2 on-stints, non-closer",
            "starter": False,
            "stint_pattern": ["off", "on", "off", "on", "off"],
        },
        {
            "id": "NonStarterNonCloserThreeStints",
            "name": "Bench, 3 on-stints, non-closer",
            "starter": False,
            "stint_pattern": ["off", "on", "off", "on", "off", "on", "off"],
        },
        {
            "id": "NonStarterCloserThreeStints",
            "name": "Bench, 3 on-stints, closer-capable",
            "starter": False,
            "stint_pattern": ["off", "on", "off", "on", "off", "on"],
        },
        {
            "id": "NonStarterCloserFourStints",
            "name": "Bench, 4 on-stints, closer-capable",
            "starter": False,
            "stint_pattern": ["off", "on", "off", "on", "off", "on", "off", "on"],
        },
        {
            "id": "GarbageTime",
            "name": "Garbage Time (does not play)",
            "starter": False,
            "stint_pattern": ["off"],
        },
        {
            "id": "Star",
            "name": "Star (special rule must sub off at 12 and 36 min)",
            "starter": True,
            "stint_pattern": ["on", "off", "on", "off", "on"],
        },
    ]
}
