"""Shared 2026 World Cup data for model training and prediction.

Keep the tournament snapshot in one place so backtests, training, and ad-hoc
prediction scripts do not drift apart.
"""

ELO = {
    "Mexico": 1890, "South Africa": 1720, "Korea": 1785, "Czechia": 1800,
    "Canada": 1870, "Bosnia": 1775, "Qatar": 1640, "Switzerland": 1891,
    "Brazil": 1991, "Morocco": 1860, "Haiti": 1480, "Scotland": 1780,
    "USA": 1860, "Paraguay": 1730, "Australia": 1720, "Turkiye": 1850,
    "Germany": 1960, "Curacao": 1500, "Cote dIvoire": 1820, "Ecuador": 1850,
    "Netherlands": 1970, "Japan": 1840, "Sweden": 1810, "Tunisia": 1720,
    "Belgium": 1930, "Egypt": 1628, "Iran": 1810, "New Zealand": 1500,
    "Spain": 2157, "Cabo Verde": 1620, "Saudi Arabia": 1660, "Uruguay": 1920,
    "France": 2063, "Senegal": 1880, "Iraq": 1620, "Norway": 1880,
    "Argentina": 2115, "Algeria": 1800, "Austria": 1820, "Jordan": 1640,
    "Portugal": 1989, "DR Congo": 1700, "Uzbekistan": 1690, "Colombia": 1982,
    "England": 2024, "Croatia": 1900, "Ghana": 1750, "Panama": 1640,
}

HOME = 85

# (home, away, hg, ag, host_home, batch)
# batch: 0=orig40, 1=Jun22 oos for v3.3, 2=Jun23 oos for v3.4, 3=Jun24 oos for v3.5
MATCHES_54 = [
    ("Mexico", "South Africa", 2, 0, 1, 0),
    ("Korea", "Czechia", 2, 1, 0, 0),
    ("Mexico", "Korea", 1, 0, 1, 0),
    ("South Africa", "Czechia", 1, 1, 0, 0),
    ("Qatar", "Switzerland", 1, 1, 0, 0),
    ("Canada", "Bosnia", 1, 1, 1, 0),
    ("Switzerland", "Bosnia", 4, 1, 0, 0),
    ("Canada", "Qatar", 6, 0, 1, 0),
    ("Brazil", "Morocco", 1, 1, 0, 0),
    ("Scotland", "Haiti", 1, 0, 0, 0),
    ("Morocco", "Scotland", 1, 0, 0, 0),
    ("Brazil", "Haiti", 3, 0, 0, 0),
    ("USA", "Paraguay", 4, 1, 1, 0),
    ("Australia", "Turkiye", 2, 0, 0, 0),
    ("USA", "Australia", 2, 0, 1, 0),
    ("Paraguay", "Turkiye", 1, 0, 0, 0),
    ("Germany", "Curacao", 7, 1, 0, 0),
    ("Cote dIvoire", "Ecuador", 1, 0, 0, 0),
    ("Germany", "Cote dIvoire", 2, 1, 0, 0),
    ("Ecuador", "Curacao", 0, 0, 0, 0),
    ("Netherlands", "Japan", 2, 2, 0, 0),
    ("Sweden", "Tunisia", 5, 1, 0, 0),
    ("Netherlands", "Sweden", 5, 1, 0, 0),
    ("Japan", "Tunisia", 4, 0, 0, 0),
    ("Belgium", "Egypt", 1, 1, 0, 0),
    ("Iran", "New Zealand", 2, 2, 0, 0),
    ("Belgium", "New Zealand", 5, 1, 0, 0),
    ("Egypt", "Iran", 1, 1, 0, 0),
    ("Spain", "Cabo Verde", 0, 0, 0, 0),
    ("Saudi Arabia", "Uruguay", 1, 1, 0, 0),
    ("Spain", "Uruguay", 1, 0, 0, 0),
    ("Cabo Verde", "Saudi Arabia", 0, 0, 0, 0),
    ("France", "Senegal", 3, 1, 0, 0),
    ("Norway", "Iraq", 4, 1, 0, 0),
    ("Argentina", "Algeria", 3, 0, 0, 0),
    ("Austria", "Jordan", 3, 1, 0, 0),
    ("Portugal", "DR Congo", 1, 1, 0, 0),
    ("Colombia", "Uzbekistan", 3, 1, 0, 0),
    ("England", "Croatia", 4, 2, 0, 0),
    ("Ghana", "Panama", 1, 0, 0, 0),
    ("France", "Iraq", 3, 0, 0, 1),
    ("Norway", "Senegal", 3, 2, 0, 1),
    ("Argentina", "Austria", 2, 0, 0, 1),
    ("Algeria", "Jordan", 2, 1, 0, 1),
    ("Portugal", "Uzbekistan", 5, 0, 0, 2),
    ("Colombia", "DR Congo", 1, 0, 0, 2),
    ("England", "Ghana", 0, 0, 0, 2),
    ("Panama", "Croatia", 0, 1, 0, 2),
    ("Mexico", "Czechia", 3, 0, 1, 3),
    ("South Africa", "Korea", 1, 0, 0, 3),
    ("Canada", "Switzerland", 1, 3, 1, 3),
    ("Bosnia", "Qatar", 3, 1, 0, 3),
    ("Brazil", "Scotland", 3, 0, 0, 3),
    ("Morocco", "Haiti", 4, 2, 0, 3),
]

# (home, away, host_home, heat, mot_home, mot_away, venue_note)
JUNE_25_MATCHES = [
    ("USA", "Turkiye", 1, "none", "through", "eliminated",
     "SoFi (roof, LA) - USA de-facto home and through; Turkiye out"),
    ("Paraguay", "Australia", 0, "none", "mustwin", "mustwin",
     "Levi's, Santa Clara (mild eve) - winner advances"),
    ("Curacao", "Cote dIvoire", 0, "mild", "mustwin", "normal",
     "Lincoln Financial, Philadelphia (~30C, 4pm ET)"),
    ("Ecuador", "Germany", 0, "mild", "mustwin", "through",
     "MetLife, NJ (~30C, 4pm ET) - Germany through, may rotate"),
    ("Japan", "Sweden", 0, "none", "normal", "normal",
     "AT&T Arlington (roof, AC) - both still alive"),
    ("Tunisia", "Netherlands", 0, "moderate", "eliminated", "through",
     "Arrowhead, Kansas City (~33C eve) - Tunisia out, NL top"),
]

BATCH_SPLITS = {
    "train": (0,),
    "validation": (1, 2),
    "locked_test": (3,),
}

BATCH_NAMES = {
    0: "orig40",
    1: "jun22_oos",
    2: "jun23_oos",
    3: "jun24_oos",
}


def matches_for_batches(*batches):
    wanted = set(batches)
    return [m for m in MATCHES_54 if m[5] in wanted]


def split_matches():
    return {name: matches_for_batches(*batches) for name, batches in BATCH_SPLITS.items()}
