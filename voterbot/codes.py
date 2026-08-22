"""Lookup tables for BES codes: parties, leaders, demographics, occupations, issues.

Every table is keyed by the numeric code in the SPSS file (see the wave 31
codebook). Phrasing is first person, UK English, plain hyphens only.
"""

from __future__ import annotations

ENGLAND, SCOTLAND, WALES = 1, 2, 3
NATIONS = {ENGLAND: "England", SCOTLAND: "Scotland", WALES: "Wales"}
NATION_ADJECTIVE = {ENGLAND: "English", SCOTLAND: "Scottish", WALES: "Welsh"}

# generalElectionVote / p_past_vote_2024 / partyId codes -> short party name used in copy
PARTIES = {
    1: "Conservative",
    2: "Labour",
    3: "Lib Dem",
    4: "SNP",
    5: "Plaid Cymru",
    6: "UKIP",
    7: "Green",
    8: "BNP",
    11: "Change UK",
    12: "Reform UK",
}
PARTY_SUPPORTER = {  # "I'm a ... supporter"
    1: "Conservative", 2: "Labour", 3: "Lib Dem", 4: "SNP", 5: "Plaid Cymru",
    6: "UKIP", 7: "Green", 8: "BNP", 11: "Change UK", 12: "Reform",
}

# like<Leader>W31 columns: (display name, party code, nations asked)
LEADERS = {
    "likeStarmerW31": ("Keir Starmer", 2, (1, 2, 3), "him"),
    "likeBadenochW31": ("Kemi Badenoch", 1, (1, 2, 3), "her"),
    "likeFarageW31": ("Nigel Farage", 12, (1, 2, 3), "him"),
    "likeDaveyW31": ("Ed Davey", 3, (1, 2, 3), "him"),
    "likePolanskiW31": ("Zack Polanski", 7, (1, 3), "him"),
    "likeSwinneyW31": ("John Swinney", 4, (2,), "him"),
    "likeGreerW31": ("Ross Greer", 7, (2,), "him"),
    "likeMackayW31": ("Gillian Mackay", 7, (2,), "her"),
    "likeIorwerthW31": ("Rhun ap Iorwerth", 5, (3,), "him"),
    "likeMorganW31": ("Eluned Morgan", 2, (3,), "her"),
}

# (name, party code, nations asked, pronoun)
# Leaders whose wave-30 rating cannot stand in for wave 31 (new in post, or a different person held it)
NEW_LEADERS_W31 = {"likePolanskiW31", "likeGreerW31", "likeMackayW31"}

GENDER = {1: "man", 2: "woman"}

# p_ethnicity2 -> headline adjective. Code 1 and the British-Asian codes are
# refined in persona.py using national identity and country of birth.
ETHNICITY = {
    1: "White British",
    2: "White Irish",
    3: "Gypsy or Irish Traveller",
    4: "White",
    5: "Mixed White and Black Caribbean",
    6: "Mixed White and Black African",
    7: "Mixed White and Asian",
    8: "Mixed-heritage",
    9: "Indian",
    10: "Pakistani",
    11: "Bangladeshi",
    12: "Chinese",
    13: "Asian",
    14: "Black African",
    15: "Black Caribbean",
    16: "Black",
    17: "Arab",
}
BRITISH_PREFIX_CODES = {9, 10, 11, 12}  # "British Indian" etc. when UK-born

# p_religion -> headline adjective (None = leave out)
RELIGION = {
    1: "non-religious",
    2: "Anglican",
    3: "Catholic",
    4: "Presbyterian",
    5: "Methodist",
    6: "Baptist",
    7: "United Reformed",
    8: "Free Presbyterian",
    9: "Brethren",
    10: "Jewish",
    11: "Hindu",
    12: "Muslim",
    13: "Sikh",
    14: "Buddhist",
    15: None,  # "other" religion - nothing natural to say in one word
    16: None,
    17: "Orthodox Christian",
    18: "Pentecostal",
    19: "evangelical Christian",
}

