"""Turning one respondent's answers into the descriptive parts of the card.

Everything here returns small "template + bold parts" pairs so the renderer
can emphasise the right words, and so the same text can be flattened for alt
text and the post body.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from . import codes, geo
from .data import latest_value, latest, raw_code, text_value, value


@dataclass
class Span:
    """A sentence template with `{slot}` markers and the bold text for each slot."""
    template: str
    bold: dict[str, str] = field(default_factory=dict)

    def plain(self) -> str:
        return self.template.format(**self.bold)

    def as_dict(self) -> dict:
        return {"template": self.template, "bold": dict(self.bold)}


# Alternative wordings for fixed sentences - each as faithful to the question as the original.
# Picked per card with the card's seed, so the same person reads differently on a return visit.
VARIANTS: dict[str, tuple[str, ...]] = {
    "I own my home outright": ("I own my home, mortgage-free", "There's no mortgage on my home - I own it outright", "My home is bought and paid for, no mortgage"),
    "I'm paying off a mortgage": ("I've got a mortgage on my home", "I own my home with a mortgage", "I'm still paying the mortgage on my place"),
    "I rent privately": ("I rent from a private landlord", "I'm a private tenant", "The place I live in is a private rental"),
    "I rent from the council": ("I'm a council tenant", "I live in council housing", "My landlord is the council"),
    "I rent from a housing association": ("I'm a housing association tenant", "My landlord is a housing association", "I rent my place through a housing association"),
    "I live rent-free with family or friends": ("I live with family or friends and pay no rent", "I stay with family or friends and don't pay any rent", "I'm living with family or friends, rent-free"),
    "money has got a lot tighter this past year": ("I'm a lot worse off than I was a year ago", "my finances have got a lot worse over the last twelve months", "money's a good deal tighter than it was this time last year"),
    "money has got a bit tighter this past year": ("I'm a bit worse off than a year ago", "my finances have got a little worse over the last twelve months", "money's slightly tighter than it was this time last year"),
    "money is much the same as it was a year ago": ("my finances are about where they were a year ago", "financially, I'm no better or worse off than I was a year ago", "my finances have stayed much the same over the past year"),
    "money has got a little easier this past year": ("I'm a little better off than a year ago", "my finances have got a little better over the last twelve months", "money's slightly easier than it was this time last year"),
    "money has got a lot easier this past year": ("I'm a lot better off than I was a year ago", "my finances have got a lot better over the last twelve months", "money's a good deal easier than it was this time last year"),
    "I worry a lot about my family's financial security": ("I'm very worried about my family's finances", "I worry a great deal about whether my family will be financially secure", "my family's financial security is something I'm really worried about"),
    "I don't lose sleep over money": ("I'm not worried about my family's finances", "I've no real worries about my family's financial security", "I'm not someone who worries about money"),
    "I've no savings to fall back on": ("I've got no savings at all", "I haven't got any savings", "I've nothing put by in savings"),
    "I expect money to get a bit tighter over the next year": ("I think I'll be a bit worse off this time next year", "I reckon my finances will get a little worse over the next twelve months", "I expect to be slightly worse off a year from now"),
    "I expect money to get a lot tighter over the next year": ("I think I'll be a lot worse off this time next year", "I reckon my finances will get a lot worse over the next twelve months", "I expect to be a good deal worse off a year from now"),
    "I expect to be a lot better off this time next year": ("I expect money to get a lot easier over the next year", "I reckon my finances will get a lot better over the next twelve months", "I think I'll be a good deal better off a year from now"),
    "I've had to borrow money for essentials this year": ("I've borrowed money this year just to cover essentials", "I've needed to borrow to pay for bills and groceries this past year", "this last year I've had to borrow just to get by on the basics"),
    "I've got a degree": ("I'm a graduate", "I went to university and got my degree", "I've a degree to my name"),
    "I've got a postgraduate degree": ("I've done a postgraduate degree", "I stayed on after my degree and did a postgraduate qualification", "I've got a postgrad degree on top of my first one"),
    "I've got A-levels": ("My highest qualification is A-levels", "I finished school with A-levels", "A-levels are the top qualification I've got"),
    "I left school with GCSEs": ("GCSEs are my highest qualification", "I finished school with GCSEs", "I've got GCSEs and that's as far as my qualifications go"),
    "I left school with no qualifications": ("I've no formal qualifications", "I came out of school without any qualifications", "I haven't got any qualifications at all"),
    "I'm in a trade union": ("I'm a union member", "I belong to a trade union", "I'm a card-carrying union member"),
    "I'm a parent, though the kids have left home": ("My kids have grown up and left home", "I've got children, but they're grown up and moved out", "I'm a parent, but my kids have flown the nest"),
    "I follow politics closely": ("I keep a close eye on politics", "I pay a fair bit of attention to politics", "I keep up with politics pretty closely"),
    "I follow politics very closely": ("I keep a very close eye on politics", "I pay a great deal of attention to politics", "I keep up with politics very closely indeed"),
    "I keep half an eye on politics": ("I take a passing interest in politics", "I pay some attention to politics, but not loads", "I follow politics a bit, on and off"),
    "I don't pay much attention to politics": ("Politics mostly passes me by", "I don't really keep up with politics", "I take very little notice of politics"),
    "I don't follow the news about politics at all": ("I don't follow political news at all", "I don't take in any news about politics", "I don't keep up with political news in any way"),
    "The paper I read most is my local daily.": ("My paper is the local daily.", "The local daily is the paper I read most often.", "I read the local daily paper more than any other."),
    "The paper I read most is {paper}.": ("My paper is {paper}.", "I read {paper} more than any other paper.", "The daily paper I read most often is {paper}.", "When it comes to papers, I mostly read {paper}."),
}


def vary(text: str, rng: random.Random | None) -> str:
    """The sentence as written, or one of its alternatives, chosen with the card's seed."""
    options = (text,) + VARIANTS.get(text, ())
    return rng.choice(options) if rng and len(options) > 1 else text


def one_of(rng: random.Random | None, *wordings: str) -> str:
    """One of several wordings of the same fact, chosen with the card's seed (the first when there is no rng)."""
    return rng.choice(wordings) if rng and len(wordings) > 1 else wordings[0]


def lv(row, stem: str):
    """The most recent answer to a question that was asked in several waves."""
    return latest_value(row, stem)[0]


