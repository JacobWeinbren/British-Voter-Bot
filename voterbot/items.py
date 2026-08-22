"""The opinion library: survey items turned into first-person speech bubbles.

Each `Item` knows which columns hold the answer (most recent wave first), which
nations it applies to, a topic (so one card never carries two bubbles on the
same subject) and how to phrase each answer. Neutral answers usually return
None so bubbles carry an actual view.

House style: UK spelling, plain hyphens, short sentences, no more than about
90 characters, and nothing a real person would not say out loud.
"""

from __future__ import annotations

import re

from collections.abc import Callable
from dataclasses import dataclass, field

from . import codes
from .data import fieldings, latest, value

Phraser = Callable[[float], "str | tuple[str, ...] | None"]  # a tuple offers alternative wordings of the same answer
ALL = (1, 2, 3)


@dataclass(frozen=True)
class Item:
    key: str
    topic: str
    cols: tuple[str, ...]
    phrase: Phraser | None = None          # simple items: code -> sentence
    custom: Callable | None = None         # complex items: (row, country) -> sentence
    nations: tuple[int, ...] = ALL
    weight: float = 1.0
    max_valid: float = 9000
    fallback: bool = True                  # fall back through every earlier fielding (wave 20 on) of the same question

    def columns(self, row) -> tuple[str, ...]:
        """The listed columns, then every other fielding of the same questions, most recent first."""
        if not self.fallback:
            return self.cols
        extra = [c for col in self.cols for c in fieldings(row.index, _stem(col)) if c not in self.cols]
        return tuple(self.cols) + tuple(dict.fromkeys(extra))

    def statement(self, row, country: int) -> str | None:
        if country not in self.nations:
            return None
        if self.custom is not None:
            return self.custom(row, country)
        answer, _ = latest(row, self.columns(row), self.max_valid)
        if answer is None:
            return None
        return self.phrase(answer)


def _stem(column: str) -> str:
    return re.sub(r"W\d+(?:_?W\d+)*$", "", column)


# ---------------------------------------------------------------------------
# Phrasing helpers


def by_code(mapping: dict[int, str]) -> Phraser:
    return lambda answer: mapping.get(int(answer))


def agree5(strong_agree: str, agree: str, disagree: str, strong_disagree: str, neither: str | None = None) -> Phraser:
    """Five-point agree scale: 1 strongly disagree ... 5 strongly agree."""
    return by_code({5: strong_agree, 4: agree, 3: neither, 2: disagree, 1: strong_disagree})


def scale11(low_strong: str, low_lean: str, high_lean: str, high_strong: str, middle: str | None = None) -> Phraser:
    """0-10 scale bucketed into strong/lean either side of the midpoint."""
    def phrase(answer: float) -> str | None:
        n = int(answer)
        if n <= 2:
            return low_strong
        if n <= 4:
            return low_lean
        if n == 5:
            return middle
        if n <= 7:
            return high_lean
        return high_strong
    return phrase


def too_far5(much_too_far: str, too_far: str, about_right: str, not_far_enough: str, nowhere_near: str) -> Phraser:
    """'Gone too far' scale: 1 not nearly far enough ... 5 gone much too far."""
    return by_code({5: much_too_far, 4: too_far, 3: about_right, 2: not_far_enough, 1: nowhere_near})


def worse_better5(lot_worse: str, little_worse: str, little_better: str, lot_better: str) -> Phraser:
    return by_code({1: lot_worse, 2: little_worse, 4: little_better, 5: lot_better})


def handling5(subject: str) -> Phraser:
    return by_code({
        1: (f"The government is handling {subject} very badly.", f"The government is making a real mess of {subject}."),
        2: f"The government is handling {subject} fairly badly.",
        4: f"The government is handling {subject} fairly well.",
        5: (f"The government is handling {subject} very well.", f"The government is doing a very good job on {subject}."),
    })


def fair_share5(who: str, of_what: str = "from the Union") -> Phraser:
    return by_code({
        1: (f"{who} gets much less than its fair share {of_what}.", f"{who} gets nowhere near its fair share {of_what}."),
        2: f"{who} gets a little less than its fair share {of_what}.",
        3: f"{who} gets more or less its fair share {of_what}.",
        4: f"{who} gets a little more than its fair share {of_what}.",
        5: (f"{who} gets much more than its fair share {of_what}.", f"{who} gets far more than its fair share {of_what}."),
    })


def approve5(who: str) -> Phraser:
    return by_code({
        1: (f"I strongly disapprove of {who}'s record.", f"I think {who} is doing a very bad job."),
        2: f"I disapprove of how {who} is doing.",
        4: f"I approve of how {who} is doing.",
        5: (f"I strongly approve of {who}'s record.", f"I think {who} is doing a very good job."),
    })


def marry5(voter: str) -> Phraser:
    return by_code({
        1: f"I'd be very unhappy if my child married {voter}.",
        2: f"I'd be a bit unhappy if my child married {voter}.",
        4: f"I'd be happy if my child married {voter}.",
        5: f"I'd be delighted if my child married {voter}.",
    })


def discrimination11(group: str, plural: bool = True) -> Phraser:
    face = "face" if plural else "faces"
    get = "get" if plural else "gets"
    return scale11(
        f"If anything, {group} {get} favoured in Britain these days.",
        f"{group} {get} a slightly easier ride than most in Britain.".replace(f"{group} {get}", f"{group[0].upper()}{group[1:]} {get}"),
        f"{group[0].upper()}{group[1:]} still {face} some discrimination in Britain.",
        f"{group[0].upper()}{group[1:]} {face} a lot of discrimination in Britain today.",
    )


def identity_statement(row, country: int) -> str | None:
    """Nation versus British identity, both on 1-7 scales."""
    nation_col = {1: "englishnessW31", 2: "scottishnessW31", 3: "welshnessW31"}[country]
    nation, british = value(row, nation_col), value(row, "britishnessW31")
    if nation is None or british is None:
        return None
    adjective = codes.NATION_ADJECTIVE[country]
    gap = nation - british
    if gap >= 3:
        return f"I'm {adjective}, not British."
    if gap >= 1:
        return f"I feel more {adjective} than British."
    if gap == 0:
        if nation >= 6:
            return f"I feel strongly {adjective} and strongly British, in equal measure."
        if nation <= 2:
            return f"I don't feel especially {adjective} or British."
        return None  # middling and equal: nothing worth a bubble
    if gap >= -2:
        return f"I feel more British than {adjective}."
    return f"I'm British first - {adjective} comes a distant second."


def european_statement(row, country: int) -> str | None:
    answer = value(row, "europeannessW31")
    if answer is None:
        return None
    return {1: "I don't feel European in the slightest.", 2: "I don't really feel European.",
            6: "I feel European.", 7: "I feel strongly European."}.get(int(answer))


def eu_statement(row, country: int) -> str | None:
    """2016 vote crossed with what they would do now."""
    now = value(row, "euRefVoteAfterW31")
    then = value(row, "p_eurefvote")
    if now is None or int(now) not in (0, 1):
        return None
    rejoin = int(now) == 0
    if then is None or int(then) not in (0, 1):
        return "I'd vote to rejoin the EU if there were another referendum." if rejoin \
            else "I'd vote to stay out of the EU if there were another referendum."
    remain = int(then) == 0
    if remain and rejoin:
        return "I voted Remain in 2016 and I'd vote to rejoin the EU tomorrow."
    if remain and not rejoin:
        return "I voted Remain in 2016, but I'd vote to stay out of the EU now."
    if not remain and rejoin:
        return "I voted Leave in 2016. Now I'd vote to rejoin the EU."
    return "I voted Leave in 2016 and I'd vote to stay out of the EU again."


def scottish_independence(row, country: int) -> str | None:
    now = value(row, "scotReferendumIntentionW31")
    then = value(row, "p_vote_scot_ref")
    if now is None or int(now) not in (0, 1):
        return None
    yes = int(now) == 1
    if then is not None and int(then) in (0, 1):
        voted_yes = int(then) == 1
        if voted_yes and yes:
            return "I voted Yes in 2014 and I'd vote Yes to independence again."
        if voted_yes and not yes:
            return "I voted Yes in 2014, but I'd vote No to independence now."
        if not voted_yes and yes:
            return "I voted No in 2014. Now I'd vote Yes to Scottish independence."
        return "I voted No in 2014 and I'd vote No to independence again."
    return "I'd vote Yes to Scottish independence." if yes else "I'd vote No to Scottish independence."


def welsh_independence(row, country: int) -> str | None:
    now = value(row, "welshReferendumIntentionW31")
    if now is None or int(now) not in (0, 1):
        return None
    return "I'd vote Yes to Welsh independence." if int(now) == 1 else "I'd vote No to Welsh independence."


def local_vote(row, country: int) -> str | None:
    """The May 2026 local elections in England."""
    turnout = value(row, "localTurnoutRetroW31")
    if turnout == 1:
        party = value(row, "localElectionVoteW31")
        if party is None or int(party) not in codes.PARTIES and int(party) != 9:
            return None
        name = "another party" if int(party) == 9 else codes.PARTIES[int(party)]
        by_post = " by post" if value(row, "voteMethodbW31") == 1 else ""
        return f"In May's local elections I voted {name}{by_post}."
    if turnout == 0:
        reason = value(row, "reasonNonVoterW31")
        if reason is not None and int(reason) in codes.NONVOTE_REASON:
            return f"I didn't vote in May's local elections - {codes.NONVOTE_REASON[int(reason)]}."
        return "I didn't vote in May's local elections."
    return None


def holyrood_vote(row, country: int) -> str | None:
    """The May 2026 Scottish Parliament election (two ballots)."""
    turnout = value(row, "scotTurnoutW31")  # 1 = voted, 2 = did not, despite the stored labels
    if turnout == 2:
        return "I didn't vote in May's Holyrood election."
    if turnout != 1:
        return None
    const, lst = value(row, "scotElectionVoteConstW31"), value(row, "scotElectionVoteListW31")
    c = codes.SCOTTISH_PARTY.get(int(const)) if const is not None else None
    l = codes.SCOTTISH_PARTY.get(int(lst)) if lst is not None else None
    if c and l and c == l:
        return f"In May's Holyrood election I voted {c} on both ballots."
    if c and l:
        return f"In May's Holyrood election I voted {c} on the constituency ballot and {l} on the list."
    if c or l:
        return f"In May's Holyrood election I voted {c or l}."
    return None


def senedd_vote(row, country: int) -> str | None:
    """The May 2026 Senedd election."""
    turnout = value(row, "welshTurnoutW31")
    vote = value(row, "senvoteW31")
    if turnout == 0 or vote == 0:
        return "I didn't vote in May's Senedd election."
    if turnout == 1 and vote is not None and int(vote) in codes.SENEDD_PARTY:
        return f"In May's Senedd election I voted {codes.SENEDD_PARTY[int(vote)]}."
    return None


def trust_mps(answer: float) -> str | None:
    return {1: "I don't trust MPs one bit.", 2: "I trust MPs very little.", 3: "I don't have much trust in MPs.",
            5: "I trust MPs a fair amount.", 6: "I trust MPs a good deal.", 7: "I trust MPs a great deal."}.get(int(answer))


# ---------------------------------------------------------------------------
# The library. Column lists start with wave 31 and fall back to earlier waves
# (wave 20 onwards) so the freshest answer each person gave is used.


IMPACT_BATTERY = {  # the "how much impact on Britain's economy" grid, per wave, for spotting straight-liners
    "W31": ("brexitEconImpactW31", "globalEconomyEconImpactW31", "conflictEconImpactW31", "ukGovtEconImpactW31", "ukLastGovtEconImpactW31"),
    "W30": ("brexitEconImpactW30", "globalEconomyEconImpactW30", "ukraineEconImpactW30", "ukGovtEconImpactW30", "ukLastGovtEconImpactW30"),
}