# homeOwn2 (asked in the survey) and p_housing (YouGov profile) -> "I ..." clause
HOME_OWN2 = {
    1: "I own my home outright",
    2: "I'm paying off a mortgage",
    3: "I rent from the council",
    4: "I rent privately",
    5: "I rent from a housing association",
    6: "I live rent-free with family or friends",
}
P_HOUSING = {
    1: "I own my home outright",
    2: "I'm paying off a mortgage",
    3: "I part-own my home through shared ownership",
    4: "I rent privately",
    5: "I rent from the council",
    6: "I rent from a housing association",
    7: "I live with family and pay them a bit of rent",
    8: "I live rent-free with family",
}

# workingStatus
WORKING = {1: "full-time", 2: "part-time", 3: "a few hours a week"}
STUDENT = {5: "I'm a full-time university student", 6: "I'm a full-time student"}

# NS-SEC operational categories (ns_sec*) -> what the job is, in plain words.
# These are the occupational class codes that exist in the data; the survey does
# not release job titles. Examples are drawn from the official NS-SEC grouping.
NSSEC_JOB = {
    10: "run a large business",
    20: "have a senior management job",
    31: "have a higher professional job",
    32: "have a higher professional job",
    33: "work as a self-employed professional",
    34: "work as a self-employed professional",
    41: "have a professional or technical job",
    42: "have a professional or technical job",
    43: "am self-employed in a professional or technical line of work",
    44: "am self-employed in a professional or technical line of work",
    50: "have a management job",
    60: "have a senior supervisory job",
    71: "do office and admin work",
    72: "have a sales or customer service job",
    73: "have a technical support job",
    74: "work as an engineering technician",
    81: "run a small business",
    82: "run a small farm business",
    91: "work for myself",
    92: "work for myself in farming",
    100: "am a team leader",
    111: "have a skilled trade",
    112: "am a skilled process operative",
    121: "have a shop floor job",
    122: "have a semi-routine service job - care work etc.",
    123: "have a semi-routine technical job",
    124: "have a semi-routine operative job",
    125: "have a semi-routine farm job",
    126: "have a semi-routine clerical job",
    127: "work in childcare",
    131: "have a routine service job - cleaning, waiting tables etc.",
    132: "have a routine production job - factory work",
    133: "have a routine technical job",
    134: "have a routine operative job - driving, machine operating etc.",
    135: "have a routine farm job",
}
NSSEC_NEVER_WORKED = 141
NSSEC_LONG_TERM_UNEMPLOYED = 142

# sector (current or most recent job)
SECTOR = {
    1: "in the private sector",
    2: "for a public corporation",
    3: "in the public sector",
    4: "for a charity",
}

# subjClass / subjClassSqueeze
CLASS_ID = {1: "middle class", 2: "working class"}
CLASS_TEMPLATES = ("I'd call myself {class_id}", "I think of myself as {class_id}", "I'm {class_id}, I'd say",
                   "If you asked, I'd say I'm {class_id}", "Class-wise, I'd put myself down as {class_id}")

# p_marital
MARITAL = {
    1: "married",
    2: "in a civil partnership",
    3: "separated",
    4: "living with my partner",
    5: "in a relationship",
    6: "single",
    7: "divorced",
    8: "widowed",
}
# p_hh_children: code -> number of under-18s in the household
CHILDREN = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6}
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}

SEXUALITY = {2: "gay" , 3: "bisexual"}  # 2 = gay or lesbian; refined by gender

# p_edlevel
EDUCATION = {
    0: "I left school with no qualifications",
    1: "I left school before GCSEs",
    2: "I left school with GCSEs",
    3: "I've got A-levels",
    4: "I've got a degree",
    5: "I've got a postgraduate degree",
}
SCOTTISH_EDUCATION = {2: "I left school with Standard Grades", 3: "I've got Highers"}

# p_country_birth -> "born in ..." (1 = UK, left out)
BIRTHPLACE = {  # the BES categories, in their own words: "EU: pre-2004" / "EU: post-2004", "Oceania & Antarctica" etc.
    2: "Ireland", 3: "the EU", 4: "the EU", 5: "Europe, outside the EU", 6: "Africa",
    7: "East Asia", 8: "South-East or Central Asia", 9: "South Asia", 10: "North America",
    11: "the Caribbean or Central America", 12: "South America", 13: "Oceania", 14: "the Middle East",
}
EU_BIRTH_CODES = {3, 4, 5}