def article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def join_and(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


# ---------------------------------------------------------------------------
# Headline


def ethnicity_label(row, country: int) -> str | None:
    code = value(row, "p_ethnicity2W31")
    if code is None:
        return None
    code = int(code)
    birth = value(row, "p_country_birthW31")
    if code == 1:
        nation_col = {1: "englishnessW31", 2: "scottishnessW31", 3: "welshnessW31"}[country]
        nation, british = value(row, nation_col), value(row, "britishnessW31")
        if nation is not None and british is not None and nation > british:
            return f"White {codes.NATION_ADJECTIVE[country]}"
        return "White British"
    if code == 4:
        return "White European" if birth is not None and int(birth) in codes.EU_BIRTH_CODES else "White"
    if code in codes.BRITISH_PREFIX_CODES:
        base = codes.ETHNICITY[code]
        return f"British {base}" if birth is not None and int(birth) == 1 else base
    return codes.ETHNICITY.get(code)


def religion_label(row, country: int) -> str | None:
    code = value(row, "p_religionW31")
    if code is None:
        return None
    label = codes.RELIGION.get(int(code))
    if label == "Anglican" and country == codes.SCOTLAND:
        return "Episcopalian"
    return label


def headline(row, country: int, place: str, age: int) -> Span:
    gender = codes.GENDER[int(value(row, "gender"))]
    words = [w for w in (ethnicity_label(row, country), religion_label(row, country)) if w]
    slots = {}
    template_words = []
    for name, word in zip(("ethnicity", "religion"), words):
        slots[name] = word
        template_words.append("{" + name + "}")
    slots["gender"] = gender
    template_words.append("{gender}")
    first_word = words[0] if words else gender
    template = f"I'm {article(first_word)} " + " ".join(template_words) + " from {place}, aged {age}."
    slots["place"] = place
    slots["age"] = str(age)
    return Span(template, slots)


# ---------------------------------------------------------------------------
# Life paragraph: home and money, work and class, then one extra detail


def lower_first(text: str) -> str:
    """Lower-case a leading capital unless the sentence starts with the pronoun I."""
    if text.startswith(("I ", "I'")):
        return text
    return text[:1].lower() + text[1:]


def is_owner(row) -> bool:
    """Owner by the same source the tenure sentence uses: the wave-31 answer first, the profile variable only if that is missing."""
    tenure = value(row, "homeOwn2W31")
    if tenure is not None:
        return int(tenure) in (1, 2)
    return value(row, "p_housingW31") in (1, 2, 3)


def housing_clause(row, rng: random.Random | None = None) -> str | None:
    code = value(row, "homeOwn2W31")
    if code is not None and int(code) in codes.HOME_OWN2:
        return vary(codes.HOME_OWN2[int(code)], rng)
    code = value(row, "p_housingW31")
    if code is not None and int(code) in codes.P_HOUSING:
        return vary(codes.P_HOUSING[int(code)], rng)
    return None


def money_clause(row, rng: random.Random) -> str | None:
    """The most telling thing their answers say about money, in one clause."""
    options: list[str] = []
    if value(row, "borrowEssentialsW31") == 1:
        options.append("I've had to borrow money for essentials this year")
    if value(row, "smallEmergency2_5W31") == 1:
        options.append(one_of(rng, "an unexpected £300 bill would be beyond me", "I couldn't find £300 for an emergency right now", "if a £300 bill landed tomorrow, I couldn't cover it"))
    retro = value(row, "econPersonalRetroW31")
    if retro is not None:
        options.append({
            1: "money has got a lot tighter this past year",
            2: "money has got a bit tighter this past year",
            3: "money is much the same as it was a year ago",
            4: "money has got a little easier this past year",
            5: "money has got a lot easier this past year",
        }[int(retro)])
    worry = value(row, "worryEconSecurityW31")
    if worry is not None:
        if worry >= 8:
            options.append("I worry a lot about my family's financial security")
        elif worry <= 2:
            options.append("I don't lose sleep over money")
    poverty = value(row, "riskPovertyW31")
    if poverty == 5:
        options.append(one_of(rng, "I fully expect to run short of money at some point", "it's very likely there'll be times this year when I can't cover my day-to-day costs", "I'm pretty sure the money will run short at some point over the next year"))
    if value(row, "savingsW31") == 0:
        options.append("I've no savings to fall back on")
    savings_amount = value(row, "savingsAmtbW31")
    if savings_amount is not None and int(savings_amount) in codes.SAVINGS_BAND:
        options.append(one_of(rng, f"I've got {codes.SAVINGS_BAND[int(savings_amount)]} put by", f"I've {codes.SAVINGS_BAND[int(savings_amount)]} in savings", f"my savings come to {codes.SAVINGS_BAND[int(savings_amount)]}"))
        if savings_amount >= 13:
            options.append(one_of(rng, "I've got a decent cushion of savings", "I've a healthy amount of savings behind me", "I've got a good bit of money put away"))
    prospect = value(row, "econPersonalProspW31")
    if prospect == 1:
        options.append("I expect money to get a lot tighter over the next year")
    elif prospect == 2:
        options.append("I expect money to get a bit tighter over the next year")
    elif prospect == 5:
        options.append("I expect to be a lot better off this time next year")
    status = value(row, "workingStatusW31")
    if status in (1, 2, 3) and value(row, "riskUnemploymentW31") in (4, 5):
        options.append(one_of(rng, "I could well be out of a job within the year", "there's a real chance I'll be out of work and job-hunting this year", "I think it's likely I'll lose my job in the next twelve months"))
    if value(row, "smallEmergency2_5W31") != 1:
        for col, how in (("smallEmergency2_6W31", one_of(rng, "put it on the credit card", "stick it on a credit card and pay it off over time", "pay for it on a credit card")), ("smallEmergency2_4W31", one_of(rng, "borrow it from family or friends", "ask family or friends to lend it to me", "go to family or friends for the money")),
                         ("smallEmergency2_2W31", one_of(rng, "take out a loan", "get a loan to cover it", "borrow it from a lender")), ("smallEmergency2_3W31", one_of(rng, "sell something", "sell something I own", "flog something to raise the cash"))):
            if value(row, col) == 1:
                options.append(one_of(rng, f"an unexpected £300 bill would mean I'd have to {how}", f"if a £300 bill turned up out of the blue, I'd have to {how}", f"to cover a surprise £300 expense I'd need to {how}"))
    if not options:
        return None
    # hardship signals first; otherwise let chance pick among the rest for variety
    for hard in options[:2]:
        if hard.startswith(("I've had to borrow", "an unexpected")):
            return vary(hard, rng)
    choice = rng.choice(options)
    if choice.startswith("money is much the same") and rng.random() < 0.5:
        return None  # nothing much to say - leave it out half the time
    return vary(choice, rng)


def job_clause(row, rng: random.Random) -> str | None:
    """What they do for a living, using the occupational class codes in the data."""
    status = value(row, "workingStatusW31")
    nssec, _ = latest(row, ("ns_secW31", "ns_secW30", "ns_secW26W27W29", "ns_secW25", "ns_secW23",
                            "ns_secW22", "ns_secW21", "ns_secW20"))
    sector = value(row, "sectorW31")
    supervises = lv(row, "selfOccSupervise")
    job = codes.NSSEC_JOB.get(int(nssec)) if nssec is not None else None
    if status is None:
        return None
    status = int(status)

    def describe(verb_phrase: str, tense_past: bool = False) -> str:
        """The job with its sector; in the past tense the aside trails after a comma."""
        core, _, aside = verb_phrase.partition(" - ")
        if tense_past:
            core = (core.replace("have a", "had a").replace("have an", "had an").replace("am a", "was a")
                    .replace("am self-employed", "was self-employed").replace("run a", "ran a")
                    .replace("work for myself", "worked for myself").replace("work as", "worked as")
                    .replace("work in", "worked in").replace("do office", "did office"))
        if sector is not None and int(sector) in codes.SECTOR and "self" not in core and "run" not in core:
            core += " " + codes.SECTOR[int(sector)]
        return f"{core} ({aside})" if aside else core

    if status in codes.WORKING:
        hours = codes.WORKING[status]
        if job is None:
            return one_of(rng, f"I work {hours}", f"I'm working {hours}", f"I'm in paid work {hours}")
        if job.startswith(("run", "work for myself", "work as a self", "am self-employed")):
            sentence = f"I {describe(job)}".replace("I am ", "I'm ")
        else:
            sentence = one_of(rng, f"I work {hours} and {describe(job)}", f"I'm working {hours} and {describe(job)}", f"I {describe(job)}, working {hours}")
            size = lv(row, "selfOccOrgSize")
            if size == 1 and rng.random() < 0.5:
                sentence += one_of(rng, " at a small firm", " for a small employer", " at a place with under 25 staff")
            elif size == 3 and rng.random() < 0.5:
                sentence += one_of(rng, " at a place with 500-plus staff", " for a big employer with over 500 staff", " somewhere with more than 500 people on the books")
        if supervises == 1 and rng.random() < 0.5 and not any(w in job for w in ("supervis", "manage", "team leader", "run")):
            sentence += one_of(rng, ", supervising other people", ", and I'm responsible for other people's work", ", with people working under me")
        return sentence
    if status in codes.STUDENT:
        return codes.STUDENT[status]
    if status == 7:
        if nssec == codes.NSSEC_NEVER_WORKED:
            return one_of(rng, "I'm retired and never had a paid job", "I'm retired, and I was never in paid work", "I'm retired now and never had a paid job in my life")
        if not job:
            return one_of(rng, "I'm retired", "I've retired", "I'm retired now")
        frame = rng.choice((one_of(rng, "I'm retired - before that I {past}", "I'm retired - in my working days I {past}", "Before I retired, I {past}"), one_of(rng, "I'm retired now. In my working life I {past}", "I'm retired now. Back when I was working, I {past}", "These days, I'm retired, but when I was working I {past}")))
        return frame.format(past=describe(job, tense_past=True))
    if status == 4:
        if nssec == codes.NSSEC_NEVER_WORKED:
            return one_of(rng, "I'm looking for my first job", "I'm out of work and looking for my first ever job", "I've never had a job yet, and I'm looking for one")
        return one_of(rng, f"I'm out of work and looking for a job - before that I {describe(job, tense_past=True)}", f"I'm unemployed and job-hunting at the moment - before that I {describe(job, tense_past=True)}", f"I'm between jobs and looking for work. Before this I {describe(job, tense_past=True)}") if job \
            else one_of(rng, "I'm out of work and looking for a job", "I'm unemployed and looking for work", "I'm job-hunting at the moment, not in work")
    if status == 8:
        if nssec == codes.NSSEC_NEVER_WORKED:
            return one_of(rng, "I'm not in paid work and never have been", "I've never been in paid work", "I don't do paid work and never have done")
        return one_of(rng, f"I'm not in paid work at the moment - before that I {describe(job, tense_past=True)}", f"These days, I'm not in paid work - previously I {describe(job, tense_past=True)}", f"I'm not doing paid work right now. Before this I {describe(job, tense_past=True)}") if job \
            else one_of(rng, "I'm not in paid work at the moment", "I'm not doing paid work right now", "I'm not in a paid job just now")
    if status == 10:
        return one_of(rng, "I'm on furlough", "I've been furloughed", "I'm furloughed from my job")
    return None


CLASS_WAVES = ("W31", "W30", "W27W29", "W26", "W25", "W23", "W22", "W21", "W20")


def class_clause(row, rng: random.Random) -> tuple[str, str | None] | None:
    """Their own class, from the most recent wave they answered the top-up question in."""
    subj, col = latest(row, tuple(f"subjClass{w}" for w in CLASS_WAVES))
    if subj is None:
        return None
    wave = col[len("subjClass"):]
    squeeze = value(row, f"subjClassSqueeze{wave}")
    subj = int(subj)
    if subj in codes.CLASS_ID:
        return rng.choice(codes.CLASS_TEMPLATES), codes.CLASS_ID[subj]
    if subj == 3:
        return one_of(rng, "I think of myself as belonging to a class, just not middle or working class", "I do think of myself as belonging to a class, but not the middle or working class", "I'd say I belong to a class, though it's neither middle nor working class"), None
    if subj == 0:
        if squeeze is not None and int(squeeze) in codes.CLASS_ID:
            return one_of(rng, "I don't really think in class terms, but if pushed I'd say I'm {class_id}", "I don't think of myself as belonging to a class, but if I had to choose I'd say {class_id}", "Class isn't something I think about much, though if pushed I'd go with {class_id}"), codes.CLASS_ID[int(squeeze)]
        return one_of(rng, "I don't think of myself as belonging to any class", "I don't see myself as belonging to any particular class", "I wouldn't say I belong to any class"), None
    return None


def extra_clause(row, country: int, rng: random.Random) -> tuple[str, str] | None:
    """One more human detail, chosen at random from what they told us, tagged by theme (home, money, other)."""
    options: list[tuple[str, str]] = []
    marital = value(row, "p_maritalW31")
    children = value(row, "p_hh_childrenW31")
    kids = codes.CHILDREN.get(int(children)) if children is not None else None
    household = value(row, "p_hh_sizeW31")
    sexuality = value(row, "p_sexualityW31")
    gender = value(row, "gender")
    if marital is not None and int(marital) in codes.MARITAL:
        status = codes.MARITAL[int(marital)]
        if sexuality == 2:
            status = ("lesbian" if gender == 2 else "gay") + " and " + status
        elif sexuality == 3:
            status = "bisexual and " + status
        if kids:
            status += one_of(rng, f" with {'one child' if kids == 1 else f'{codes.NUMBER_WORDS[kids]} kids'} at home", f" and have {'one child' if kids == 1 else f'{codes.NUMBER_WORDS[kids]} kids'} living at home", f" with {'one child' if kids == 1 else f'{codes.NUMBER_WORDS[kids]} kids'} under my roof")
        elif household == 1 and int(marital) not in (1, 2, 4):  # a one-person household, unless they say they live with a partner
            status += one_of(rng, " and live on my own", " and I live alone", " and it's just me at home")
        elif kids == 0 and int(marital) in (1, 2, 4):
            status += one_of(rng, ", no kids at home", ", with no children at home", " and there are no kids living with us")
        options.append(("other", f"I'm {status}"))
    edu = value(row, "p_edlevelW31")
    if edu is not None:
        table = dict(codes.EDUCATION)
        if country == codes.SCOTLAND:
            table.update(codes.SCOTTISH_EDUCATION)
        options.append(("other", table[int(edu)]))
    birth = value(row, "p_country_birthW31")
    if birth is not None and int(birth) in codes.BIRTHPLACE:
        options.append(("other", one_of(rng, f"I was born in {codes.BIRTHPLACE[int(birth)]}", f"I'm originally from {codes.BIRTHPLACE[int(birth)]}", f"I was born abroad, in {codes.BIRTHPLACE[int(birth)]}")))
    union, _ = latest(row, ("currentUnionMemberW31", "currentUnionMemberW19_W26W29W30"))
    if union == 1:
        options.append(("other", "I'm in a trade union"))
    member = lv(row, "partyMemberOrSupporter")
    member_of = lv(row, "partyMemberNow")
    if member == 1 and member_of is not None and int(member_of) in codes.PARTY_SUPPORTER:
        options.append(("other", one_of(rng, f"I'm a paid-up member of the {codes.PARTY_SUPPORTER[int(member_of)]} party", f"I'm a card-carrying member of the {codes.PARTY_SUPPORTER[int(member_of)]} party", f"I'm signed up as a member of the {codes.PARTY_SUPPORTER[int(member_of)]} party")))
    elif member == 1:
        options.append(("other", one_of(rng, "I'm a paid-up member of a political party", "I'm a card-carrying member of a political party", "I'm signed up as a member of a political party")))
    shop = lv(row, "statusSupermarket")
    if shop is not None and int(shop) in codes.SUPERMARKET:
        options.append(("other", one_of(rng, f"I do most of my food shopping at {codes.SUPERMARKET[int(shop)]}", f"{codes.SUPERMARKET[int(shop)]} is where I do most of my food shopping", f"The grocery shopping is mostly done at {codes.SUPERMARKET[int(shop)]}")))
    attendance = lv(row, "churchAttendance")
    religion = value(row, "p_religionW31")
    if attendance is not None and religion is not None:
        religion = int(religion)
        place = "church" if religion in codes.CHRISTIAN_CODES else codes.PLACE_OF_WORSHIP.get(religion)
        if place and attendance == 6:
            options.append(("other", one_of(rng, f"I'm at {place} every week", f"I go to {place} every week", f"I'm at {place} at least once a week")))
        elif place and attendance in (4, 5):
            options.append(("other", one_of(rng, f"I get to {place} most months", f"I'm at {place} at least once a month", f"I go to {place} once or twice a month")))
    if lv(row, "sickElderlyInHouse") == 1:
        options.append(("other", one_of(rng, "I look after a sick or elderly relative at home", "There's a sick or elderly relative living with me that I care for", "I care for a sick or elderly relative who lives with me")))
    options += circumstance_details(row, country, rng)
    disability = value(row, "p_disabilityW31")
    if disability == 1:
        options.append(("other", one_of(rng, "I have a disability that limits my day-to-day life a lot", "I've a health problem or disability that limits what I can do day to day a lot", "My day-to-day activities are limited a lot by a disability")))
    elif disability == 2:
        options.append(("other", one_of(rng, "I have a health condition that limits me a little day to day", "I've a health problem that limits what I can do day to day a little", "My day-to-day activities are limited a bit by a health condition")))
    if lv(row, "disabilityChild") == 1:  # only a yes is ever shown; no and prefer-not-to-say stay private
        options.append(("other", one_of(rng, "one of my children has a long-term health condition or disability",
                                      "I've a child with a long-term health condition or disability",
                                      "one of my kids has a long-term illness or disability")))
    if value(row, "eligibleUKGEW31") == 0:
        options.append(("other", one_of(rng, "I'm not eligible to vote in general elections", "I can't vote in general elections", "general elections are one vote I'm not eligible to cast")))
    if lv(row, "privScndSchl") == 1:
        options.append(("other", one_of(rng, "I went to a private school", "I was privately educated at secondary level", "My secondary school was a private one")))
    welsh = lv(row, "speakWelsh")
    if welsh == 2:
        options.append(("other", one_of(rng, "I speak Welsh fluently", "I'm a fluent Welsh speaker", "Welsh is a language I speak fluently")))
    elif welsh == 1:
        options.append(("other", one_of(rng, "I speak a bit of Welsh", "I can speak some Welsh, but I'm not fluent", "I've got a bit of Welsh, not fluent though")))
    mother, father = lv(row, "motherVote2"), lv(row, "fatherVote2")
    parent_parties = {1: "Labour", 2: "Conservative", 3: "Liberal", 4: "SNP", 5: "Plaid Cymru", 12: "Reform"}
    if mother is not None and father is not None and int(mother) in parent_parties and int(father) in parent_parties:
        m, f = parent_parties[int(mother)], parent_parties[int(father)]
        options.append(("other", one_of(rng, f"my mum and dad both voted {m}", f"both my parents were {m} voters", f"my mum and dad were both {m} voters when I was growing up") if m == f else one_of(rng, f"my mum voted {m} and my dad {f}", f"growing up, my mum voted {m} and my dad voted {f}", f"my mum usually voted {m}, my dad {f}")))
    done = [codes.ACTIVITIES[c] for c in codes.ACTIVITIES if value(row, c) == 1]
    if len(done) >= 2:
        picks = rng.sample(done, k=min(3, len(done)))
        options.append(("other", one_of(rng, f"in the past year, I've {join_and(picks)}", f"over the last twelve months, I've {join_and(picks)}", f"since this time last year, I've {join_and(picks)}")))
    if not options:
        return None
    theme, text = rng.choice(options)
    return theme, vary(text, rng)


def circumstance_details(row, country: int, rng: random.Random) -> list[tuple[str, str]]:
    """The smaller facts of a life that the survey happens to record, each tagged home / money / other."""
    options: list[tuple[str, str]] = []
    alone = value(row, "p_hh_sizeW31") == 1  # "my household income" and "I've got two bedrooms" for a one-person household
    our, we_have = ("my", "I've got") if alone else ("our", "we've got")
    gender = value(row, "gender")
    age = value(row, "ageW31")
    kids = codes.CHILDREN.get(int(value(row, "p_hh_childrenW31") or 0))

    income = value(row, "p_gross_householdW31")
    if income is not None and int(income) in codes.INCOME_BAND:
        options.append(("money", one_of(rng, f"last time I was asked, {our} household income was {codes.INCOME_BAND[int(income)]} a year", f"when I was last asked, the household's income came to {codes.INCOME_BAND[int(income)]} a year", f"{our} household income, last time I gave it, was {codes.INCOME_BAND[int(income)]} a year")))
    home_value = lv(row, "homeAmtb")
    if is_owner(row) and home_value is not None and int(home_value) in codes.HOME_VALUE:
        band = codes.HOME_VALUE[int(home_value)]
        options.append(("home", one_of(rng, f"my home is worth {band}", f"my place would fetch {band}", f"I'd put the value of my home at {band}") if band.startswith(("over", "under")) else one_of(rng, f"my home is worth somewhere around {band}", f"I'd put my home's value at roughly {band}", f"my place would fetch something like {band}")))
    if lv(row, "inheritMoney") == 1:
        inherit = one_of(rng, "I'm expecting an inheritance that will change things for me", "I'm likely to inherit, and it'll make a big difference to my finances", "There's an inheritance coming my way that will be a major change for me financially") if lv(row, "inheritChangeCircs") == 1 else one_of(rng, "I'm expecting to inherit some money or property one day", "I'll probably come into some money or property at some point", "There's likely to be an inheritance for me down the line")
        options.append(("other", inherit))
    loan = lv(row, "homeFinance")
    if loan == 1:
        options.append(("other", one_of(rng, "nobody in my family could lend me a penny towards a house", "there's no one in my family who could lend or give me anything towards a house", "if I needed money for a house, my family couldn't put anything towards it")))
    elif loan is not None and int(loan) in codes.FAMILY_LOAN:
        options.append(("other", one_of(rng, f"my family could lend me {codes.FAMILY_LOAN[int(loan)]} towards a house if I needed it", f"if I needed it, someone in my family could put {codes.FAMILY_LOAN[int(loan)]} towards a house for me", f"my family could find me {codes.FAMILY_LOAN[int(loan)]} towards a house if it came to it")))
    buy = lv(row, "buyHomeFuture")
    if buy is not None and int(buy) in codes.BUY_HOME and value(row, "homeOwn2W31") in (3, 4, 5, 6):
        options.append(("home", codes.BUY_HOME[int(buy)]))
    bedrooms, garden = lv(row, "statusBedrooms"), lv(row, "statusGardenSize")
    if bedrooms is not None and int(bedrooms) in codes.BEDROOMS:
        home = one_of(rng, f"{we_have} {codes.BEDROOMS[int(bedrooms)]}", f"I've got {codes.BEDROOMS[int(bedrooms)]}", f"the place has {codes.BEDROOMS[int(bedrooms)]}")
        if garden is not None and int(garden) in codes.GARDEN:
            home += one_of(rng, f" with {codes.GARDEN[int(garden)]}", f" and {codes.GARDEN[int(garden)]}", f", plus {codes.GARDEN[int(garden)]}")
        elif lv(row, "statusHasGarden") == 0:
            home += one_of(rng, " and no garden", " but no garden", " with no garden")
        options.append(("home", home))

    left = value(row, "p_education_ageW31")
    if left is not None and int(left) in codes.LEFT_EDUCATION:
        options.append(("other", codes.LEFT_EDUCATION[int(left)]))
    if lv(row, "anyUni") == 2:
        options.append(("other", one_of(rng, "I started university but didn't finish", "I went to university but never completed it", "I did go to uni, though I dropped out before the end")))
    if value(row, "p_parentW31") == 1 and kids == 0 and age is not None and age >= 45:
        options.append(("other", "I'm a parent, though the kids have left home"))
    partner = lv(row, "workingStatusPartner")
    if partner is not None:
        partner_job = lv(row, "ns_sec_partner")
        job = codes.NSSEC_JOB.get(int(partner_job)) if partner_job is not None else None
        if partner == 7:
            options.append(("other", one_of(rng, "my partner's retired", "my other half is retired", "my partner has retired")))
        elif partner in (1, 2) and job:
            verb = one_of(rng, "works full-time", "is in full-time work", "has a full-time job") if partner == 1 else one_of(rng, "works part-time", "is in part-time work", "has a part-time job")
            options.append(("other", one_of(rng, f"my partner {verb} and {third_person(job.split(' - ')[0], 'they', singular=True)}", f"my other half {verb} and {third_person(job.split(' - ')[0], 'they', singular=True)}")))
        elif partner in (1, 2):
            options.append(("other", one_of(rng, "my partner works full-time", "my partner has a full-time job", "my partner's in full-time work") if partner == 1 else one_of(rng, "my partner works part-time", "my partner has a part-time job", "my partner's in part-time work")))
        elif partner == 4:
            options.append(("other", one_of(rng, "my partner's out of work at the moment", "my partner is unemployed and looking for work right now", "my other half is between jobs and looking for work")))
    if lv(row, "justIT") == 1:
        options.append(("other", one_of(rng, "my work is in IT", "I work in IT", "IT is the line of work I'm in")))
    elif lv(row, "cci") == 1:
        options.append(("other", one_of(rng, "my work is in the creative industries", "I work in the creative industries", "the creative industries are where I earn my living")))
    if lv(row, "voterIDpage1_111") == 1:
        options.append(("other", one_of(rng, "I've no passport or driving licence", "I don't hold a passport or a driving licence")))
    if lv(row, "registered") == 0:
        options.append(("other", one_of(rng, "I'm not on the electoral register", "I'm not registered to vote", "My name isn't on the electoral register")))

    faith = lv(row, "religImportant")
    religion = value(row, "p_religionW31")
    if faith == 4 and religion not in (None, 1):
        options.append(("other", one_of(rng, "my faith makes a great difference to my life", "my spiritual beliefs make a huge difference to how I live", "my religion makes a great deal of difference to my life")))
    elif faith == 1 and religion not in (None, 1, 16):
        options.append(("other", one_of(rng, "my religion doesn't make much difference to my day-to-day life", "my spiritual beliefs don't really affect my day-to-day life", "day to day, my religion doesn't make any real difference to my life")))
    if value(row, "belongGroup_2W26") == 1:
        options.append(("other", one_of(rng, "I feel a real sense of belonging to my local community", "I feel I really belong in my local community", "My local community is somewhere I feel a sense of belonging")))
    if country == codes.ENGLAND and raw_code(row, "belongGroup_6W26") == 1:
        options.append(("other", one_of(rng, "I feel a real sense of belonging to England", "I feel I really belong to England", "England is a place I feel I belong to")))

    if value(row, "careDuty_1_3W28") == 1:
        options.append(("other", one_of(rng, "I help support my grown-up children financially", "I've got financial responsibilities for my grown-up kids", "I'm helping my adult children out with money")))
    if value(row, "careDuty_3_2W28") == 1:
        options.append(("other", one_of(rng, "I look after my parents", "I've got caring responsibilities for my parents", "I'm a carer for my parents")))
    elif value(row, "careDuty_3_3W28") == 1:
        options.append(("other", one_of(rng, "I help my parents out financially", "I've got financial responsibilities for my parents", "My parents get financial help from me")))

    for col, text in (("participation_3W29", one_of(rng, "I had a poster up for the 2024 election", "I put an election poster up in 2024", "During the 2024 campaign, I displayed a poster")),
                      ("participation_2W29", one_of(rng, "I gave money to a party during the 2024 campaign", "I donated to a political party during the 2024 election campaign", "In the 2024 campaign, I put some money towards a party")),
                      ("participation_1W29", one_of(rng, "I did some campaigning for a party in 2024", "I did some work for a party or campaign group during the 2024 election", "In 2024 I helped out with a party's campaign"))):
        if value(row, col) == 1:
            options.append(("other", text))
    for col, text in (("nonelecParticipation_6W26", one_of(rng, "I've been on a demonstration", "I've taken part in a public demonstration", "I've been out on a protest")),
                      ("nonelecParticipation_8W26", one_of(rng, "I've been on strike", "I've taken industrial action", "I've taken strike action at work")),
                      ("nonelecParticipation_7W26", one_of(rng, "I've boycotted products for political reasons", "I've refused to buy certain products on political grounds", "I've boycotted products over politics or ethics")),
                      ("nonelecParticipation_1W26", one_of(rng, "I've written to a politician", "I've contacted a politician", "I've got in touch with a politician or official"))):
        if value(row, col) == 1:
            options.append(("other", text))

    risk = value(row, "riskScaleW20")
    if risk is not None and risk <= 2:
        options.append(("other", one_of(rng, "I'd take a sure thing over a gamble every time", "Give me a guaranteed payment over a gamble any day", "I'll always go for the safe bet rather than a gamble")))
    elif risk is not None and risk >= 12:
        options.append(("other", one_of(rng, "I'd take a gamble over a sure thing", "I'd rather take my chances than settle for a sure thing", "I'll gamble rather than take the safe option")))
    # Mini-IPIP personality items: life of the party / keep in the background; mood swings / relaxed;
    # vivid imagination and abstract ideas; chores done right away and liking order; sympathy for others
    for trait, high, low in (("extraversion", one_of(rng, "I'm an extrovert", "I'd describe myself as an extrovert", "I'm an outgoing sort of person"), one_of(rng, "I'm an introvert", "I'd describe myself as an introvert", "I'm the sort who keeps in the background, as I see it")),
                             ("neuroticism", one_of(rng, "I'm a worrier", "I'm someone who worries a lot", "I'd say I'm a worrier by nature"), one_of(rng, "not much rattles me", "I'm pretty relaxed most of the time", "I don't get rattled easily")),
                             ("openness", one_of(rng, "I've a vivid imagination and a taste for abstract ideas", "I've got a vivid imagination and I like abstract ideas", "I'm imaginative, and I enjoy getting into abstract ideas"), None),
                             ("conscientiousness", one_of(rng, "I'm organised and tidy", "I keep things tidy and organised", "I'm a tidy, organised person"), one_of(rng, "I'm not the tidiest or most organised person", "I'm not very tidy or organised", "Being organised and tidy isn't my strong point")),
                             ("agreeableness", one_of(rng, "I'm the sympathetic sort", "I'd describe myself as a sympathetic person", "I'm someone who feels for other people"), None)):
        score = value(row, f"big_five_{trait}", max_valid=21)
        if score is not None and score >= 17 and high:
            options.append(("other", high))
        elif score is not None and score <= 7 and low:
            options.append(("other", low))

    first_home = lv(row, "buyHouseYear")
    if first_home is not None and 1900 <= first_home <= 2026 and is_owner(row):
        options.append(("home", one_of(rng, f"I bought my first home in {int(first_home)}", f"I first owned a home back in {int(first_home)}", f"I got on the housing ladder in {int(first_home)}")))
    ladder = lv(row, "mapHouse")
    if ladder is not None and ladder <= 15:
        options.append(("other", one_of(rng, "a few years back I put my household among the poorest in the country", "a few years ago I rated my household as one of the poorest in the UK", "when asked a few years back, I put my household down near the poorest end in the country")))
    elif ladder is not None and ladder >= 85:
        options.append(("other", one_of(rng, "a few years back I put my household among the richest in the country", "a few years ago I rated my household as one of the richest in the UK", "when asked a few years back, I put my household up near the richest end in the country")))
    wealth = lv(row, "statusWealth")
    if wealth is not None and wealth <= 2:
        options.append(("other", one_of(rng, "on a ladder of wealth I'd put myself near the bottom", "for wealth, I'd place myself right down near the bottom of the ladder", "in terms of wealth I'd say I'm close to the bottom of the pile")))
    elif wealth is not None and wealth >= 9:
        options.append(("other", one_of(rng, "on a ladder of wealth I'd put myself near the top", "for wealth, I'd place myself right up near the top of the ladder", "in terms of wealth I'd say I'm close to the top of the pile")))
    standing = lv(row, "statusTopBottom")
    if standing is not None and standing <= 2:
        options.append(("other", one_of(rng, "I'd put myself near the bottom of the social ladder", "In society, I'd say I'm one of those near the bottom", "I'd place myself close to the bottom of the social scale")))
    elif standing is not None and standing >= 9:
        options.append(("other", one_of(rng, "I'd put myself near the top of the social ladder", "In society, I'd say I'm one of those near the top", "I'd place myself close to the top of the social scale")))
    # Need for cognition and empathy short scales
    if value(row, "nfc5W21") == 5 or value(row, "nfc2W21") == 5:
        options.append(("other", one_of(rng, "I love a problem that takes a lot of thinking", "I really enjoy a task where I have to work out new solutions", "Give me something that needs a lot of thinking and I'm happy")))
    elif value(row, "nfc3W21") == 5:
        options.append(("other", one_of(rng, "thinking isn't my idea of fun", "I don't find thinking hard about things much fun", "having to think a lot isn't my idea of a good time")))
    if value(row, "empathy2W20") == 4:
        options.append(("other", one_of(rng, "I can usually tell straight away when a friend is angry", "I'm quick to pick up on it when a friend is angry", "When a friend's angry, I usually realise right away")))
    elif value(row, "empathy8W20") in (3, 4):
        options.append(("other", one_of(rng, "other people's feelings don't bother me much", "I'm not much bothered by how other people are feeling", "other people's feelings don't really get to me")))
    # Who they could call on (social resources)
    rent = value(row, "resourceAccess3_4W20")
    if rent == 1:
        options.append(("other", one_of(rng, "I know someone who could lend me a month's rent if I needed it", "If I needed a month's rent, there's someone I could borrow it from", "I've got someone I could ask to lend me a month's rent or mortgage")))
    elif rent == 0:
        options.append(("other", one_of(rng, "I don't know anyone who could lend me a month's rent", "There's nobody I know who could lend me a month's rent", "If I needed a month's rent, I've no one I could borrow it from")))
    if value(row, "resourceAccess2_2W20") == 1:
        options.append(("other", one_of(rng, "I know a local councillor personally", "I personally know someone who's a local councillor", "One of the local councillors is someone I know")))
    if value(row, "resourceAccess3_8W20") == 0:
        options.append(("other", one_of(rng, "if I had to move, I don't know anyone who could help me find somewhere to live", "there's no one I could turn to for help finding a new place if I had to move", "I've nobody who could help me find somewhere to live if I had to move home")))
    if lv(row, "everUnionMember") == 1 and value(row, "currentUnionMemberW31") == 0:
        options.append(("other", one_of(rng, "I used to be in a trade union", "I was in a trade union once, but not any more", "I've been a union member in the past")))
    if value(row, "nonelecParticipation_4W26") == 1:
        options.append(("other", one_of(rng, "I've done work for a political party or campaign group", "I've put in some work for a political party or action group", "I've helped out a political party or campaign group")))
    if value(row, "nonelecParticipation_5W26") == 1:
        options.append(("other", one_of(rng, "I've given money to a political party or cause", "I've donated to a political party or cause", "I've put some money towards a party or a political cause")))

    earner = value(row, "headHouseholdPast")
    parent_job = value(row, "ns_sec_parent")
    if earner in (1, 2) and parent_job is not None and int(parent_job) in codes.NSSEC_JOB:
        job = codes.NSSEC_JOB[int(parent_job)].split(" - ")[0]
        past = third_person(job, "he" if earner == 1 else "she", past_tense=True)
        options.append(("other", one_of(rng, f"when I was 14, the main earner at home was {codes.MAIN_EARNER[int(earner)]}, who {past}", f"growing up, around 14, the main wage earner in our house was {codes.MAIN_EARNER[int(earner)]}, who {past}", f"the main wage earner at home when I was 14 was {codes.MAIN_EARNER[int(earner)]}, who {past}")))
    return options


def third_person(job: str, pronoun: str, past_tense: bool = False, singular: bool | None = None) -> str:
    """Turn a first-person NS-SEC job phrase ('have a skilled trade') into he/she/they form.

    `singular` forces singular verbs for a singular subject described with 'they'
    ("my partner ... has a skilled trade", not "have").
    """
    reflexive = {"he": "himself", "she": "herself", "they": "themselves"}[pronoun]
    singular = pronoun != "they" if singular is None else singular
    swaps = [
        (r"\bam self-employed\b", "was self-employed" if past_tense else ("is self-employed" if singular else "are self-employed")),
        (r"\bam a\b", "was a" if past_tense else ("is a" if singular else "are a")),
        (r"\bhave a\b", "had a" if past_tense else ("has a" if singular else "have a")),
        (r"\bhave an\b", "had an" if past_tense else ("has an" if singular else "have an")),
        (r"\brun a\b", "ran a" if past_tense else ("runs a" if singular else "run a")),
        (r"\bwork for myself\b", f"worked for {reflexive}" if past_tense else (f"works for {reflexive}" if singular else f"work for {reflexive}")),
        (r"\bwork as\b", "worked as" if past_tense else ("works as" if singular else "work as")),
        (r"\bwork in\b", "worked in" if past_tense else ("works in" if singular else "work in")),
        (r"\bdo office\b", "did office" if past_tense else ("does office" if singular else "do office")),
    ]
    for pattern, replacement in swaps:
        job = re.sub(pattern, replacement, job)
    return job


def join_clauses(first: str, second: str) -> str:
    """Two independent clauses on the same theme in one sentence, with a comma before the 'and'."""
    return first + ", and " + second


def life_paragraph(row, country: int, rng: random.Random) -> Span:
    """Home, money, work, one extra detail, then class - with each detail kept to its own theme.

    A description of the home itself (what it is worth, the bedrooms, when they
    first bought, whether they could buy) joins the tenure sentence; the income
    band joins the money sentence; everything else - including money-adjacent
    facts like an inheritance or who could lend them rent - gets a sentence of
    its own after work, so two unrelated thoughts are never run together.
    """
    bold: dict[str, str] = {}
    home = housing_clause(row, rng)
    money = money_clause(row, rng)
    work = job_clause(row, rng)
    theme, detail = extra_clause(row, country, rng) or (None, None)
    sentences: list[str] = []
    if home and detail and theme == "home":
        sentences.append(join_clauses(home, detail))
        detail = None
    elif home:
        sentences.append(home)
    if detail and theme == "money":
        sentences.append(join_clauses(detail, money) if money else detail)
        detail = None
    elif money:
        sentences.append(money)
    if work:
        sentences.append(work)
    if detail and sum(len(s) for s in sentences) < 190:
        sentences.append(detail)
    # Class comes last, as the closing thought after the facts of their life.
    cls = class_clause(row, rng)
    if cls:
        template, class_id = cls
        if class_id:
            bold["class_id"] = class_id
        sentences.append(template)
    return Span(" ".join(s[0].upper() + s[1:] + "." for s in sentences), bold)


# ---------------------------------------------------------------------------
# Media paragraph


def news_habit(row, rng: random.Random | None = None) -> str | None:
    """How much politics they take in, and through what."""
    scores = {col: value(row, col) for col in codes.NEWS_SOURCES}
    answered = {c: int(s) for c, s in scores.items() if s is not None}
    if answered:
        top = max(answered.values())
        if top <= 1:
            return vary("I don't follow the news about politics at all", rng)
        sources = [codes.NEWS_SOURCES[c] for c, s in answered.items() if s == top][:2]
        amount = {2: one_of(rng, ", a few minutes a day", ", less than half an hour a day", ", only a few minutes each day"), 3: one_of(rng, ", half an hour or so a day", ", somewhere between half an hour and an hour a day", ", a good half hour a day"), 4: one_of(rng, ", an hour or two a day", ", one to two hours a day", ", between one and two hours a day"), 5: one_of(rng, ", for hours every day", ", more than two hours a day", ", several hours a day")}[top]
        frame = rng.choice((one_of(rng, "I mostly follow politics {sources}{amount}", "I keep up with politics mainly {sources}{amount}", "Most of what I take in about politics is {sources}{amount}"), one_of(rng, "I get most of my politics {sources}{amount}", "The politics I take in is mostly {sources}{amount}", "For politics, I mostly rely on what I get {sources}{amount}"))) if rng else "I mostly follow politics {sources}{amount}"
        return frame.format(sources=join_and(sources), amount=amount)
    attention = value(row, "polAttentionW31")
    if attention is None:
        return None
    if attention <= 3:
        return vary("I don't pay much attention to politics", rng)
    if attention <= 6:
        return vary("I keep half an eye on politics", rng)
    if attention <= 8:
        return vary("I follow politics closely", rng)
    return vary("I follow politics very closely", rng)


def social_media(row, bold: dict[str, str], rng: random.Random | None = None) -> str | None:
    """What they use, and whether politics reaches them there (wave 28 follow-ups).

    Three honest states per platform: they saw political content on it; they said
    outright that they don't follow politics on it; or we only know they use it.
    """
    political, not_political, just_used, source_types = [], [], [], [0, 0, 0]
    answered = False
    for name, use_col, info_cols, (marker_col, marker_code) in codes.PLATFORMS:
        use = value(row, use_col)
        if use is None:
            continue
        answered = True
        if use != 1:
            continue
        hits = [value(row, c) == 1 for c in info_cols]
        if any(hits):
            political.append(name)
            for i, hit in enumerate(hits):
                source_types[i] += hit
        elif raw_code(row, marker_col) == marker_code:
            not_political.append(name)
        else:
            just_used.append(name)
    if not answered:
        return None
    if not (political or not_political or just_used):
        return one_of(rng, "I'm not on social media.", "I don't use social media.", "Social media isn't something I use.")

    def slots(names: list[str]) -> str:
        keys = []
        for name in names:
            key = f"platform{len(bold)}"
            bold[key] = name
            keys.append("{" + key + "}")
        return join_and(keys)

    def usage(names: list[str], also: bool = False) -> str:
        """'I use Facebook and Instagram, and watch YouTube.' - you watch YouTube, you use the rest."""
        others = [n for n in names if n != "YouTube"]
        watch = "YouTube" in names
        on = bool(rng and rng.random() < 0.5)  # "I'm on Facebook" reads as naturally as "I use Facebook"
        verb = (one_of(rng, "I'm also on", "I've also got an account on", "You'll also find me on") if on else one_of(rng, "I also use", "I also spend time on", "I also go on")) if also else (one_of(rng, "I'm on", "I've got an account on", "You'll find me on") if on else one_of(rng, "I use", "I spend time on", "I go on"))
        if others and watch:
            if len(others) >= 2:  # "I use Facebook, X and Instagram. I watch YouTube too." - never two "and"s in one sentence
                return one_of(rng, f"{verb} {slots(others)}. I watch {slots(['YouTube'])} too.", f"{verb} {slots(others)}. Then there's {slots(['YouTube'])}, which I watch.", f"{verb} {slots(others)}. I watch {slots(['YouTube'])} on top of that.")
            return one_of(rng, f"{verb} {slots(others)} and {'I ' if on else ''}watch {slots(['YouTube'])}.", f"{verb} {slots(others)}, and {'I ' if on else ''}watch {slots(['YouTube'])} as well.", f"{verb} {slots(others)} and {'I ' if on else ''}watch {slots(['YouTube'])} too.")
        if watch:
            return one_of(rng, f"I{' also' if also else ''} watch {slots(['YouTube'])}.", f"I{' also' if also else ''} spend time watching {slots(['YouTube'])}.", f"{slots(['YouTube'])} is something I{' also' if also else ''} watch.")
        return f"{verb} {slots(others)}."

    sentences = []
    if political:
        tail = ""
        best = max(source_types)
        if len(political) <= 2 and source_types.count(best) == 1:
            tail = ", " + codes.POLITICAL_SOURCE_TAIL[source_types.index(best)]
        sentences.append(one_of(rng, f"I get some of my politics from {slots(political)}{tail}.", f"Some of what I see about politics comes from {slots(political)}{tail}.", f"A bit of my political news reaches me via {slots(political)}{tail}."))
        rest = not_political + just_used
        if rest:
            sentences.append(usage(rest, also=True))
    else:
        sentences.append(usage(just_used + not_political))
    return " ".join(sentences)


def media_paragraph(row, country: int, rng: random.Random | None = None) -> Span | None:
    bold: dict[str, str] = {}
    sentences = []
    habit = news_habit(row, rng)
    if habit:
        sentences.append(habit + ".")
    paper = value(row, "p_paper_readW31")
    if paper is not None:
        paper = int(paper)
        if paper == codes.LOCAL_PAPER_CODE:
            sentences.append(vary("The paper I read most is my local daily.", rng))
        elif paper in codes.NEWSPAPER:
            name = codes.SCOTTISH_NEWSPAPER.get(paper, codes.NEWSPAPER[paper]) if country == codes.SCOTLAND else codes.NEWSPAPER[paper]
            bold["paper"] = "the " + name
            sentences.append(vary("The paper I read most is {paper}.", rng))
    social = social_media(row, bold, rng)
    if social:
        sentences.append(social)
    talk = talking_politics(row, rng)
    if talk:
        sentences.append(talk + ".")
    shared = shared_content(row, bold, rng)
    if shared and sum(len(s) for s in sentences) < 200:  # keep the paragraph to a few lines
        sentences.append(shared)
    if not sentences:
        return None
    return Span(" ".join(sentences), bold)


def talking_politics(row, rng: random.Random | None = None) -> str | None:
    """Wave 28: on how many days in the past week they discussed politics with others."""
    days = value(row, "discussPolDaysW28")
    if days is None:
        return None
    n = int(days)
    if n == 0:
        return one_of(rng, "I don't talk politics with people", "Politics isn't something I talk about with people", "I never get into politics with people")
    if n <= 2:
        return one_of(rng, "I talk politics with people now and then", "Politics comes up with people once or twice a week", "I get into politics with people a day or two a week")
    if n <= 4:
        return one_of(rng, "I talk politics a few days a week", "Politics comes up in conversation a few days a week", "I get into politics with people several days a week")
    return one_of(rng, "I talk politics most days", "Politics comes up in conversation nearly every day", "I get into politics with people almost daily")


SHARED_PLATFORMS = (("sharedContentOnline_1W28", "Facebook"), ("sharedContentOnline_2W28", "X"), ("sharedContentOnline_6W28", "YouTube"),
                    ("sharedContentOnline_7W28", "Instagram"), ("sharedContentOnline_8W28", "TikTok"))
SHARED_OTHER = (("sharedContentOnline_3W28", "by email"), ("sharedContentOnline_4W28", "over messaging apps"))


def shared_content(row, bold: dict[str, str], rng: random.Random | None = None) -> str | None:
    """Wave 28: where they shared political content during the 2024 campaign (platform names in bold)."""
    names = [name for col, name in SHARED_PLATFORMS if value(row, col) == 1]
    other = [how for col, how in SHARED_OTHER if value(row, col) == 1]
    if not names and not other:
        return None
    slots = []
    for name in names:
        key = f"shared{len(bold)}"
        bold[key] = name
        slots.append("{" + key + "}")
    if names:
        where = "on " + join_and(slots) + (", and " + join_and(other) if other else "")
        return one_of(rng, f"During the 2024 campaign, I shared political posts {where}.", f"I shared political content {where} during the 2024 election.",
                      f"In the 2024 campaign, I passed political posts on {where}.")
    return one_of(rng, f"During the 2024 campaign, I passed political content on {join_and(other)}.", f"I shared political content {join_and(other)} during the 2024 election.")


# ---------------------------------------------------------------------------
# Leaders, vote and band


def feeling(score: int, pronoun: str, rng: random.Random | None = None) -> str:
    """A 0-10 like/dislike rating as a plain clause: 'I really don't like him'."""
    if score <= 1:
        return one_of(rng, f"I can't stand {pronoun}", f"I've no time at all for {pronoun}", f"I can't bear {pronoun}")
    if score <= 3:
        return one_of(rng, f"I really don't like {pronoun}", f"I've very little time for {pronoun}", f"I'm really not keen on {pronoun}")
    if score == 4:
        return one_of(rng, f"I don't much like {pronoun}", f"I'm not that keen on {pronoun}", f"I don't think much of {pronoun}")
    if score == 5:
        return one_of(rng, f"I'm lukewarm about {pronoun}", f"I'm neither here nor there on {pronoun}", f"I could take or leave {pronoun}")
    if score == 6:
        return one_of(rng, f"I quite like {pronoun}", f"I'm fairly keen on {pronoun}", f"I've a bit of time for {pronoun}")
    if score <= 8:
        return one_of(rng, f"I like {pronoun}", f"I've got time for {pronoun}", f"I'm keen on {pronoun}")
    return one_of(rng, f"I really like {pronoun}", f"I've got a lot of time for {pronoun}", f"I rate {pronoun} very highly")


def leader_bubble(row, country: int, intention_party: int | None, rng: random.Random) -> Span:
    """Bubble 1, always about the leaders - falling back to a plain statement when ratings are thin."""
    scores = {}
    for col, (name, party, nations, _) in codes.LEADERS.items():
        if country in nations:
            score = value(row, col)
            if score is not None:
                scores[col] = score
    if not scores:  # nothing this wave: use last year's ratings of the leaders still in post
        for col, (name, party, nations, _) in codes.LEADERS.items():
            previous = col.replace("W31", "W30")
            if country in nations and col not in codes.NEW_LEADERS_W31:
                score = value(row, previous)
                if score is not None:
                    scores[col] = score
    if not scores:
        return Span(one_of(rng, "I don't have a view on any of the party leaders.", "I couldn't tell you what I think of any of the party leaders.", "I've no opinion on any of the party leaders."))
    if len(scores) == 1:
        (col, score), = scores.items()
        name = codes.LEADERS[col][0]
        return Span(one_of(rng, "The only leader I have a view on is {best}, and ", "{best} is the only leader I've an opinion on, and ", "Of the party leaders, {best} is the only one I can rate, and ") + feeling(int(score), codes.LEADERS[col][3], rng) + ".", {"best": name})
    if max(scores.values()) == min(scores.values()):
        n = int(max(scores.values()))
        if n <= 2:
            return Span(one_of(rng, "I can't stand any of the party leaders.", "I've no time at all for any of the party leaders.", "Every one of the party leaders puts me off."))
        if n <= 4:
            return Span(one_of(rng, "I don't much like any of the party leaders.", "I'm not that keen on any of the party leaders.", "I don't think much of any of the party leaders."))
        if n >= 7:
            return Span(one_of(rng, "I like all the party leaders about the same.", "I've got time for all the party leaders, and about the same for each.", "I like every one of the party leaders, and much the same amount."))
        return Span(one_of(rng, "I'm lukewarm about all the party leaders - none of them stands out.", "I could take or leave any of the party leaders - they're all much the same to me.", "I'm neither here nor there on the party leaders, and none of them stands out from the rest."))
    party_id = value(row, "partyIdW31")
    preferred = {intention_party, int(party_id) if party_id is not None else None}

    def pick(cols: list[str], want_preferred: bool) -> str:
        tied = [c for c in cols if (codes.LEADERS[c][1] in preferred) == want_preferred] or cols
        return rng.choice(tied)

    top = max(scores.values())
    bottom = min(scores.values())
    best = pick([c for c, s in scores.items() if s == top], want_preferred=True)
    worst = pick([c for c, s in scores.items() if s == bottom and c != best], want_preferred=False)
    best_name, worst_name = codes.LEADERS[best][0], codes.LEADERS[worst][0]
    bold = {"best": best_name, "worst": worst_name}
    if top <= 5:
        return Span(rng.choice((one_of(rng, "I don't much like any of the leaders - {best} comes closest. My least favourite is {worst}.", "I'm not keen on any of the leaders, though {best} is the nearest to it. {worst} is my least favourite.", "I don't think much of any of the leaders - {best} is the best of a bad lot, {worst} the worst."),
                                one_of(rng, "None of the leaders does much for me. {best} comes closest; {worst} comes last.", "I've not got much time for any of the leaders. {best} comes nearest; {worst} is bottom of the pile.", "None of the leaders really does it for me - {best} comes closest, and {worst} is last."))), bold)
    if bottom >= 5:
        return Span(rng.choice((one_of(rng, "I quite like all the leaders, {best} most of all. {worst} is my least favourite.", "I'm fairly keen on all the leaders, with {best} top of the list and {worst} at the bottom.", "There's none of the leaders I dislike - {best} is my favourite, {worst} my least favourite."),
                                one_of(rng, "I've a fair amount of time for all the leaders - {best} most, {worst} least.", "I've got some time for every one of the leaders, though {best} comes first and {worst} last.", "None of the leaders is bad in my book - I'd rank {best} highest and {worst} lowest."))), bold)
    return Span(rng.choice((one_of(rng, "My favourite leader is {best}. My least favourite is {worst}.", "Out of all the leaders, {best} is the one I like best, and {worst} the one I like least.", "Top of the leaders for me is {best}, bottom is {worst}."),
                            one_of(rng, "Of the party leaders, I like {best} most and {worst} least.", "When it comes to the party leaders, {best} is my pick and {worst} is my least favourite.", "I rate {best} highest of the party leaders and {worst} lowest."),
                            one_of(rng, "{best} is my favourite of the party leaders; {worst} is my least favourite.", "{best} is the leader I've most time for, {worst} the one I've least time for.", "If I had to rank the party leaders, {best} would be first and {worst} last."))), bold)


def vote_2024(row) -> tuple[str | None, str] | None:
    """(party name or None for non-voters, sentence) for the 2024 general election."""
    turnout = value(row, "p_turnout_2024")
    if turnout == 0:
        return None, "In 2024 I didn't vote."
    if turnout is None and raw_code(row, "p_turnout_2024") == 9999:
        return None, "I'm not sure whether I voted in 2024."
    vote = value(row, "p_past_vote_2024")
    if vote is None:
        if turnout == 1 and raw_code(row, "p_past_vote_2024") == 9999:
            return None, "I can't remember how I voted in 2024."
        if turnout == 1:
            return None, "In 2024 I voted."
        return None
    vote = int(vote)
    if vote == 0:
        return None, "In 2024 I didn't vote."
    if vote == 13:
        return "an independent", "In 2024 I voted for an independent."
    if vote == 9:
        return "another party", "In 2024 I voted for a smaller party."
    name = codes.PARTIES.get(vote)
    if name is None:
        return None
    return name, f"In 2024 I voted {name}."


RANKED_COLUMNS = {f"generalElectionRanked_{code}W31": code for code in (1, 2, 3, 4, 5, 7, 12, 9)}


def first_ranked_party(row) -> int | None:
    """Some respondents ranked the parties instead of naming one; the party ranked first."""
    ranks = {code: value(row, col) for col, code in RANKED_COLUMNS.items()}
    ranks = {code: r for code, r in ranks.items() if r is not None}
    if not ranks:
        return None
    return min(ranks, key=ranks.get)


def band(row) -> tuple[str, str | None] | None:
    """Footer text and the party whose colour the band takes (None for no colour)."""
    past = vote_2024(row)
    intention = value(row, "generalElectionVoteW31")
    if past is None:
        return None
    if intention is None and raw_code(row, "generalElectionVoteW31") is None:
        ranked = first_ranked_party(row)
        if ranked is None:
            return None
        past_party, past_sentence = past
        if ranked == 9:
            return f"{past_sentence} Today I'd rank a smaller party first*", None
        name = codes.PARTIES.get(ranked)
        return (f"{past_sentence} Today I'd rank {name} first*", name) if name else None
    if intention is None:
        return None
    past_party, past_sentence = past
    intention = int(intention)
    if intention == 0 and past_sentence == "In 2024 I didn't vote.":
        return non_voter_band(row)
    if intention == 0:
        return f"{past_sentence} Today I wouldn't vote*", None
    if intention == 13:
        return f"{past_sentence} Today I'd vote for an independent*", None
    if intention == 9:
        return f"{past_sentence} Today I'd vote for a smaller party*", None
    name = codes.PARTIES.get(intention)
    if name is None:
        return None
    if name == past_party:
        return f"{past_sentence} Today I still would*", name
    return f"{past_sentence} Today I'd vote {name}*", name


def non_voter_band(row) -> tuple[str, None]:
    """Someone who neither voted in 2024 nor would now: say so, plus the party they identify with if they gave one.

    The party comes from the party-identity question ("do you think of yourself
    as...") or its squeeze ("if you had to choose, which party do you feel
    closest to?"); the card's footnote is switched to say which.
    """
    direct = value(row, "partyIdW31")
    pushed = value(row, "partyIdSqueezeW31")
    if direct is not None and int(direct) in codes.PARTY_SUPPORTER:
        noun = codes.PARTY_SUPPORTER[int(direct)]
        return f"In 2024 I didn't vote. Today I wouldn't either, but I'm {article(noun)} {noun} supporter*", None
    if pushed is not None and int(pushed) in codes.PARTIES:
        return f"In 2024 I didn't vote. Today I wouldn't either - at a push, I'm closest to {codes.PARTIES[int(pushed)]}*", None
    return "In 2024 I didn't vote. Today I wouldn't either*", None


def dont_know_band(row) -> tuple[str, None] | None:
    """Band for people who answered 'don't know' to vote intention."""
    raw = row.get("generalElectionVoteW31")
    try:
        is_dk = int(float(raw)) == 9999
    except (TypeError, ValueError):
        return None
    if not is_dk:
        return None
    past = vote_2024(row)
    if past is None:
        return None
    return f"{past[1]} Today I don't know who I'd vote for*", None