def impact_item(cols: tuple[str, ...], lot_damage: str, some_damage: str, good: str, very_good: str) -> Callable:
    """BES economic-impact scale, 0 (large negative impact) to 100 (large positive).

    The middle (41-59) says nothing. Someone who gave the identical answer to
    every item in the grid is skipped - that is a straight-liner, not a view.
    """
    def custom(row, country: int) -> str | None:
        answer, col = latest(row, cols)
        if answer is None:
            return None
        wave = "W" + col.rsplit("W", 1)[1]
        grid = [value(row, c) for c in IMPACT_BATTERY.get(wave, ())]
        grid = [g for g in grid if g is not None]
        if len(grid) >= 3 and len(set(grid)) == 1:
            return None
        n = int(answer)
        if n <= 20:
            return lot_damage
        if n <= 40:
            return some_damage
        if n >= 80:
            return very_good
        if n >= 60:
            return good
        return None
    return custom


def scot_ref_bond(row, country: int) -> str | None:
    """Identity with the Yes or No side of 2014, from the referendum-identity battery (Scotland, 2024)."""
    side = {1: "the Yes side", 2: "the No side"}.get(int(value(row, "scotRefIDW27") or 0))
    if side is None:
        return None
    if value(row, "scotRefID3W27") == 4:
        return f"When people criticise {side}, it feels like a personal insult."
    if value(row, "scotRefID1W27") == 4:
        return f"I still say 'we' when I talk about {side}."
    if value(row, "scotRefID6W27") == 4:
        return f"When I meet someone else from {side}, I feel a connection."
    return None


def eu_ref_bond(row, country: int) -> str | None:
    """Identity with Remain or Leave, from the EU-referendum-identity battery (2023)."""
    side = {1: "Remainers", 2: "Leavers"}.get(int(value(row, "euIDW24") or 0))
    if side is None:
        return None
    if value(row, "euID3W24") == 4:
        return f"When people criticise {side}, it feels like a personal insult."
    if value(row, "euID1W24") == 4:
        return f"I still say 'we' when I talk about {side}."
    if value(row, "euID6W24") == 4:
        return f"When I meet another of the {side}, I feel a connection."
    return None


def eu_regret(row, country: int) -> str | None:
    regret = value(row, "regretsIHaveAFewEUW26")
    if regret == 1:
        return "I regret how I voted in the EU referendum."
    if regret == 0:
        return "I've no regrets about how I voted in the EU referendum."
    return None


def social_circle_vote(row, country: int) -> str | None:
    party = value(row, "normPartyVoteW28")
    if party is None:
        return None
    if int(party) == 0:
        return "Most people I know weren't going to vote in 2024."
    if int(party) in codes.PARTIES:
        return f"Most people I know were voting {codes.PARTIES[int(party)]} in 2024."
    return None





def warmth_item(group: str) -> Phraser:
    """The 0-100 feeling thermometer: cold below 20, cool to 40, warm from 60, very warm from 80."""
    def phrase(answer: float) -> str | None:
        n = int(answer)
        if n < 20:
            return f"I feel cold towards {group}."
        if n <= 40:
            return f"I don't feel warmly towards {group}."
        if n >= 80:
            return f"I feel very warmly towards {group}."
        if n >= 60:
            return f"I feel warmly towards {group}."
        return None
    return phrase


def gone_too_far_item(what: str) -> Phraser:
    return by_code({
        1: f"{what[0].upper()}{what[1:]} haven't gone nearly far enough.",
        2: f"{what[0].upper()}{what[1:]} haven't gone far enough.",
        3: f"{what[0].upper()}{what[1:]} are about right.",
        4: f"{what[0].upper()}{what[1:]} have gone too far.",
        5: f"{what[0].upper()}{what[1:]} have gone much too far.",
    })