# p_paper_read -> name as people say it
NEWSPAPER = {
    1: "Express", 2: "Daily Mail", 3: "Mirror", 4: "Daily Star", 5: "Sun",
    6: "Telegraph", 7: "Financial Times", 8: "Guardian", 9: "Independent",
    10: "Times", 11: "Scotsman", 12: "Herald", 13: "Western Mail",
}
SCOTTISH_NEWSPAPER = {3: "Daily Record"}
LOCAL_PAPER_CODE = 14
NO_PAPER_CODE = 16

# infoSource<...>W29 columns -> how people say it
NEWS_SOURCES = {
    "infoSourceTVW29": "on TV",
    "infoSourceInternetW29": "online",
    "infoSourcePaperW29": "in the papers",
    "infoSourceRadioW29": "on the radio",
    "infoSourcePeopleW29": "by talking to people",
}
# Wave 28 platform questions: do you use it, and have you read political content
# there posted by (1) parties or candidates, (2) people you know, (3) commentators
# and journalists. "Not for politics" is only known when the person said so
# outright: code 9998 on the Facebook/X items, or the _111 tick-box for the rest.
# Fields: name, use column, the three source columns, the explicit "not politics" marker.
PLATFORMS = [
    ("Facebook", "fbUseW28", ("fbInfo_1W28", "fbInfo_2W28", "fbInfo_3W28"), ("fbInfo_1W28", 9998)),
    ("X", "twitterUseW28", ("twitterInfo_1W28", "twitterInfo_2W28", "twitterInfo_3W28"), ("twitterInfo_1W28", 9998)),
    ("YouTube", "socMedia_1W28", ("socMediaInfo_Youtube_1W28", "socMediaInfo_Youtube_2W28", "socMediaInfo_Youtube_3W28"), ("socMediaInfo_Youtube_111W28", 1)),
    ("Instagram", "socMedia_2W28", ("socMediaInfo_Instagram_1W28", "socMediaInfo_Instagram_2W28", "socMediaInfo_Instagram_3W28"), ("socMediaInfo_Instagram_111W28", 1)),
    ("TikTok", "socMedia_3W28", ("socMediaInfo_TikTok_1W28", "socMediaInfo_TikTok_2W28", "socMediaInfo_TikTok_3W28"), ("socMediaInfo_TikTok_111W28", 1)),
]
POLITICAL_SOURCE_TAIL = {0: "mostly from the parties themselves", 1: "mostly from people I know", 2: "mostly from commentators and journalists"}

# bestOnMII party codes as they read in a sentence
PARTY_NOUN = {1: "the Conservatives", 2: "Labour", 3: "the Lib Dems", 4: "the SNP", 5: "Plaid Cymru", 7: "the Greens", 12: "Reform UK"}

# statusActivities (wave 30) -> things done in the last 12 months
ACTIVITIES = {
    "statusActivities1_1W30": "visited a stately home",
    "statusActivities1_2W30": "been to a classical concert",
    "statusActivities1_3W30": "been horse riding",
    "statusActivities1_4W30": "gone for country walks",
    "statusActivities1_5W30": "watched modern dance",
    "statusActivities1_6W30": "done some fine dining",
    "statusActivities1_7W30": "been sailing",
    "statusActivities1_8W30": "played rugby",
    "statusActivities1_9W30": "eaten at a gastropub",
    "statusActivities1_10W30": "played football",
    "statusActivities1_11W30": "been to the bookies",
    "statusActivities1_12W30": "spent time on Facebook",
    "statusActivities1_13W30": "been to the pub",
    "statusActivities1_14W30": "had a bet online",
    "statusActivities1_15W30": "been to gigs",
    "statusActivities1_16W30": "played bingo",
    "statusActivities1_17W30": "watched the greyhounds",
    "statusActivities1_18W30": "read my horoscope",
    "statusActivities1_19W30": "eaten at McDonald's",
    "statusActivities2_1W30": "watched the BBC news",
    "statusActivities2_2W30": "been to the gym",
    "statusActivities2_3W30": "read books",
    "statusActivities2_4W30": "read about celebrities",
    "statusActivities2_5W30": "visited heritage sites",
    "statusActivities2_6W30": "played tennis",
    "statusActivities2_7W30": "been skiing",
    "statusActivities2_8W30": "watched reality TV",
    "statusActivities2_9W30": "played darts",
    "statusActivities2_10W30": "been to the ballet",
    "statusActivities2_11W30": "been to the theatre",
    "statusActivities2_12W30": "been to the opera",
    "statusActivities2_13W30": "done some gardening",
    "statusActivities2_14W30": "been to art galleries",
    "statusActivities2_15W30": "played video games",
    "statusActivities2_16W30": "been to rugby union matches",
    "statusActivities2_17W30": "done DIY",
    "statusActivities2_18W30": "been to football matches",
    "statusActivities2_19W30": "been to museums",
}

# statusSupermarket (wave 30)
SUPERMARKET = {1: "Aldi", 2: "Asda", 3: "the Co-op", 4: "Iceland", 5: "Lidl", 6: "Morrisons",
               7: "Sainsbury's", 8: "Tesco", 9: "Waitrose", 10: "M&S"}

# Place of worship by religion code, for the church attendance item
PLACE_OF_WORSHIP = {10: "synagogue", 11: "the temple", 12: "the mosque", 13: "the gurdwara", 14: "the temple"}
CHRISTIAN_CODES = {2, 3, 4, 5, 6, 7, 8, 9, 17, 18, 19}

# mii_cat_llm -> "My top issue is ..." (lower-case noun phrase). Missing codes are
# the uncodable ones (45 other, 46 uncoded, 47 referendum unspecified).
TOP_ISSUE = {
    1: "the NHS",
    2: "education",
    3: "the next election",
    4: "the state of our politics",
    5: "party politics",
    6: "division in society",
    7: "morals and values",
    8: "Britain losing its identity",
    9: "racism and discrimination",
    10: "welfare",
    11: "terrorism",
    12: "immigration",
    13: "asylum seekers",
    14: "crime",
    15: "Brexit and Europe",
    16: "constitutional reform",
    17: "trade",
    18: "devolution",
    19: "Scottish independence",
    21: "foreign affairs",
    22: "war",
    23: "defence",
    24: "a crisis abroad",
    25: "an emergency here at home",
    26: "the economy",
    27: "my own finances",
    28: "jobs and unemployment",
    29: "tax",
    30: "the national debt",
    31: "inflation",
    32: "the cost of living",
    33: "poverty",
    34: "cuts to public services",
    35: "inequality",
    36: "housing",
    37: "social care",
    38: "pensions",
    39: "transport and infrastructure",
    40: "the environment",
    41: "order, discipline and respect",
    42: "freedom and civil liberties",
    43: "the size of the state",
    44: "big business and the rich",
    48: "coronavirus",
    49: "the economic fallout of Covid",
    50: "gender and sexuality debates",
}

# ---------------------------------------------------------------------------
# Small details of background and circumstance

# p_gross_household (YouGov profile; collected whenever YouGov last asked, so the
# card says "last time I was asked"). Bands are the survey's own - no comparison
# to any external average.
INCOME_BAND = {
    1: "under £5,000", 2: "£5,000-£10,000", 3: "£10,000-£15,000", 4: "£15,000-£20,000", 5: "£20,000-£25,000",
    6: "£25,000-£30,000", 7: "£30,000-£35,000", 8: "£35,000-£40,000", 9: "£40,000-£45,000", 10: "£45,000-£50,000",
    11: "£50,000-£60,000", 12: "£60,000-£70,000", 13: "£70,000-£100,000", 14: "£100,000-£150,000", 15: "over £150,000",
}
# homeAmtb (wave 31)
HOME_VALUE = {
    1: "under £50,000", 2: "£50,000-£100,000", 3: "£100,000-£150,000", 4: "£150,000-£200,000", 5: "£200,000-£250,000",
    6: "£250,000-£300,000", 7: "£300,000-£400,000", 8: "£400,000-£500,000", 9: "£500,000-£600,000", 10: "£600,000-£700,000",
    11: "£700,000-£800,000", 12: "£800,000-£900,000", 13: "£900,000-£1 million", 14: "over £1 million",
}
# savingsAmtb (wave 31)
SAVINGS_BAND = {
    1: "under £100", 2: "£100-£500", 3: "£500-£1,000", 4: "£1,000-£2,000", 5: "£2,000-£3,000", 6: "£3,000-£5,000",
    7: "£5,000-£10,000", 8: "£10,000-£15,000", 9: "£15,000-£20,000", 10: "£20,000-£30,000", 11: "£30,000-£40,000",
    12: "£40,000-£50,000", 13: "£50,000-£75,000", 14: "£75,000-£100,000", 15: "£100,000-£150,000", 16: "£150,000-£200,000",
    17: "over £200,000",
}
# homeFinance: what family could lend or give towards a house
FAMILY_LOAN = {
    2: "less than £5,000", 3: "£5,000-£10,000", 4: "£10,000-£25,000", 5: "£25,000-£50,000", 6: "£50,000-£75,000",
    7: "£75,000-£100,000", 8: "£100,000-£150,000", 9: "£150,000-£200,000", 10: "£200,000 or more",
}
# buyHomeFuture (renters, waves 25-26)
BUY_HOME = {
    1: "I've no wish to buy a home",
    2: "I don't expect to be able to buy a home in the next ten years",
    3: "I reckon I'll be able to buy with a mortgage in the next few years",
    4: "I expect to be able to buy a home outright in the next few years",
}
# p_education_age
LEFT_EDUCATION = {1: "I left school at 15 or younger", 2: "I left school at 16", 3: "I left school at 17 or 18",
                  4: "I finished education at 19", 5: "I stayed in education past 20"}