ITEMS: list[Item] = [
    # Economic values (lr1-5)
    Item("lr1", "redistribution", ("lr1W31",),
         agree5(("The government should do far more to redistribute income from the better off to those with less.", "The government should take a lot more from the well-off and give it to those with less."),
                ("The government should take more from the well-off and give it to those with less.", "I'd like to see more redistribution from the well-off to people who have less."),
                ("I'm not keen on the government taking from the well-off to give to others.", "I don't think it's the government's job to redistribute income."),
                ("The government has no business redistributing income from the well-off.", "Taking from the better off to give to the less well off is wrong."))),
    Item("lr2", "big-business", ("lr2W31",),
         agree5(("Big business takes advantage of ordinary people at every turn.", "Big business rides roughshod over ordinary people."),
                ("Big business takes advantage of ordinary people.", "Ordinary people get taken advantage of by big business."),
                ("I don't think big business takes advantage of ordinary people.", "Big business doesn't take advantage of ordinary people, as a rule."),
                ("The idea that big business exploits ordinary people is wrong.", "Big business doesn't take advantage of ordinary people - that's a myth."))),
    Item("lr3", "fair-share-wealth", ("lr3W31",),
         agree5(("Ordinary working people don't get anything like their fair share of the nation's wealth.", "Working people are a long way from getting their fair share of the nation's wealth."),
                ("Ordinary working people don't get their fair share of the nation's wealth.", "Working people get less than their fair share of the nation's wealth."),
                ("Ordinary working people do get their fair share of the nation's wealth.", "I think working people get a fair share of the nation's wealth."),
                ("Working people certainly get their fair share of the nation's wealth.", "Ordinary working people get every bit of their fair share of the nation's wealth."))),
    Item("lr4", "one-law", ("lr4W31",),
         agree5(("There's clearly one law for the rich and another for the poor.", "One law for the rich, another for the poor - that's how it is."),
                ("There's one law for the rich and another for the poor.", "The law treats the rich and the poor differently."),
                ("I don't think there's one law for the rich and another for the poor.", "The law treats rich and poor much the same."),
                ("The idea that there's one law for the rich and another for the poor is nonsense.", "Rich or poor, the law is the same for everyone."))),
    Item("lr5", "management", ("lr5W31",),
         agree5(("Management will always get the better of staff if it gets the chance.", "Give management half a chance and it'll get the better of its employees every time."),
                ("Management will try to get the better of employees if it gets the chance.", "Bosses tend to get the better of their staff when they can."),
                ("I don't think management sets out to get the better of employees.", "Most managers aren't out to get the better of their staff."),
                ("Management doesn't try to get the better of employees - that's an old myth.", "The idea that bosses are always out to get the better of staff is rubbish."))),
    Item("al1", "young-people", ("al1W31",),
         agree5(("Young people today have no respect for traditional British values.", "Young people have far too little respect for traditional British values."),
                ("Young people don't have enough respect for traditional British values.", "Young people could do with more respect for traditional British values."),
                ("Young people today respect traditional British values well enough.", "I don't think young people lack respect for traditional British values."),
                ("The idea that young people don't respect traditional British values is nonsense.", "Young people have plenty of respect for traditional British values."))),
    Item("al2", "death-penalty", ("al2W31",),
         agree5(("For some crimes, the death penalty is the only right sentence.", "Some crimes deserve the death penalty - nothing less."),
                ("For some crimes, the death penalty is the right sentence.", "I'd bring back the death penalty for some crimes."),
                ("I don't think the death penalty is ever the right sentence.", "I'm against the death penalty."),
                ("The death penalty is never the right sentence, whatever the crime.", "I'm completely against the death penalty, whatever the crime."))),
    Item("al3", "obey-authority", ("al3W31",),
         agree5(("Teaching children to obey authority should be one of a school's main jobs.", "Schools should teach children to obey authority, first and foremost."),
                ("Schools should teach children to obey authority.", "Children should be taught to obey authority at school."),
                ("Teaching children to obey authority isn't what schools are for.", "I don't think schools should be teaching children to obey authority."),
                ("Schools should be teaching children to think for themselves, not to obey authority.", "The last thing schools should teach is obedience to authority."))),
    Item("al4", "censorship", ("al4W31",),
         agree5(("Films and magazines need censoring to uphold moral standards.", "Without censorship of films and magazines, moral standards go."),
                ("Some censorship of films and magazines is needed to uphold moral standards.", "I'd keep some censorship of films and magazines, for the sake of moral standards."),
                ("Films and magazines don't need censoring to uphold moral standards.", "I don't think censorship of films and magazines does anything for moral standards."),
                ("Censorship of films and magazines has no place in upholding moral standards.", "I'm against censoring films and magazines, moral standards or not."))),
    Item("al5", "sentencing", ("al5W31",),
         agree5(("People who break the law should get much stiffer sentences.", "Sentences for lawbreakers are far too soft."),
                ("People who break the law should get stiffer sentences.", "Sentences should be tougher on people who break the law."),
                ("I don't think lawbreakers need stiffer sentences.", "Sentences are stiff enough as they are."),
                ("Stiffer sentences are the last thing we need.", "I'm firmly against stiffer sentences for lawbreakers."))),

    Item("cwLanguage", "offence", ("cwLanguageW31", "cwLanguageW26W27", "cwLanguageW25"),
         agree5("Far too many people are easily offended these days over the words others use.",
                "Too many people are easily offended these days over the language others use.",
                "I don't think people are too easily offended by language - words matter.",
                "People aren't too easily offended over language - far from it.")),
    Item("cwStatues", "statues", ("cwStatuesW31", "cwStatuesW26W27", "cwStatuesW25"),
         agree5("Statues of historical figures should stay up, even if they profited from slavery.",
                "I'd keep statues of historical figures up, even if they profited from slavery.",
                "Statues of people who profited from slavery shouldn't necessarily stay up.",
                "Statues of people who profited from slavery should come down.")),
    Item("cwTraining", "diversity-training", ("cwTrainingW31", "cwTrainingW26W27", "cwTrainingW25"),
         agree5("Workplaces should scrap mandatory diversity training altogether.",
                "Workplaces should end mandatory diversity training.",
                "I'd keep mandatory diversity training at work.",
                "Mandatory diversity training at work should definitely stay.")),
    Item("cwAuthors", "curriculum", ("cwAuthorsW31", "cwAuthorsW26W27", "cwAuthorsW25"),
         agree5("School and university reading lists need far more female and non-white authors.",
                "Reading lists should include more female and non-white authors.",
                "I don't see the need to change reading lists to add more female and non-white authors.",
                "I'm firmly against changing reading lists to add more female and non-white authors.")),
    Item("cwTrans", "trans-sport", ("cwTransW31", "cwTransW26W27", "cwTransW25"),
         agree5("Transgender women have every right to compete in women's sport.",
                "Transgender women should be allowed to compete in women's sport.",
                "Transgender women shouldn't compete in women's sport.",
                "Transgender women should not be competing in women's sport at all.")),
    Item("cwParents", "same-sex-parents", ("cwParentsW31", "cwParentsW30", "cwParentsW26W27", "cwParentsW25"),
         agree5("Children's TV should show far more families with same-sex parents.",
                "Children's TV should show more families with same-sex parents.",
                "I don't think children's TV needs to show more families with same-sex parents.",
                "Children's TV certainly doesn't need more families with same-sex parents.")),
    # Spending and the state
    Item("cutsNational", "spending-cuts", ("cutsTooFarNationalW31", "cutsTooFarNationalW30", "cutsTooFarNationalW26"),
         too_far5("Cuts to public spending have gone much too far.", "Cuts to public spending have gone too far.",
                  "Public spending cuts have been about right.", "Cuts to public spending haven't gone far enough.",
                  "Cuts to public spending haven't gone nearly far enough."), fallback=False),
    Item("cutsNHS", "nhs-cuts", ("cutsTooFarNHSW31", "cutsTooFarNHSW30", "cutsTooFarNHSW26"),
         too_far5("Cuts to NHS spending have gone much too far.", "Cuts to NHS spending have gone too far.",
                  "NHS spending cuts have been about right.", "NHS spending cuts haven't gone far enough.",
                  "NHS spending cuts haven't gone nearly far enough."), fallback=False),
    Item("cutsLocal", "local-cuts", ("cutsTooFarLocalW31", "cutsTooFarLocalW30", "cutsTooFarLocalW26"),
         too_far5("Cuts to local services where I live have gone much too far.",
                  "Cuts to local services where I live have gone too far.",
                  "Cuts to local services round here have been about right.",
                  "Cuts to local services where I live haven't gone far enough.",
                  "Cuts to local services where I live haven't gone nearly far enough."), fallback=False),
    Item("privatisation", "privatisation", ("privatTooFarW31", "privatTooFarW26"),
         too_far5("Private companies have far too big a role in running public services.",
                  "Private companies have too big a role in running public services.",
                  "The role of private companies in public services is about right.",
                  "Private firms should be running more of our public services.",
                  "Private firms should be running far more of our public services.")),
    Item("enviroProtection", "green-rules", ("enviroProtectionW31", "enviroProtectionW30", "enviroProtectionW26"),
         too_far5("Measures to protect the environment have gone much too far.",
                  "Measures to protect the environment have gone too far.",
                  "Environmental protection is about right as it is.",
                  "Measures to protect the environment haven't gone far enough.",
                  "Measures to protect the environment haven't gone nearly far enough.")),
    Item("taxSpend", "tax-and-spend", ("taxSpendSelfW31", "taxSpendSelfW30", "taxSpendSelfW28", "taxSpendSelfW27"),
         scale11("Cut taxes a lot, even if it means spending much less on health and social services.",
                 "I'd cut taxes a bit and trim spending on health and social services.",
                 "I'd pay a bit more tax for better health and social services.",
                 "Raise taxes a lot and spend much more on health and social services.",
                 "Tax and spending on health and social services should stay about where they are.")),
    Item("redist", "redistribution", ("redistSelfW31", "redistSelfW30", "redistSelfW29"),
         scale11("Government should be doing much more to make incomes equal.",
                 "Government should do a bit more to even out incomes.",
                 "Government should worry less about making incomes equal.",
                 "Making incomes more equal shouldn't be the government's concern at all."), weight=0.7),
    Item("welfare", "benefits", ("welfarePreferenceW31", "welfarePreferenceW27"),
         by_code({1: "Benefits are much too high.", 2: "Benefits are too high.", 3: "Benefit levels are about right.",
                  4: "Benefits are too low.", 5: "Benefits are much too low."})),
    Item("enviroGrowth", "growth-v-environment", ("enviroGrowthW31", "enviroGrowthW30", "enviroGrowthW28"),
         scale11("Economic growth has to come first, ahead of the environment.",
                 "Growth should come first, but the environment matters too.",
                 "Protecting the environment should come first, though growth matters.",
                 "Protecting the environment must come before economic growth.")),
    # Immigration and Europe
    Item("immigSelf", "immigration", ("immigSelfW31", "immigSelfW30", "immigSelfW29"),
         scale11("Britain should let in far fewer immigrants.", "I'd like to see fewer immigrants coming in.",
                 "I'd be happy for a few more immigrants to come.", "Britain should let in many more immigrants.",
                 "Immigration levels are about right as they are.")),
    Item("immigEcon", "immigration", ("immigEconW31", "immigEconW30", "immigEconW27"),
         by_code({1: "Immigration is clearly bad for the economy.", 2: "Immigration is bad for the economy.",
                  3: "On balance, immigration is slightly bad for the economy.",
                  5: "On balance, immigration is slightly good for the economy.",
                  6: "Immigration is good for the economy.", 7: "Immigration is clearly good for the economy."}),
         weight=0.6),
    Item("euIntegration", "europe", ("EUIntegrationSelfW31", "EUIntegrationSelfW29"),
         scale11("Britain should unite fully with the European Union.", "I'd like Britain much closer to the EU.",
                 "I'd keep Britain at arm's length from the EU.", "Britain must protect its independence from the EU."),
         weight=0.6),
    Item("euRef", "europe", (), custom=eu_statement, weight=1.3),
    # Democracy and politicians
    Item("strongLeader", "strong-leader", ("strongLeaderW31",),
         agree5("Britain would be better run by a strong leader who ignores parliament and elections.",
                "A strong leader who didn't have to bother with parliament would run things better.",
                "I don't want a strong leader who ignores parliament and elections.",
                "I'd never want a leader who ignored parliament and elections.")),
    Item("trustMPs", "trust", ("trustMPsW31",), trust_mps),
    Item("efficacyPolCare", "politicians", ("efficacyPolCareW31", "efficacyPolCareW30", "efficacyPolCareW27"),
         agree5("Politicians couldn't care less what people like me think.",
                "Politicians don't care what people like me think.",
                "I think politicians do care what people like me think.",
                "Politicians really do care what people like me think.")),
    Item("efficacyNoMatter", "politicians", ("efficacyNoMatterW31", "efficacyNoMatterW30", "efficacyNoMatterW27"),
         agree5("It makes no difference which party is in power.",
                "It doesn't much matter which party is in power.",
                "It does matter which party is in power.",
                "It matters enormously which party is in power."), weight=0.7),
    Item("efficacyUnderstand", "political-interest", ("efficacyUnderstandW31", "efficacyUnderstandW30"),
         agree5("I've got a good grasp of the big political issues facing the country.",
                "I understand the big political issues facing the country pretty well.",
                "I don't really understand the big political issues facing the country.",
                "I struggle to follow the big political issues facing the country."), weight=0.5),
    Item("approveUK", "uk-government", ("approveUKGovtW31",), approve5("the UK government"), fallback=False),
    Item("approveScot", "scottish-government", ("approveScotGovtW31",), approve5("the Scottish Government"), nations=(2,), fallback=False),
    Item("approveWelsh", "welsh-government", ("approveWelshGovtW31",), approve5("the Welsh Government"), nations=(3,), fallback=False),
    Item("approveCouncil", "council", ("approveLAW31",), approve5("my local council"), weight=0.6, fallback=False),
    # How things are going
    Item("govtEcon", "government-handling", ("govtHandleEconAW31", "govtHandleEconBW31", "govtHandleEconW30"), handling5("the economy"), weight=0.6, fallback=False),
    Item("govtNHS", "government-handling", ("govtHandleNHSAW31", "govtHandleNHSBW31", "govtHandleNHSW30"), handling5("the NHS"), weight=0.6, fallback=False),
    Item("govtImmig", "government-handling", ("govtHandleImmigAW31", "govtHandleImmigBW31", "govtHandleImmigW30"), handling5("immigration"), weight=0.6, fallback=False),
    Item("govtCrime", "government-handling", ("govtHandleLevelCrimeAW31", "govtHandleLevelCrimeBW31", "govtHandleLevelCrimeW30"), handling5("crime"), weight=0.5, fallback=False),
    Item("govtForeign", "government-handling", ("govtHandleForeignAW31", "govtHandleForeignBW31"), handling5("foreign affairs"), weight=0.5, fallback=False),
    Item("changeNHS", "nhs-direction", ("changeNHSW31", "changeNHSW30"),
         worse_better5("The NHS is getting a lot worse.", "The NHS is getting a bit worse.",
                       "The NHS is getting a bit better.", "The NHS is getting a lot better."), fallback=False),
    Item("changeEconomy", "economy-direction", ("changeEconomyW31", "changeEconomyW30"),
         worse_better5("The economy is getting a lot worse.", "The economy is getting a bit worse.",
                       "The economy is getting a bit better.", "The economy is getting a lot better."), weight=0.7, fallback=False),
    Item("changeSchools", "schools", ("changeSchoolsW31", "changeSchoolsW30"),
         worse_better5("Schools are getting a lot worse.", "Schools are getting a bit worse.",
                       "Schools are getting a bit better.", "Schools are getting a lot better."), weight=0.6, fallback=False),
    Item("changeCostLive", "cost-of-living", ("changeCostLiveW31", "changeCostLiveW30"),
         by_code({5: "The cost of living is still going up a lot.", 4: "The cost of living is still creeping up.",
                  2: "The cost of living is starting to come down a little.", 1: "The cost of living is coming down a lot."}), fallback=False),
    Item("changeImmig", "immigration-direction", ("changeImmigW31", "changeImmigW30"),
         by_code({5: "Immigration is going up a lot.", 4: "Immigration is going up a bit.",
                  2: "Immigration is coming down a bit.", 1: "Immigration is coming down a lot."}), weight=0.5, fallback=False),
    Item("changeCrime", "crime-direction", ("changeCrimeW31", "changeCrimeW30"),
         by_code({5: "Crime is going up a lot.", 4: "Crime is going up a bit.",
                  2: "Crime is falling a bit.", 1: "Crime is falling a lot."}), weight=0.6, fallback=False),
    Item("econGenRetro", "economy-direction", ("econGenRetroW31", "econGenRetroW30"),
         worse_better5("The economy has got a lot worse over the past year.", "The economy has got a bit worse over the past year.",
                       "The economy has got a bit better over the past year.", "The economy has got a lot better over the past year."),
         weight=0.5, fallback=False),
    Item("econGenProsp", "economy-outlook", ("econGenProspW31",),
         worse_better5("The economy is going to get a lot worse over the next year.", "I expect the economy to get a bit worse next year.",
                       "I expect the economy to pick up a bit next year.", "The economy is going to get a lot better over the next year."),
         weight=0.6, fallback=False),
    # Nation, union and identity
    Item("identity", "identity", (), custom=identity_statement, weight=1.0),
    Item("european", "identity", (), custom=european_statement, weight=0.5),
    Item("scotIndy", "independence", (), custom=scottish_independence, nations=(2,), weight=1.5),
    Item("welshIndy", "independence", (), custom=welsh_independence, nations=(3,), weight=1.5),
    Item("engFairShare", "fair-share", ("engFairShareW31", "engFairShareW30"), fair_share5("England"), nations=(1,), weight=0.8),
    Item("scotFairShare", "fair-share", ("scotFairShareW31", "scotFairShareW30"), fair_share5("Scotland"), nations=(2,), weight=0.8),
    Item("walesFairShare", "fair-share", ("walesFairShareW31", "walesFairShareW30"), fair_share5("Wales"), nations=(3,), weight=0.8),
    Item("localFairShare", "fair-share", ("localFairShareW31", "localFairShareW30", "localFairShareW21"),
         fair_share5("My local area", "of government spending"), weight=0.8),
    Item("londonFairShare", "fair-share", ("londonFairShareW31", "londonFairShareW30"),
         fair_share5("London", "of government spending"), weight=0.6),
    # Society
    Item("discrimWomen", "discrimination", ("discrimWomenW31",), discrimination11("women"), weight=0.5),
    Item("discrimMen", "discrimination", ("discrimMenW31",), discrimination11("men"), weight=0.5),
    Item("discrimBME", "discrimination", ("discrimBMEW31",), discrimination11("ethnic minorities"), weight=0.5),
    Item("discrimWhite", "discrimination", ("discrimWhiteW31",), discrimination11("white people"), weight=0.5),
    Item("discrimGay", "discrimination", ("discrimGayW31",), discrimination11("gay and lesbian people"), weight=0.5),
    Item("discrimTrans", "discrimination", ("discrimTransW31",), discrimination11("transgender people"), weight=0.5),
    Item("israelPalestine", "israel-palestine", ("israelPalestineW31", "israelPalestineW28"),
         by_code({1: "My sympathies lie firmly with Israel over the Palestinians.",
                  2: "I sympathise a little more with the Israeli side.",
                  3: "On Israel and Palestine, I don't take either side.",
                  4: "I sympathise a little more with the Palestinian side.",
                  5: "My sympathies lie firmly with the Palestinians."})),
    Item("happyTrump", "trump", ("happyTrumpW31", "happyTrumpW30"),
         scale11("Trump back in the White House is a disaster.", "I'm disappointed Trump is back in the White House.",
                 "I'm fairly pleased Trump is back in the White House.", "I'm delighted Trump is back in the White House."), fallback=False),
    Item("automationSelf", "automation", ("automationEffectsSelfW31",),
         by_code({1: "Robots and AI taking over work would be very bad for me.", 2: "Automation taking over jobs would be bad for me.",
                  4: "Automation taking over jobs would be good for me.", 5: "Robots and AI doing more of the work would be very good for me."}),
         weight=0.6),
    Item("automationCountry", "automation", ("automationEffectsCountryW31",),
         by_code({1: "Robots and AI taking over work would be very bad for the country.",
                  2: "Automation taking over jobs would be bad for the country.",
                  4: "Automation taking over jobs would be good for the country.",
                  5: "Robots and AI doing more of the work would be very good for the country."}), weight=0.6),
    # Tribes: how they'd feel about their child marrying a ... voter
    Item("marryCon", "marrying", ("socialDistConW31",), marry5("a Conservative voter"), weight=0.4),
    Item("marryLab", "marrying", ("socialDistLabW31",), marry5("a Labour voter"), weight=0.4),
    Item("marryLD", "marrying", ("socialDistLDW31",), marry5("a Lib Dem voter"), weight=0.3),
    Item("marryGreen", "marrying", ("socialDistGreenW31",), marry5("a Green voter"), weight=0.3),
    Item("marryReform", "marrying", ("socialDistBrexitW31",), marry5("a Reform voter"), weight=0.5),
    Item("marryRemain", "marrying", ("socialDistRemainW31",), marry5("a Remainer"), weight=0.3),
    Item("marryLeave", "marrying", ("socialDistLeaveW31",), marry5("a Leaver"), weight=0.3),
    Item("marrySNP", "marrying", ("socialDistSNPW31",), marry5("an SNP voter"), nations=(2,), weight=0.5),
    Item("marryPlaid", "marrying", ("socialDistPlaidW31",), marry5("a Plaid Cymru voter"), nations=(3,), weight=0.5),

    # ------------------------------------------------------------------
    # Questions last asked between waves 20 and 30. Views on these are
    # fairly stable, and they widen the range of things a card can say.

    # Policies (1 strongly oppose ... 5 strongly support)
    Item("votesAt16", "voting-age", ("votesAt16W28",),
         agree5("Sixteen-year-olds should definitely get the vote.", "I'd give sixteen-year-olds the vote.",
                "I'd keep the voting age at 18.", "Sixteen is far too young to vote.")),
    Item("militaryService", "national-service", ("militaryServiceW28",),
         agree5("Every 18-year-old should do a year of national service, military or community.",
                "I'd back a year of national service for 18-year-olds.",
                "I'm against making 18-year-olds do a year of national service.",
                "I'm firmly against compulsory national service for 18-year-olds.")),
    Item("breakfastClub", "breakfast-clubs", ("breakfastClubW28",),
         agree5("Every primary school should have a free breakfast club.",
                "I'm in favour of free breakfast clubs in every primary school.",
                "I'm against free breakfast clubs for all primary pupils.",
                "Free breakfast clubs for every primary pupil are a waste of money."), weight=0.7),
    Item("inheritanceTax", "inheritance-tax", ("inheritanceTaxW28",),
         agree5("Inheritance tax should be abolished altogether.", "I'd abolish inheritance tax.",
                "I'd keep inheritance tax.", "Inheritance tax should stay - scrapping it would be wrong.")),
    Item("tripleLock", "pensions", ("tripleLockW28",),
         agree5("Pensions should keep rising even when wages and prices don't.", "I'd keep the pensions triple lock.",
                "Pensions shouldn't rise faster than wages and prices.", "The pensions triple lock should go.")),
    Item("privVAT", "private-schools", ("privVATW28",),
         agree5("Private school fees should never have had VAT put on them.",
                "I'd take VAT back off private school fees.",
                "Private school fees should be taxed like anything else.",
                "Putting VAT on private school fees was the right call.")),
    Item("abolishPrivSchool", "private-schools", ("abolishPrivSchoolW27",),
         agree5("Private schools should be abolished altogether.", "I'd get rid of private schools.",
                "I'm against abolishing private schools.", "Abolishing private schools would be completely wrong.")),
    Item("banSmoke", "smoking-ban", ("banSmokeW27",),
         agree5("Nobody born after 2009 should ever be sold cigarettes.",
                "I back the ban on selling cigarettes to anyone born after 2009.",
                "I'm against banning cigarette sales by year of birth.",
                "A smoking ban by year of birth is the nanny state at its worst."), weight=0.7),
    Item("govtEnergy", "public-energy", ("govtEnergyW27",),
         agree5("A publicly owned renewable energy company is exactly what we need.",
                "I back a publicly owned renewable energy company.",
                "I'm against a publicly owned energy company.",
                "The state has no business running an energy company."), weight=0.7),
    Item("newTown", "housing", ("newTownW27",),
         agree5("We should be building new towns - we need the houses.",
                "I'm in favour of building new towns to get more houses built.",
                "I'm against building new towns.", "Building new towns is entirely the wrong answer.")),
    Item("monarch", "monarchy", ("monarchW25",),
         agree5("Britain should definitely keep the monarchy.", "I'd keep the monarchy.",
                "I'd rather we did away with the monarchy.", "The monarchy should go.")),
    Item("keepNukes", "nuclear-weapons", ("keepNukesW23",),
         agree5("Britain must keep its nuclear submarines.", "I'd keep Britain's nuclear weapons.",
                "I'd give up Britain's nuclear weapons.", "Britain should scrap its nuclear weapons altogether.")),
    Item("overseasAid", "foreign-aid", ("overseasAidW30", "overseasAidW27"),
         agree5("Britain should stop all overseas aid spending, every penny of it.", "Britain should stop spending on overseas aid.",
                "Britain should keep spending on overseas aid.", "Cutting overseas aid to nothing would be shameful.")),
    Item("natSecuritySpending", "defence", ("natSecuritySpendingW30", "natSecuritySpendingW25"),
         by_code({5: "Britain should spend a lot more on defence.", 4: "I'd spend a bit more on defence.", 3: "Defence spending is about right.",
                  2: "I'd spend a bit less on defence.", 1: "Britain should spend a lot less on defence."})),
    Item("renationaliseRail", "nationalisation", ("renationaliseRailW26",),
         agree5("Bringing the railways back into public ownership is right, and about time too.", "Bringing the railways back into public ownership is the right thing to do.",
                "I'm against bringing the railways back into public ownership.", "Taking the railways back into public ownership is a big mistake.")),
    Item("nationaliseUtilities", "nationalisation", ("nationalizeUtilitiesW26",),
         by_code({1: "Gas, electricity and water should be run entirely by the public sector.",
                  2: "Gas, electricity and water should be mostly in public hands.",
                  3: "Gas, electricity and water should be a mix of public and private.",
                  4: "Gas, electricity and water should be mostly run by private firms.",
                  5: "Gas, electricity and water should be run entirely by private firms."})),
    Item("nationaliseHospitals", "nationalisation", ("nationalizeHospitalsW26",),
         by_code({1: "Hospitals should be run entirely by the public sector.", 2: "Hospitals should be mostly in public hands.",
                  4: "Hospitals should be mostly run by private firms.", 5: "Hospitals should be run entirely by private firms."}), weight=0.6),
    Item("nationaliseSchools", "nationalisation", ("nationalizeSchoolsW26",),
         by_code({1: "Schools should be run entirely by the public sector.", 2: "Schools should be mostly in public hands.",
                  4: "Schools should be mostly run by private firms.", 5: "Schools should be run entirely by private firms."}), weight=0.5),
    Item("pubPrivEfficient", "nationalisation", ("pubPrivEfficientW26",),
         scale11("Private companies give better value on gas, water and electricity.",
                 "Private firms probably give better value on utilities.",
                 "The public sector probably gives better value on utilities.",
                 "The public sector gives far better value on gas, water and electricity."), weight=0.6),
    Item("privateHospChoice", "private-health", ("privateHospChoiceW26",),
         agree5("People should have every right to pay to be seen faster in healthcare.",
                "People should be able to pay to be seen faster if they want to.",
                "Nobody should be able to jump the healthcare queue by paying.",
                "Paying to jump the healthcare queue is plain wrong.")),
    Item("privateHospAfford", "private-health", ("privateHospAffordW26",),
         agree5("Private healthcare is unfair - only the rich can afford it.", "Private healthcare isn't fair when only the rich can afford it.",
                "I don't see private healthcare as unfair.", "There's nothing unfair about private healthcare."), weight=0.7),
    Item("zeroHours", "zero-hours", ("zeroHourContractW27",),
         by_code({1: "Zero-hours contracts should definitely be illegal.", 2: "Zero-hours contracts should probably be banned.",
                  3: "Zero-hours contracts should probably stay legal.", 4: "Zero-hours contracts should definitely stay legal."})),
    Item("deficit", "deficit", ("deficitReduceW27",),
         by_code({4: "Getting rid of the deficit is completely necessary.", 3: "Cutting the deficit matters, but it isn't everything.",
                  2: "Cutting the deficit would be nice but it isn't necessary.", 1: "There's no need to eliminate the deficit at all."})),
    Item("howToReduceDeficit", "deficit", ("howToReduceDeficitW27",),
         by_code({1: "If the deficit has to come down, do it through taxes, not cuts.",
                  2: "Cut the deficit mainly with tax rises, with some spending cuts.",
                  3: "Cut the deficit with an even mix of tax rises and spending cuts.",
                  4: "Cut the deficit mainly through spending cuts, with a few tax rises.",
                  5: "Cut the deficit through spending cuts alone - no tax rises."}), weight=0.6),
    Item("inequalityLevel", "inequality", ("inequalityLevelW25",),
         by_code({1: "The gap between rich and poor is much too wide.", 2: "The gap between rich and poor is too wide.",
                  3: "The gap between rich and poor is about right.", 4: "The gap between rich and poor is too small.",
                  5: "The gap between rich and poor is far too small."})),
    Item("changeInequality", "inequality", ("changeInequalityW21",),
         by_code({5: "The gap between rich and poor is getting much wider.", 4: "The gap between rich and poor is getting wider.",
                  2: "The gap between rich and poor is getting smaller.", 1: "The gap between rich and poor is closing fast."}), weight=0.5),
    Item("climateChange", "climate", ("climateChangeW26",),
         by_code({1: "Climate change is real and it's us causing it.",
                  2: "The climate is changing, but I don't think humans are the cause.",
                  3: "I don't believe the climate is changing."})),
    # Values and outlook
    Item("britishPride", "pride", ("britishPrideW27", "britishPrideW25"),
         agree5("I'm very proud to be British.", "I'm proud to be British.",
                "I'm not especially proud to be British.", "I'm not proud to be British.")),
    Item("radical", "change", ("radicalW27", "radicalW25"),
         agree5("We need to fundamentally change how society works in Britain.", "Britain needs big changes to how society works.",
                "I don't think society in Britain needs fundamental change.", "Society doesn't need fundamental change - it mostly works.")),
    Item("harkBack", "change", ("harkBackW27", "harkBackW25"),
         agree5("Things in Britain were definitely better in the past.", "Things in Britain were better in the past.",
                "I don't think things were better in the past.", "Things in Britain were not better in the past - that's rose-tinted thinking.")),
    Item("populismPeople", "populism", ("populism2W27", "populism2W26"),
         agree5("The people, not politicians, should be making the big decisions.",
                "I'd rather the people made the big decisions than politicians.",
                "Big decisions are better left to elected politicians than to the public.",
                "The public shouldn't be making the big policy decisions instead of politicians."), weight=0.7),
    Item("populismTalk", "populism", ("populism5W27", "populism5W26"),
         agree5("Politicians talk far too much and do far too little.", "Politicians talk too much and act too little.",
                "I don't think politicians are all talk.", "Politicians aren't all talk."), weight=0.6),
    Item("populismCompromise", "populism", ("populism6W27", "populism6W26"),
         agree5("Compromise in politics is just selling out your principles.", "Political compromise usually means selling out.",
                "Compromise in politics isn't selling out - it's how things get done.", "Compromise is the heart of politics, not a sell-out."),
         weight=0.6),
    Item("antiIntellectual", "experts", ("antiIntellectualW23", "antiIntellectualW21"),
         agree5("I'd trust the common sense of ordinary people over the experts any day.",
                "I'd rather trust ordinary people's wisdom than the experts.",
                "I'd rather trust the experts than the wisdom of the crowd.",
                "Give me the experts over the wisdom of ordinary people every time.")),
    Item("dutyToVote", "voting-duty", ("dutyToVote2W27", "dutyToVote2W26"),
         agree5("Voting is every citizen's duty, without exception.", "It's every citizen's duty to vote.",
                "I don't think people have a duty to vote.", "Nobody has a duty to vote - it's a choice."), weight=0.7),
    Item("wastedVote", "tactical-voting", ("smallPartyWastedVoteW27", "smallPartyWastedVoteW25"),
         agree5("Voting for a small party is throwing your vote away.", "A vote for a small party is a wasted vote.",
                "A vote for a small party isn't wasted.", "Voting for a small party is never a wasted vote."), weight=0.7),
    Item("smallVoterPref", "tactical-voting", ("smallVoterPrefW27", "smallVoterPrefW25"),
         agree5("Always vote for the party you like best, even if they can't win.", "Vote for the party you like best, whether or not they can win.",
                "There's not much point voting for a party that can't win.", "There's no point at all voting for a party that can't win."), weight=0.7),
    Item("polPreferToFight", "politicians", ("polPreferToFightW28",),
         agree5("Politicians care far more about fighting each other than about the public.",
                "Parties are more interested in fighting each other than in the public interest.",
                "Parties aren't just in it to fight each other.", "I don't think politicians are just fighting each other."), weight=0.6),
    Item("partyDifference", "party-difference", ("partydiffconlabW28",),
         by_code({1: "There's a world of difference between Labour and the Tories.",
                  2: "There's some difference between Labour and the Tories.",
                  3: "There's not much difference between Labour and the Tories."}), weight=0.7),
    Item("prPreference", "electoral-system", ("prPreferenceW29",),
         by_code({1: "I'd rather one party won outright and governed alone than have proportional representation.",
                  2: "Seats in parliament should match votes - I want proportional representation."})),
    Item("voterID", "voter-id", ("voterIDSupportW29", "voterIDSupportW25"),
         agree5("Photo ID at polling stations is the right thing.", "I support needing photo ID to vote.",
                "I'm against needing photo ID to vote.", "Making people show photo ID to vote is wrong."), weight=0.7),
    Item("satDemUK", "democracy", ("satDemUKW29", "satDemUKW27"),
         by_code({1: "I'm very dissatisfied with how democracy works in the UK.", 2: "I'm a bit dissatisfied with how democracy works in the UK.",
                  3: "I'm fairly satisfied with how democracy works in the UK.", 4: "I'm very satisfied with how democracy works in the UK."})),
    Item("satDemScot", "democracy", ("satDemScotW29",),
         by_code({1: "I'm very dissatisfied with how democracy works in Scotland.", 2: "I'm a bit dissatisfied with how democracy works in Scotland.",
                  3: "I'm fairly satisfied with how democracy works in Scotland.", 4: "I'm very satisfied with how democracy works in Scotland."}),
         nations=(2,)),
    Item("satDemWales", "democracy", ("satDemWalesW29",),
         by_code({1: "I'm very dissatisfied with how democracy works in Wales.", 2: "I'm a bit dissatisfied with how democracy works in Wales.",
                  3: "I'm fairly satisfied with how democracy works in Wales.", 4: "I'm very satisfied with how democracy works in Wales."}),
         nations=(3,)),
    Item("trustYourMP", "trust", ("trustYourMPW27",),
         by_code({1: "I don't trust my local MP one bit.", 2: "I've little trust in my local MP.", 5: "I trust my local MP a fair amount.",
                  6: "I trust my local MP a good deal.", 7: "I trust my local MP a great deal."}), weight=0.6),
    Item("genTrust", "social-trust", ("genTrustW27", "genTrustW23"),
         by_code({1: "Most people can be trusted.", 2: "You can't be too careful in dealing with people."})),
    Item("homenorm", "home-ownership", ("homenormW23",),
         agree5("If you haven't bought a home by 40, you haven't made it.",
                "To count as a success you need to own a home by 40.",
                "You don't need to own a home by 40 to be a success.",
                "Owning a home by 40 has nothing to do with success in life."), weight=0.6),
    Item("econSecurityFuture", "personal-outlook", ("EconSecurityFutureW25", "EconSecurityFutureW23"),
         by_code({1: "I expect to be a lot better off in ten years' time.", 2: "I expect to be a little better off in ten years.",
                  4: "I expect to be a little worse off in ten years.", 5: "I expect to be a lot worse off in ten years' time."}), weight=0.6),
    Item("statusLadder", "status", ("statusTopBottomW30", "statusTopBottomW21"),
         by_code({1: "I'd put myself right at the bottom of the pile in society.", 2: "I'd put myself near the bottom of the pile in society.",
                  3: "I'd put myself near the bottom of the pile in society.", 4: "I'd put myself a bit below the middle of society.",
                  7: "I'd put myself a bit above the middle of society.", 8: "I'd put myself near the top of the pile in society.",
                  9: "I'd put myself near the top of the pile in society.", 10: "I'd put myself right at the top of the pile in society."}),
         weight=0.5),
    # Welfare and work (wave 20 values battery)
    Item("jobForAll", "state-role", ("jobForAllW20",),
         agree5("It's the government's job to make sure everyone who wants work has it.",
                "Government should provide a job for everyone who wants one.",
                "It isn't the government's job to find everyone work.", "Providing jobs for everyone is not the government's job at all.")),
    Item("stateOwnership", "state-role", ("stateOwnershipW20",),
         agree5("Major public services and industries should definitely be in state hands.",
                "Major public services and industries ought to be state-owned.",
                "Major industries shouldn't be in state hands.", "State ownership of major industries is the wrong way to go."), weight=0.7),
    Item("privateEnterprise", "state-role", ("privateEnterpriseW20",),
         agree5("Private enterprise is definitely the best way to fix Britain's economic problems.",
                "Private enterprise is the best way to solve Britain's economic problems.",
                "Private enterprise isn't the answer to Britain's economic problems.",
                "Leaving our economic problems to private enterprise would be a disaster."), weight=0.7),
    Item("govtHandouts", "welfare-attitudes", ("govtHandoutsW20",),
         agree5("Far too many people like living off government handouts.", "Too many people rely on government handouts these days.",
                "I don't think too many people rely on handouts.", "The idea people choose to live off handouts is a myth.")),
    Item("benefitsNotDeserved", "welfare-attitudes", ("benefitsNotDeservedW20",),
         agree5("Plenty of people on benefits don't really deserve the help.", "Many people on benefits don't really deserve help.",
                "Most people on benefits genuinely need the help.", "People on benefits fully deserve the help they get.")),
    Item("reasonForUnemployment", "welfare-attitudes", ("reasonForUnemploymentW20",),
         agree5("When someone's out of work, it's almost never their own fault.", "Unemployment is usually through no fault of the person's own.",
                "Being out of work is often the person's own doing.", "People out of work usually have themselves to blame."), weight=0.7),
    Item("immigrantsWelfare", "immigration", ("immigrantsWelfareStateW20",),
         agree5("Immigrants are clearly a burden on the welfare state.", "Immigrants are a burden on the welfare state.",
                "I don't think immigrants are a burden on the welfare state.", "Immigrants are no burden on the welfare state at all."), weight=0.6),
    Item("immigCultural", "immigration", ("immigCulturalW27", "immigCulturalW24"),
         by_code({1: "Immigration undermines Britain's culture - badly.", 2: "Immigration undermines British cultural life.",
                  3: "On balance, immigration takes something away from British culture.",
                  5: "On balance, immigration adds something to British culture.",
                  6: "Immigration enriches British cultural life.", 7: "Immigration enriches Britain's culture enormously."}), weight=0.6),
    Item("studentsMore", "immigration", ("studentsMoreW26", "studentsMoreW25"),
         scale11("Britain should take far fewer foreign students.", "I'd take fewer foreign students.",
                 "I'd happily take more foreign students.", "Britain should welcome many more foreign students."), weight=0.4),
    Item("euMore", "immigration", ("euMoreW26", "euMoreW25"),
         scale11("Far fewer workers from the EU should be let in.", "I'd let in fewer workers from the EU.",
                 "I'd let in more workers from the EU.", "Britain should let in many more workers from the EU."), weight=0.4),
    Item("familiesMore", "immigration", ("familiesMoreW26", "familiesMoreW25"),
         scale11("Far fewer relatives of people already here should be let in.", "I'd let in fewer relatives of people already here.",
                 "I'd let in more relatives of people already settled here.", "Families of people already here should be welcomed in."), weight=0.4),
    # Brexit, looking back
    Item("brexitEcon", "brexit-effects", ("effectsEUEconRetroW27",),
         by_code({1: "Brexit has made the economy much worse.", 2: "Brexit has made the economy worse.",
                  3: "Brexit hasn't made much difference to the economy.", 4: "Brexit has made the economy better.",
                  5: "Brexit has made the economy much better."})),
    Item("brexitNHS", "brexit-effects", ("effectsNHSRetroW27",),
         by_code({1: "Brexit has made the NHS much worse.", 2: "Brexit has made the NHS worse.",
                  4: "Brexit has been good for the NHS.", 5: "Brexit has been very good for the NHS."}), weight=0.6),
    Item("brexitImmigration", "brexit-effects", ("effectsEUImmigrationRetroW27",),
         by_code({1: "Brexit has made immigration much worse.", 2: "Brexit has made immigration worse.",
                  3: "Brexit hasn't made much difference to immigration.", 4: "Brexit has made immigration better.",
                  5: "Brexit has made immigration much better."}), weight=0.6),
    Item("brexitVoice", "brexit-effects", ("euLeaveVoiceRetroW27",),
         by_code({1: "Brexit has left Britain with far less clout in the world.", 2: "Brexit has left Britain with less clout in the world.",
                  4: "Brexit has given Britain more clout in the world.", 5: "Brexit has given Britain far more clout in the world."}), weight=0.6),
    Item("brexitFinance", "brexit-effects", ("effectsEUFinanceRetroW27",),
         by_code({1: "Brexit has left me personally much worse off.", 2: "Brexit has left me personally worse off.",
                  3: "Brexit hasn't made any difference to my own finances.", 4: "Brexit has left me personally better off.",
                  5: "Brexit has left me personally much better off."}), weight=0.6),
    Item("handleEUPost", "brexit-effects", ("handleEUPostW27",),
         by_code({1: "The government made a complete mess of taking Britain out of the EU.", 2: "The government made a mess of taking Britain out of the EU.",
                  4: "The government handled leaving the EU well.", 5: "The government handled leaving the EU very well."}), weight=0.5),
    Item("euRefDoOver", "europe", ("euRefDoOverW29",),
         by_code({1: "I'd like another referendum on EU membership.", 0: "I don't want another EU referendum."}), weight=0.7),
    Item("euID", "europe", ("euIDW27", "euIDW25"),
         by_code({1: "I still think of myself as a Remainer.", 2: "I still think of myself as a Leaver.",
                  3: "I don't think of myself as a Leaver or a Remainer."}), weight=0.8),
    # America, free speech and the wider world
    Item("usTies", "usa", ("selfUSTie1W30",),
         scale11("Britain should get much closer to the United States economically.", "I'd like closer economic ties with the US.",
                 "I'd keep the United States at arm's length.", "Britain must protect its independence from the United States.")),
    Item("freeSpeechRacistTV", "free-speech", ("freeSpeechRacistTVW30",),
         by_code({1: "Someone who thinks white people are superior should never be given airtime on TV.",
                  2: "A white supremacist probably shouldn't be given airtime on TV.",
                  3: "Even a white supremacist should probably be allowed on TV to put their case.",
                  4: "Even a white supremacist should be allowed on TV to put their case - that's free speech."}), weight=0.6),
    Item("freeSpeechIslamistTV", "free-speech", ("freeSpeechIslamistTVW30",),
         by_code({1: "A preacher who preaches hatred of the West should never be given airtime on TV.",
                  2: "A preacher who preaches hatred of the West probably shouldn't be on TV.",
                  3: "Even a preacher who preaches hatred of the West should probably be allowed on TV.",
                  4: "Even a preacher who preaches hatred of the West should be allowed on TV - that's free speech."}), weight=0.6),
    Item("freeSpeechLeaderElection", "free-speech", ("freeSpeechLeaderElectionW30",),
         by_code({1: "Someone who wants to scrap elections for a strongman should never be allowed to stand for office.",
                  2: "Someone who wants to scrap elections probably shouldn't be allowed to stand for office.",
                  3: "Even someone who wants to scrap elections should probably be allowed to stand.",
                  4: "Even someone who wants to scrap elections should be free to stand for office."}), weight=0.5),
    # Local area
    Item("amenities", "local-area", ("amenitiesW21",),
         by_code({5: "My area is very well served by shops, schools and services.", 4: "My area is fairly well served by shops, schools and services.",
                  2: "My area is fairly poorly served by shops, schools and services.", 1: "My area is very poorly served by shops, schools and services."}),
         weight=0.6),
    Item("mapRepresent", "local-voice", ("mapRepresentW21",),
         by_code({1: "Nobody in national government listens to people round here.", 2: "National government doesn't listen much to people round here.",
                  3: "National government listens to people round here a bit.", 4: "National government listens to people round here a great deal."}),
         weight=0.6),
    Item("areaRichPoor", "local-area", ("areaRichPoorW21",), max_valid=101,
         phrase=lambda a: ("My area is among the poorest in the country." if a <= 25 else "My area is poorer than most." if a <= 40
                           else "My area is better off than most." if 60 <= a < 75 else "My area is one of the richest in the country." if a >= 75 else None),
         weight=0.6),
    Item("areaSpirit", "local-area", ("statusAreaSpiritW30", "statusAreaSpiritW25"),
         agree5("There's no community spirit round here any more.", "There's a lack of community spirit where I live.",
                "There's a decent community spirit where I live.", "Community spirit round here is strong."), weight=0.6),
    Item("areaCrime", "local-area", ("statusAreaCrimeW30", "statusAreaCrimeW25"),
         agree5("There's a lot of crime round where I live.", "Crime is a real problem in my area.",
                "Crime isn't much of a problem where I live.", "There's hardly any crime round here."), weight=0.6),
    Item("areaShops", "local-area", ("statusAreaShopsW30", "statusAreaShopsW25"),
         agree5("My area is full of interesting restaurants, bars and shops.", "There are good restaurants, bars and shops round here.",
                "There's not much in the way of restaurants, bars and shops round here.",
                "There's nowhere worth going round here - no decent bars, shops or restaurants."), weight=0.5),
    # Scotland and Wales
    Item("scotRefID", "independence", ("scotRefIDW27",),
         by_code({1: "I'm firmly on the Yes side of the independence debate.", 2: "I'm on the No side of the independence debate.",
                  3: "I don't feel on either side of the independence debate."}), nations=(2,), weight=0.8),
    Item("referendumSettled", "independence", ("referendumSettledW29", "referendumSettledW27"),
         by_code({1: "There should be another independence referendum within ten years.",
                  0: "There shouldn't be another independence referendum for at least ten years."}), nations=(2,), weight=0.8),
    Item("sovereignty", "independence", ("sovereignty1W29",),
         agree5("People in Scotland, and nobody else, should have the final say on how Scotland is governed.",
                "People in Scotland should have the final say on how Scotland is governed.",
                "I don't think Scotland alone should decide how it's governed.",
                "Scotland shouldn't decide alone how it's governed - we're part of the UK."), nations=(2,), weight=0.6),
    Item("scotIndepEconomy", "independence", ("scotIndepEconomyW25", "scotIndepEconomyW23"),
         by_code({5: "Scotland's economy would certainly be worse off under independence.", 4: "Scotland's economy would probably be worse off under independence.",
                  2: "I don't think independence would hurt Scotland's economy.", 1: "Independence wouldn't hurt Scotland's economy at all."}),
         nations=(2,), weight=0.6),
    Item("scotIndepBetterOff", "independence", ("scotIndepMeBetterOffW25", "scotIndepMeBetterOffW23"),
         by_code({5: "I'd definitely be better off if Scotland were independent.", 4: "I'd probably be better off if Scotland were independent.",
                  2: "I probably wouldn't be better off under independence.", 1: "I'd be worse off if Scotland went independent."}),
         nations=(2,), weight=0.6),
    Item("happyScotIndep", "independence", ("happyScotIndepResultW21",),
         scale11("I'd be gutted if Scotland left the UK.", "I'd be disappointed if Scotland left the UK.",
                 "I'd be fairly happy to see Scotland go independent.", "I'd be delighted to see Scotland become independent."), weight=0.5),
    Item("scotDevoMax", "devolution", ("scotDevoMaxW21",),
         by_code({5: "Holyrood should have many more powers.", 4: "Holyrood should have some more powers.", 3: "Holyrood's powers are about right.",
                  2: "Holyrood should have fewer powers.", 1: "Holyrood should have far fewer powers."}), nations=(2,), weight=0.8),
    Item("devoPrefWales", "devolution", ("devoPrefWalesW27", "devoPrefWalesW21"),
         by_code({1: "Wales shouldn't have a devolved government at all.", 2: "The Senedd should have fewer powers.",
                  3: "I'd leave Welsh devolution as it is.", 4: "The Senedd should have more powers.", 5: "Wales should be independent."}),
         nations=(3,), weight=1.0),

    # ------------------------------------------------------------------
    # What they actually did: the May 2026 elections and the 2024 general election
    Item("localVote", "recent-vote", (), custom=local_vote, nations=(1,), weight=1.2),
    Item("holyroodVote", "recent-vote", (), custom=holyrood_vote, nations=(2,), weight=1.6),
    Item("seneddVote", "recent-vote", (), custom=senedd_vote, nations=(3,), weight=1.6),
    Item("turnoutLikely", "turnout", ("turnoutUKGeneralW31",),
         by_code({1: "If there were an election tomorrow, I very probably wouldn't vote.",
                  2: "If there were an election tomorrow, I probably wouldn't bother voting.",
                  3: "If there were an election tomorrow, I'm not sure I'd bother voting."}), weight=0.6, fallback=False),
    # Parties: likes, bonds, unity, who they look after
    Item("regionFairShare", "fair-share", ("regionFairShareW31", "regionFairShareW21"),
         fair_share5("My region", "of government spending"), nations=(1,), weight=0.4),
    # Attitudes to gender (wave 27)
    Item("benevolentSexism", "gender-attitudes", ("benevolentSexism1W27",),
         agree5("Women should always be cherished and protected by men.", "Women should be cherished and protected by men.",
                "I don't think women need men to cherish and protect them.", "The idea that women need protecting by men is outdated."),
         weight=0.4),
    Item("hostileSexism", "gender-attitudes", ("hostileSexism3W27",),
         agree5("Most women really do take innocent remarks as sexist.", "Most women take innocent remarks as sexist.",
                "I don't think women go round taking innocent remarks as sexist.", "Women don't take innocent remarks as sexist - that's a myth."),
         weight=0.4),

    # --- added after the wave-20+ audit (docs/unused-questions.md) ---
    Item("brexitEcon", "economy-blame", (), custom=impact_item(("brexitEconImpactW31", "brexitEconImpactW30"),
         "Brexit has done the economy a lot of damage.", "Brexit has done the economy some damage.",
         "Brexit has been good for the economy.", "Brexit has been very good for the economy."), weight=0.8),
    Item("worldEcon", "economy-blame", (), custom=impact_item(("globalEconomyEconImpactW31", "globalEconomyEconImpactW30"),
         "The state of the world economy has hit Britain hard.", "The state of the world economy has hurt Britain a bit.",
         "The world economy has been good for Britain.", "The world economy has been very good for Britain."), weight=0.5),
    Item("conflictEcon", "economy-blame", (), custom=impact_item(("conflictEconImpactW31",),
         "Global conflicts like Iran and Ukraine have hit the economy hard.", "Global conflicts like Iran and Ukraine have hurt the economy a bit.",
         "Global conflicts like Iran and Ukraine have been good for the economy.", "Global conflicts like Iran and Ukraine have been very good for the economy."), weight=0.7),
    Item("govtEconImpact", "economy-blame", (), custom=impact_item(("ukGovtEconImpactW31", "ukGovtEconImpactW30"),
         "This government has done the economy a lot of damage.", "This government has done the economy some damage.",
         "This government has been good for the economy.", "This government has been very good for the economy."), weight=0.7),
    Item("lastGovtEconImpact", "economy-blame", (), custom=impact_item(("ukLastGovtEconImpactW31", "ukLastGovtEconImpactW30"),
         "The last government did the economy a lot of damage.", "The last government did the economy some damage.",
         "The last government was good for the economy.", "The last government was very good for the economy."), weight=0.6),
    Item("brexitEconScot", "economy-blame", (), custom=impact_item(("brexitEconImpactScotW31", "brexitEconImpactScotW30"),
         "Brexit has done Scotland's economy a lot of damage.", "Brexit has done Scotland's economy some damage.",
         "Brexit has been good for Scotland's economy.", "Brexit has been very good for Scotland's economy."), nations=(2,), weight=0.6),
    Item("scotGovtEcon", "scottish-government", (), custom=impact_item(("scotGovtEconImpactScotW31", "scotGovtEconImpactScotW30"),
         "The Scottish Government has done Scotland's economy a lot of damage.", "The Scottish Government has done Scotland's economy some damage.",
         "The Scottish Government has been good for Scotland's economy.", "The Scottish Government has been very good for Scotland's economy."), nations=(2,), weight=0.7),
    Item("conflictEconScot", "economy-blame", (), custom=impact_item(("conflictEconImpactScotW31",),
         "Global conflicts like Iran and Ukraine have hit Scotland's economy hard.", "Global conflicts like Iran and Ukraine have hurt Scotland's economy a bit.",
         "Global conflicts like Iran and Ukraine have been good for Scotland's economy.", "Global conflicts like Iran and Ukraine have been very good for Scotland's economy."), nations=(2,), weight=0.5),
    Item("conflictEconWales", "economy-blame", (), custom=impact_item(("conflictEconImpactWalesW31",),
         "Global conflicts like Iran and Ukraine have hit Wales's economy hard.", "Global conflicts like Iran and Ukraine have hurt Wales's economy a bit.",
         "Global conflicts like Iran and Ukraine have been good for Wales's economy.", "Global conflicts like Iran and Ukraine have been very good for Wales's economy."), nations=(3,), weight=0.5),
    Item("brexitEconWales", "economy-blame", (), custom=impact_item(("brexitEconImpactWalesW31", "brexitEconImpactWalesW30"),
         "Brexit has done Wales's economy a lot of damage.", "Brexit has done Wales's economy some damage.",
         "Brexit has been good for Wales's economy.", "Brexit has been very good for Wales's economy."), nations=(3,), weight=0.6),
    Item("welshGovtEcon", "welsh-government", (), custom=impact_item(("welshGovtEconImpactWalesW31", "welshGovtEconImpactWalesW30"),
         "The Welsh Government has done Wales's economy a lot of damage.", "The Welsh Government has done Wales's economy some damage.",
         "The Welsh Government has been good for Wales's economy.", "The Welsh Government has been very good for Wales's economy."), nations=(3,), weight=0.7),
    Item("freeSpeechRacistElection", "free-speech", ("freeSpeechRacistElectionW30",),
         by_code({1: "A white supremacist should never be allowed to stand for election.", 2: "A white supremacist probably shouldn't be allowed to stand for election.",
                  3: "Even a white supremacist should probably be allowed to stand for election.", 4: "Even a white supremacist should be free to stand for election."}), weight=0.4),
    Item("freeSpeechRacistSpeech", "free-speech", ("freeSpeechRacistSpeechW30",),
         by_code({1: "A white supremacist should never be allowed to hold a public meeting round here.", 2: "A white supremacist probably shouldn't be allowed to speak in public round here.",
                  3: "Even a white supremacist should probably be allowed to speak in public round here.", 4: "Even a white supremacist should be allowed to hold a public meeting round here."}), weight=0.4),
    Item("freeSpeechRacistTeach", "free-speech", ("freeSpeechRacistTeachW30",),
         by_code({1: "A white supremacist should never be allowed to teach in a school.", 2: "A white supremacist probably shouldn't be allowed to teach in a school.",
                  3: "Even a white supremacist should probably be allowed to teach in a school.", 4: "Even a white supremacist should be allowed to teach in a school."}), weight=0.4),
    Item("freeSpeechIslamistElection", "free-speech", ("freeSpeechIslamistElectionW30",),
         by_code({1: "A preacher who preaches hatred of the West should never be allowed to stand for election.", 2: "A preacher who preaches hatred of the West probably shouldn't stand for election.",
                  3: "Even a preacher who preaches hatred of the West should probably be allowed to stand for election.", 4: "Even a preacher who preaches hatred of the West should be free to stand for election."}), weight=0.4),
    Item("freeSpeechIslamistSpeech", "free-speech", ("freeSpeechIslamistSpeechW30",),
         by_code({1: "A preacher who preaches hatred of the West should never be allowed to speak in public round here.", 2: "A preacher who preaches hatred of the West probably shouldn't speak in public round here.",
                  3: "Even a preacher who preaches hatred of the West should probably be allowed to speak round here.", 4: "Even a preacher who preaches hatred of the West should be allowed to speak round here."}), weight=0.4),
    Item("freeSpeechIslamistTeach", "free-speech", ("freeSpeechIslamistTeachW30",),
         by_code({1: "A preacher who preaches hatred of the West should never be allowed to teach in a school.", 2: "A preacher who preaches hatred of the West probably shouldn't teach in a school.",
                  3: "Even a preacher who preaches hatred of the West should probably be allowed to teach in a school.", 4: "Even a preacher who preaches hatred of the West should be allowed to teach in a school."}), weight=0.4),
    Item("freeSpeechLeaderSpeech", "free-speech", ("freeSpeechLeaderSpeechW30",),
         by_code({1: "Someone who wants to scrap elections should never be allowed to speak in public round here.", 2: "Someone who wants to scrap elections probably shouldn't speak in public round here.",
                  3: "Even someone who wants to scrap elections should probably be allowed to speak round here.", 4: "Even someone who wants to scrap elections should be allowed to speak round here."}), weight=0.4),
    Item("freeSpeechLeaderTeach", "free-speech", ("freeSpeechLeaderTeachW30",),
         by_code({1: "Someone who wants to scrap elections should never be allowed to teach in a school.", 2: "Someone who wants to scrap elections probably shouldn't teach in a school.",
                  3: "Even someone who wants to scrap elections should probably be allowed to teach in a school.", 4: "Even someone who wants to scrap elections should be allowed to teach in a school."}), weight=0.4),
    Item("freeSpeechLeaderTV", "free-speech", ("freeSpeechLeaderTVW30",),
         by_code({1: "Someone who wants to scrap elections should never be given airtime on TV.", 2: "Someone who wants to scrap elections probably shouldn't be on TV.",
                  3: "Even someone who wants to scrap elections should probably be allowed on TV.", 4: "Even someone who wants to scrap elections should be allowed on TV - that's free speech."}), weight=0.4),
    Item("efficacyEffort", "political-interest", ("efficacyTooMuchEffortW31", "efficacyTooMuchEffortW30"),
         agree5("Being active in politics takes far too much time and effort.", "Getting involved in politics takes too much time and effort.",
                "Getting involved in politics isn't too much effort.", "It's no great effort to get involved in politics."), weight=0.5),
    Item("asylum", "immigration", ("asylumMoreW26", "asylumMoreW25"),
         scale11("Britain should take in far fewer asylum seekers.", "I'd let in fewer asylum seekers.",
                 "I'd take in a few more asylum seekers.", "Britain should take in many more asylum seekers."), weight=0.7),
    Item("nonEuWorkers", "immigration", ("noneuMoreW26", "noneuMoreW25"),
         scale11("Britain should let in far fewer workers from outside the EU.", "I'd let in fewer workers from outside the EU.",
                 "I'd let in a few more workers from outside the EU.", "Britain should let in many more workers from outside the EU."), weight=0.5),
    Item("trains", "privatisation", ("nationalizeTrainsW26", "nationalizeTrainsW25"),
         by_code({1: "The railways should be run entirely by the public sector.", 2: "The railways should mostly be publicly run.",
                  4: "The railways should mostly be privately run.", 5: "The railways should be run entirely by private companies."}), weight=0.7),
    Item("globalisation", "globalisation", ("globalGoodOverallW21", "globalGoodOverallW20"),
         by_code({1: "Globalisation has been mainly bad for Britain.", 2: "Globalisation has done Britain more harm than good.",
                  4: "Globalisation has done Britain more good than harm.", 5: "Globalisation has been mainly good for Britain."}), weight=0.5),
    Item("fairElections", "elections", ("expectGoodConductGeneralW29", "expectGoodConductGeneralW27"),
         by_code({1: "I'm confident our general elections are run fairly.", 2: "I'm fairly confident our elections are run fairly.",
                  4: "I'm not convinced our elections are run fairly.", 5: "I don't believe our general elections are run fairly."}), weight=0.5),
    Item("voterIdDifficult", "voter-id", ("voterIDDifficultW25",),
         agree5("Having to show ID makes voting a lot harder.", "Having to show ID makes voting harder.",
                "Showing ID doesn't make voting any harder.", "Showing ID at the polling station is no bother at all."), weight=0.4),
    Item("voterIdFraud", "voter-id", ("voterIDFraudW25",),
         agree5("Voter ID stops fraud.", "Voter ID helps stop fraud.", "Voter ID doesn't stop fraud.", "Voter ID does nothing to stop fraud."), weight=0.4),
    Item("populismWill", "populism", ("populism1W27", "populism1W26"),
         agree5("MPs should follow the will of the people.", "MPs should generally follow the will of the people.",
                "MPs shouldn't just follow the will of the people.", "MPs are there to use their judgement, not just follow the will of the people."), weight=0.6),
    Item("populismCitizen", "populism", ("populism4W27", "populism4W26"),
         agree5("I'd much rather be represented by an ordinary citizen than a career politician.", "I'd rather be represented by an ordinary citizen than a career politician.",
                "I'd rather be represented by a professional politician than an ordinary citizen.", "Give me a professional politician over an ordinary citizen any day."), weight=0.6),
    Item("privateHealthEfficient", "private-healthcare", ("privateHospEfficientW26",),
         agree5("Private companies run healthcare far more efficiently than the NHS.", "Private companies provide healthcare more efficiently than the NHS.",
                "Private companies don't provide healthcare any more efficiently than the NHS.", "The idea that private companies run healthcare better than the NHS is nonsense."), weight=0.6),
    Item("privateHealthTax", "private-healthcare", ("privateHospTaxW26",),
         agree5("Private healthcare takes a lot of pressure off the taxpayer, so it benefits everyone.", "Private healthcare takes pressure off the taxpayer, so it benefits everyone.",
                "Private healthcare doesn't benefit everyone just because it eases the burden on taxpayers.", "I don't accept that private healthcare helps everyone by easing the tax burden."), weight=0.5),
    Item("sexismWomenAppreciate", "sexism", ("hostileSexism1W27",),
         agree5("Most women don't appreciate all that men do for them.", "Most women don't fully appreciate what men do for them.",
                "It's not true that women don't appreciate what men do for them.", "The idea that women don't appreciate what men do for them is rubbish."), weight=0.4),
    Item("sexismWomenPower", "sexism", ("hostileSexism2W27",),
         agree5("Women seek power by getting control over men.", "Women tend to seek power by getting control over men.",
                "Women don't seek power by controlling men.", "The idea that women seek power by controlling men is rubbish."), weight=0.4),
    Item("sexismMenAppreciate", "sexism", ("hostileSexismM1W27",),
         agree5("Most men don't appreciate all that women do for them.", "Most men don't fully appreciate what women do for them.",
                "It's not true that men don't appreciate what women do for them.", "The idea that men don't appreciate what women do for them is rubbish."), weight=0.4),
    Item("sexismMenPower", "sexism", ("hostileSexismM2W27",),
         agree5("Men seek power by getting control over women.", "Men tend to seek power by getting control over women.",
                "Men don't seek power by controlling women.", "The idea that men seek power by controlling women is rubbish."), weight=0.4),
    Item("sexismPurity", "sexism", ("benevolentSexism2W27",),
         agree5("Many women have a quality of purity that few men possess.", "A lot of women have a purity about them that few men do.",
                "Women aren't any purer than men.", "The idea that women have some special purity men lack is nonsense."), weight=0.3),
    Item("sexismPedestal", "sexism", ("benevolentSexism3W27",),
         agree5("A good woman should be set on a pedestal by her man.", "A good woman deserves to be put on a pedestal by her man.",
                "No woman needs putting on a pedestal by her man.", "Putting a woman on a pedestal is the last thing a good man should do."), weight=0.3),
    Item("scotRefBond", "independence", (), custom=scot_ref_bond, nations=(2,), weight=0.8),
    Item("scotRejoinEU", "independence", ("scotIndepRejoinEUW25", "scotIndepRejoinEUW23"),
         by_code({1: "An independent Scotland would have no chance of rejoining the EU.", 2: "An independent Scotland probably couldn't rejoin the EU.",
                  4: "An independent Scotland would probably be able to rejoin the EU.", 5: "An independent Scotland would be able to rejoin the EU."}), nations=(2,), weight=0.6),
    Item("scotSovereignty", "europe", ("sovereignty2W29",),
         agree5("The UK as a whole voted to leave the EU, and Scotland has to accept that.", "The UK voted to leave, and Scotland should accept that.",
                "Scotland shouldn't have to accept Brexit just because the UK as a whole voted for it.", "Scotland should never have been dragged out of the EU against its will."), nations=(2,), weight=0.6),
    Item("euRefBond", "europe", (), custom=eu_ref_bond, weight=0.5),
    Item("euRegret", "europe", (), custom=eu_regret, weight=0.6),
    Item("socialCircle", "social-circle", (), custom=social_circle_vote, weight=0.5),
    Item("satDemUK", "democracy", ("satDemUKW29", "satDemUKW27"),
         by_code({1: "I'm very dissatisfied with how democracy works in the UK.", 2: "I'm a little dissatisfied with how democracy works in the UK.",
                  3: "I'm fairly satisfied with how democracy works in the UK.", 4: "I'm very satisfied with how democracy works in the UK."}), weight=0.5),
    Item("satDemEng", "democracy", ("satDemEngW29",),
         by_code({1: "I'm very dissatisfied with how democracy works in England.", 2: "I'm a little dissatisfied with how democracy works in England.",
                  3: "I'm fairly satisfied with how democracy works in England.", 4: "I'm very satisfied with how democracy works in England."}), nations=(1,), weight=0.4),
    Item("localSchools", "local-area", ("statusAreaEduW30", "statusAreaEduW25"),
         agree5("The schools round here are excellent.", "The schools round here are good.", "The schools round here aren't up to much.", "The schools round here are poor."), weight=0.5),
    Item("localSpaces", "local-area", ("statusAreaSpacesW30", "statusAreaSpacesW25"),
         agree5("The buildings and public spaces round here are really well kept.", "The buildings and public spaces round here are well kept.",
                "The buildings and public spaces round here are a bit run down.", "The buildings and public spaces round here are badly run down."), weight=0.5),
    Item("ukGovtEconScot", "economy-blame", (), custom=impact_item(("ukGovtEconImpactScotW31", "ukGovtEconImpactScotW30"),
         "The UK government has done Scotland's economy a lot of damage.", "The UK government has done Scotland's economy some damage.",
         "The UK government has been good for Scotland's economy.", "The UK government has been very good for Scotland's economy."), nations=(2,), weight=0.6),
    Item("lastGovtEconScot", "economy-blame", (), custom=impact_item(("ukLastGovtEconImpactScotW31", "ukLastGovtEconImpactScotW30"),
         "The last UK government did Scotland's economy a lot of damage.", "The last UK government did Scotland's economy some damage.",
         "The last UK government was good for Scotland's economy.", "The last UK government was very good for Scotland's economy."), nations=(2,), weight=0.5),
    Item("ukGovtEconWales", "economy-blame", (), custom=impact_item(("ukGovtEconImpactWalesW31", "ukGovtEconImpactWalesW30"),
         "The UK government has done Wales's economy a lot of damage.", "The UK government has done Wales's economy some damage.",
         "The UK government has been good for Wales's economy.", "The UK government has been very good for Wales's economy."), nations=(3,), weight=0.6),
    Item("lastGovtEconWales", "economy-blame", (), custom=impact_item(("ukLastGovtEconImpactWalesW31", "ukLastGovtEconImpactWalesW30"),
         "The last UK government did Wales's economy a lot of damage.", "The last UK government did Wales's economy some damage.",
         "The last UK government was good for Wales's economy.", "The last UK government was very good for Wales's economy."), nations=(3,), weight=0.5),
    Item("warmMuslim", "warmth", ("warmMuslimW26",), warmth_item("Muslims"), weight=0.4),
    Item("warmJewish", "warmth", ("warmJewishW26",), warmth_item("Jewish people"), weight=0.4),
    Item("warmChristian", "warmth", ("warmChristianW26",), warmth_item("Christians"), weight=0.4),
    Item("warmAtheist", "warmth", ("warmAtheistW26",), warmth_item("non-religious people"), weight=0.4),
    Item("equalityBME", "equality", ("blackEqualityW27", "blackEqualityW23"), gone_too_far_item("equal opportunities for ethnic minorities"), weight=0.5),
    Item("equalityWomen", "equality", ("femaleEqualityW27", "femaleEqualityW23"), gone_too_far_item("equal opportunities for women"), weight=0.5),
    Item("equalityGay", "equality", ("gayEqualityW27", "gayEqualityW23"), gone_too_far_item("equal opportunities for gay and lesbian people"), weight=0.5),
]