# statusGardenSize / statusBedrooms (wave 30)
GARDEN = {1: "a balcony for a garden", 2: "a small garden", 3: "a garden about the size of a tennis court",
          4: "a garden the size of a couple of tennis courts", 5: "a big garden", 6: "a very big garden"}
BEDROOMS = {1: "a one-bedroom place", 2: "a two-bedroom place", 3: "a three-bedroom place", 4: "a four-bedroom place",
            5: "a five-bedroom place", 6: "a place with six or more bedrooms"}
# headHouseholdPast
MAIN_EARNER = {1: "my dad", 2: "my mum"}
# riskScale (wave 20): 1 most risk averse ... 16 most risk inclined
# big five mini-IPIP scores run 4-20; anything at 17+ or 7 and under is a clear trait

# reasonNonVoter (May 2026 local elections)
NONVOTE_REASON = {
    1: "I forgot", 2: "I wasn't interested", 3: "I was too busy", 4: "I didn't like any of the choices",
    5: "I wasn't registered", 6: "I didn't have the right photo ID", 7: "I was away", 8: "I was unwell",
    9: "I couldn't get to the polling station", 10: "the weather was too bad", 11: "the queue was too long",
    12: "I was turned away at the polls", 13: "my postal ballot never arrived", 15: "I didn't know where to vote",
    16: "I didn't feel I knew enough about the choices",
}
# May 2026 devolved elections: Holyrood ballots use their own party codes
SCOTTISH_PARTY = {1: "Labour", 2: "Conservative", 3: "Lib Dem", 4: "SNP", 6: "Green", 9: "another party", 12: "Reform UK"}
SENEDD_PARTY = {1: "Conservative", 2: "Labour", 3: "Lib Dem", 5: "Plaid Cymru", 7: "Green", 9: "another party", 12: "Reform UK"}

# like<Party>W31 columns for the most/least liked party bubble
PARTY_LIKES = {
    "likeConW31": ("the Conservatives", (1, 2, 3)), "likeLabW31": ("Labour", (1, 2, 3)), "likeLDW31": ("the Lib Dems", (1, 2, 3)),
    "likeGrnW31": ("the Greens", (1, 2, 3)), "likeBrexitPartyW31": ("Reform UK", (1, 2, 3)),
    "likeSNPW31": ("the SNP", (2,)), "likePCW31": ("Plaid Cymru", (3,)),
}
PARTY_UNITY = {"conUnitedW31": "The Conservatives", "labUnitedW31": "Labour", "ldUnitedW31": "The Lib Dems",
               "grnUnitedW31": "The Greens", "brexitUnitedW31": "Reform UK", "snpUnitedW31": "The SNP", "pcUnitedW31": "Plaid Cymru"}
LOOKS_AFTER = {  # column -> (party, group)
    "conLookAfterWCW31": ("The Conservatives", "working-class people"), "labLookAfterWCW31": ("Labour", "working-class people"),
    "brexitLookAfterWCW31": ("Reform UK", "working-class people"), "labLookAfterYoungW31": ("Labour", "young people"),
    "conLookAfterRetiredW31": ("The Conservatives", "retired people"), "brexitLookAfterMCW31": ("Reform UK", "middle-class people"),
}