# Top-issue category (codes.TOP_ISSUE) -> bubble topics on the same subject, so one bubble can speak to it
ISSUE_TOPICS: dict[int, set[str]] = {
    1: {"nhs-cuts", "nhs-direction", "private-healthcare", "private-health"},
    2: {"schools", "curriculum", "private-schools", "breakfast-clubs", "local-area"},
    3: {"elections", "party-difference", "tactical-voting", "electoral-system"},
    4: {"politicians", "trust", "democracy", "populism", "party-difference", "strong-leader"},
    5: {"party-difference", "politicians"},
    6: {"social-trust", "discrimination", "identity", "free-speech", "offence"},
    7: {"young-people", "obey-authority", "censorship", "same-sex-parents", "gender-attitudes", "warmth"},
    8: {"identity", "immigration", "statues", "pride", "monarchy"},
    9: {"discrimination", "diversity-training", "statues", "offence", "equality", "warmth"},
    10: {"benefits", "welfare-attitudes"},
    11: {"free-speech", "defence", "crime-direction"},
    12: {"immigration", "immigration-direction"},
    13: {"immigration", "immigration-direction"},
    14: {"crime-direction", "sentencing", "death-penalty"},
    15: {"europe", "brexit-effects", "economy-blame", "globalisation"},
    16: {"electoral-system", "monarchy", "voting-age", "democracy", "devolution"},
    17: {"globalisation", "europe", "brexit-effects", "usa", "trump"},
    18: {"devolution", "fair-share", "local-voice", "scottish-government", "welsh-government", "independence"},
    19: {"independence", "scottish-government"},
    21: {"usa", "trump", "israel-palestine", "foreign-aid", "defence", "nuclear-weapons"},
    22: {"defence", "nuclear-weapons", "israel-palestine"},
    23: {"defence", "nuclear-weapons", "national-service"},
    24: {"israel-palestine", "usa", "defence", "economy-blame"},
    25: {"government-handling", "economy-direction"},
    26: {"economy-direction", "economy-outlook", "economy-blame", "tax-and-spend"},
    27: {"personal-outlook", "cost-of-living", "economy-outlook"},
    28: {"zero-hours", "automation", "management", "economy-direction"},
    29: {"tax-and-spend", "inheritance-tax", "deficit", "redistribution"},
    30: {"deficit", "spending-cuts", "tax-and-spend"},
    31: {"cost-of-living", "economy-direction", "economy-blame"},
    32: {"cost-of-living", "economy-direction", "personal-outlook", "public-energy"},
    33: {"redistribution", "fair-share-wealth", "benefits", "inequality", "one-law"},
    34: {"spending-cuts", "local-cuts", "nhs-cuts", "tax-and-spend", "council"},
    35: {"inequality", "redistribution", "fair-share-wealth", "one-law", "big-business"},
    36: {"housing", "home-ownership"},
    37: {"nhs-direction", "spending-cuts", "local-cuts"},
    38: {"pensions"},
    39: {"privatisation", "nationalisation", "local-cuts"},
    40: {"climate", "green-rules", "growth-v-environment", "public-energy"},
    41: {"obey-authority", "young-people", "sentencing", "crime-direction"},
    42: {"free-speech", "censorship", "voter-id", "strong-leader", "smoking-ban"},
    43: {"state-role", "tax-and-spend", "privatisation", "nationalisation", "spending-cuts"},
    44: {"big-business", "management", "redistribution", "one-law", "fair-share-wealth"},
    49: {"economy-direction", "economy-blame"},
    50: {"trans-sport", "same-sex-parents", "gender-attitudes", "discrimination", "sexism", "equality"},
}

# Topics that are, in effect, the same issue. A card never carries two bubbles from one theme:
# "it doesn't matter which party is in power" and "there's not much difference between Labour and
# the Tories" are one thought, not two. Topics not listed here are themes of their own.
THEMES: dict[str, set[str]] = {
    "politicians": {"politicians", "party-difference", "populism", "trust", "strong-leader", "experts", "political-interest"},
    "elections": {"democracy", "elections", "electoral-system", "voter-id", "voting-duty", "tactical-voting", "turnout", "voting-age"},
    "economy": {"economy-direction", "economy-outlook", "economy-blame", "cost-of-living", "personal-outlook"},
    "inequality": {"redistribution", "inequality", "fair-share-wealth", "one-law", "big-business", "management"},
    "public-spending": {"tax-and-spend", "deficit", "spending-cuts", "local-cuts"},
    "health": {"nhs-direction", "nhs-cuts", "private-health", "private-healthcare"},
    "immigration": {"immigration", "immigration-direction"},
    "europe": {"europe", "brexit-effects"},
    "environment": {"climate", "green-rules", "growth-v-environment"},
    "public-ownership": {"nationalisation", "privatisation", "public-energy", "state-role"},
    "welfare": {"benefits", "welfare-attitudes"},
    "crime-and-punishment": {"crime-direction", "sentencing", "death-penalty"},
    "traditional-values": {"young-people", "obey-authority", "censorship"},
    "culture-war": {"offence", "statues", "diversity-training", "curriculum"},
    "prejudice-and-equality": {"discrimination", "equality", "warmth"},
    "gender-and-sexuality": {"trans-sport", "same-sex-parents", "sexism", "gender-attitudes"},
    "identity": {"identity", "pride"},
    "nation": {"independence", "devolution", "fair-share", "scottish-government", "welsh-government", "local-voice"},
    "local-area": {"local-area", "council"},
    "housing": {"housing", "home-ownership"},
    "education": {"schools", "breakfast-clubs", "private-schools"},
    "world": {"usa", "trump", "israel-palestine", "foreign-aid", "globalisation"},
    "defence": {"defence", "nuclear-weapons", "national-service"},
    "work": {"zero-hours", "automation"},
    "government-record": {"uk-government", "government-handling"},
}
TOPIC_THEME = {topic: theme for theme, topics in THEMES.items() for topic in topics}


def theme_of(topic: str) -> str:
    return TOPIC_THEME.get(topic, topic)


NATION_TOPICS = {"identity", "independence", "fair-share", "scottish-government", "welsh-government"}


NEUTRAL = re.compile(r"more or less its fair share|about right|in equal measure|not sure I'd bother")
NEUTRAL_WEIGHT = 0.2  # a middling answer is drawn at a fifth of the weight of a view either way


def is_neutral(text: str) -> bool:
    """A statement that sits on the fence ('England gets more or less its fair share')."""
    return bool(NEUTRAL.search(text))


def candidate_statements(row, country: int, rng=None) -> list[tuple[Item, str]]:
    """Every item this respondent answered with a usable view, one wording each.

    Everything is in the first person: the card's bubble heading ("Her views,
    from her survey answers") does the attribution.
    """
    out = []
    for item in ITEMS:
        text = item.statement(row, country)
        if isinstance(text, tuple):
            text = rng.choice(text) if rng else text[0]
        if text:
            out.append((item, text))
    return out
