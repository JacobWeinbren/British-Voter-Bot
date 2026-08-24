"""The opinion library: survey items turned into first-person speech bubbles.

Each `Item` knows which columns hold the answer (most recent wave first), which
nations it applies to, a topic (so one card never carries two bubbles on the
same subject) and how to phrase each answer. Middling answers either return
None or read as an explicit mixed verdict; either way a clear view comes
first - fence-sitting statements are drawn at NEUTRAL_WEIGHT, because surveys
nudge people towards the middle option.

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
        1: (f"The UK government is handling {subject} very badly.", f"The UK government is making a real mess of {subject}.",
            f"The UK government is doing a very bad job on {subject}."),
        2: (f"The UK government is handling {subject} fairly badly.", f"The UK government isn't doing a great job on {subject}.",
            f"The UK government is doing a fairly poor job on {subject}."),
        4: (f"The UK government is handling {subject} fairly well.", f"The UK government is doing a fairly good job on {subject}.",
            f"The UK government has {subject} reasonably well in hand."),
        5: (f"The UK government is handling {subject} very well.", f"The UK government is doing a very good job on {subject}.",
            f"The UK government has {subject} well in hand."),
    })


def fair_share5(who: str, of_what: str = "from the Union") -> Phraser:
    mid = who[0].lower() + who[1:] if who.startswith("My ") else who  # "my local area" inside a sentence
    return by_code({
        1: (f"{who} gets much less than its fair share {of_what}.", f"{who} gets nowhere near its fair share {of_what}.",
            f"{who} is badly short-changed when it comes to its fair share {of_what}."),
        2: (f"{who} gets a little less than its fair share {of_what}.", f"{who} doesn't quite get its fair share {of_what}.",
            f"{who} gets a bit less than its fair share {of_what}."),
        3: (f"{who} gets more or less its fair share {of_what}.", f"On the whole, {mid} gets more or less its fair share {of_what}.",
            f"I'd say {mid} gets more or less its fair share {of_what}."),
        4: (f"{who} gets a little more than its fair share {of_what}.", f"{who} gets a bit more than its fair share {of_what}.",
            f"{who} does slightly better than its fair share {of_what}."),
        5: (f"{who} gets much more than its fair share {of_what}.", f"{who} gets far more than its fair share {of_what}.",
            f"{who} gets way more than its fair share {of_what}."),
    })


def approve5(who: str) -> Phraser:
    return by_code({
        1: (f"I strongly disapprove of {who}'s record.", f"I think {who} is doing a very bad job."),
        2: (f"I disapprove of how {who} is doing.", f"I'm not happy with how {who} is doing.", f"I don't think much of the job {who} is doing."),
        4: (f"I approve of how {who} is doing.", f"I'm happy with how {who} is doing.", f"I think {who} is doing a decent job."),
        5: (f"I strongly approve of {who}'s record.", f"I think {who} is doing a very good job."),
    })


def marry5(voter: str) -> Phraser:
    return by_code({
        1: (f"I'd be very unhappy if my child married {voter}.", f"It would really upset me if my child married {voter}.",
            f"My child marrying {voter} would make me very unhappy."),
        2: (f"I'd be a bit unhappy if my child married {voter}.", f"I'd be a little put out if my child married {voter}.",
            f"My child marrying {voter} wouldn't exactly please me."),
        4: (f"I'd be happy if my child married {voter}.", f"I'd be fairly pleased if my child married {voter}.",
            f"It would make me happy if my child married {voter}."),
        5: (f"I'd be delighted if my child married {voter}.", f"I'd be thrilled if my child married {voter}.",
            f"My child marrying {voter} would make me very happy."),
    })


def discrimination11(group: str, plural: bool = True) -> Phraser:
    face = "face" if plural else "faces"
    get = "get" if plural else "gets"
    are = "are" if plural else "is"
    cap = f"{group[0].upper()}{group[1:]}"
    return scale11(
        (f"If anything, {group} {get} favoured in Britain these days.", f"{cap} {get} special treatment in Britain these days, if anything.",
         f"These days, {group} {get} the easier ride in Britain, if anything."),
        (f"{cap} {get} a slightly easier ride than most in Britain.", f"{cap} {are} a little better treated than most in Britain.",
         f"If anything, {group} {get} slightly favoured in Britain."),
        (f"{cap} still {face} some discrimination in Britain.", f"There's still some discrimination against {group} in Britain.",
         f"{cap} still {get} a bit of a raw deal in Britain."),
        (f"{cap} {face} a lot of discrimination in Britain today.", f"There's a great deal of discrimination against {group} in Britain today.",
         f"{cap} {get} a very raw deal in Britain today."),
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
        return (f"I'm {adjective}, not British.", f"I see myself as {adjective}, not British.", f"Call me {adjective}, not British.")
    if gap >= 1:
        return (f"I feel more {adjective} than British.", f"I'd say I'm more {adjective} than British.", f"I feel {adjective} more than I feel British.")
    if gap == 0:
        if nation >= 6:
            return (f"I feel strongly {adjective} and strongly British, in equal measure.", f"I'm strongly {adjective} and strongly British, in equal measure.", f"I feel very {adjective} and very British, in equal measure.")
        if nation <= 2:
            return (f"I don't feel especially {adjective} or British.", f"I don't feel particularly {adjective} or particularly British.", f"Being {adjective} or British isn't a big part of how I see myself.")
        return None  # middling and equal: nothing worth a bubble
    if gap >= -2:
        return (f"I feel more British than {adjective}.", f"I'd say I'm more British than {adjective}.", f"I feel British more than I feel {adjective}.")
    return (f"I'm British first - {adjective} comes a distant second.", f"I'm British above all, and being {adjective} comes a long way behind.", f"I see myself as British far more than {adjective}.")


def european_statement(row, country: int) -> str | None:
    answer = value(row, "europeannessW31")
    if answer is None:
        return None
    return {1: ("I don't feel European in the slightest.", "I don't feel European at all.", "I don't feel the least bit European."), 2: ("I don't really feel European.", "I don't feel especially European.", "Being European isn't something I really feel."),
            6: ("I feel European.", "I'd describe myself as European.", "I do feel European."), 7: ("I feel strongly European.", "I feel very strongly European.", "Being European is a big part of who I am.")}.get(int(answer))


def eu_statement(row, country: int) -> str | None:
    """2016 vote crossed with what they would do now."""
    now = value(row, "euRefVoteAfterW31")
    then = value(row, "p_eurefvote")
    if now is None or int(now) not in (0, 1):
        return None
    rejoin = int(now) == 0
    if then is None or int(then) not in (0, 1):
        return ("I'd vote to rejoin the EU if there were another referendum.", "If there were another EU referendum, I'd vote to rejoin.", "Given another referendum on the EU, I'd vote to go back in.") if rejoin \
            else ("I'd vote to stay out of the EU if there were another referendum.", "If there were another EU referendum, I'd vote to stay out.", "Given another referendum on the EU, I'd vote to keep Britain out.")
    remain = int(then) == 0
    if remain and rejoin:
        return ("I voted Remain in 2016 and I'd vote to rejoin the EU tomorrow.", "I voted Remain in 2016, and if there were another referendum I'd vote to rejoin the EU.", "I was a Remain voter in 2016 and I'd vote to rejoin the EU in a heartbeat.")
    if remain and not rejoin:
        return ("I voted Remain in 2016, but I'd vote to stay out of the EU now.", "I voted Remain in 2016, but if there were another referendum I'd vote to stay out of the EU.", "I was a Remain voter in 2016, but these days I'd vote to stay out of the EU.")
    if not remain and rejoin:
        return ("I voted Leave in 2016. Now I'd vote to rejoin the EU.", "I voted Leave in 2016, but if there were another referendum I'd vote to rejoin the EU.", "I was a Leave voter in 2016, but these days I'd vote to rejoin the EU.")
    return ("I voted Leave in 2016 and I'd vote to stay out of the EU again.", "I voted Leave in 2016, and if there were another referendum I'd vote to stay out of the EU.", "I was a Leave voter in 2016 and I'd vote to stay out of the EU again tomorrow.")


def scottish_independence(row, country: int) -> str | None:
    now = value(row, "scotReferendumIntentionW31")
    then = value(row, "p_vote_scot_ref")
    if now is None or int(now) not in (0, 1):
        return None
    yes = int(now) == 1
    if then is not None and int(then) in (0, 1):
        voted_yes = int(then) == 1
        if voted_yes and yes:
            return ("I voted Yes in 2014 and I'd vote Yes to independence again.", "I voted Yes in 2014 and I'd vote Yes again tomorrow.", "I backed independence in 2014 and I still would.")
        if voted_yes and not yes:
            return ("I voted Yes in 2014, but I'd vote No to independence now.", "I voted Yes in 2014, but these days I'd vote No to independence.", "I backed independence in 2014, but I'd vote against it now.")
        if not voted_yes and yes:
            return ("I voted No in 2014. Now I'd vote Yes to Scottish independence.", "I voted No in 2014, but now I'd vote Yes to independence.", "I was against independence in 2014, but I'd vote for it now.")
        return ("I voted No in 2014 and I'd vote No to independence again.", "I voted No in 2014 and I'd vote No again tomorrow.", "I was against independence in 2014 and I still am.")
    return ("I'd vote Yes to Scottish independence.", "If there were another referendum, I'd vote for Scottish independence.", "I'd vote Yes to Scotland leaving the UK.") if yes else ("I'd vote No to Scottish independence.", "If there were another referendum, I'd vote against Scottish independence.", "I'd vote No to Scotland leaving the UK.")


def welsh_independence(row, country: int) -> str | None:
    now = value(row, "welshReferendumIntentionW31")
    if now is None or int(now) not in (0, 1):
        return None
    return ("I'd vote Yes to Welsh independence.", "If there were a referendum, I'd vote for Welsh independence.", "I'd vote Yes to Wales leaving the UK.") if int(now) == 1 else ("I'd vote No to Welsh independence.", "If there were a referendum, I'd vote against Welsh independence.", "I'd vote No to Wales leaving the UK.")


def local_vote(row, country: int) -> str | None:
    """The May 2026 local elections in England."""
    turnout = value(row, "localTurnoutRetroW31")
    if turnout == 1:
        party = value(row, "localElectionVoteW31")
        if party is None or int(party) not in codes.PARTIES and int(party) != 9:
            return None
        name = "another party" if int(party) == 9 else codes.PARTIES[int(party)]
        by_post = " by post" if value(row, "voteMethodbW31") == 1 else ""
        return (f"In May's local elections I voted {name}{by_post}.", f"I voted {name}{by_post} in May's local elections.", f"At the local elections in May, I voted {name}{by_post}.")
    if turnout == 0:
        reason = value(row, "reasonNonVoterW31")
        if reason is not None and int(reason) in codes.NONVOTE_REASON:
            return (f"I didn't vote in May's local elections - {codes.NONVOTE_REASON[int(reason)]}.", f"I didn't vote in the local elections in May - {codes.NONVOTE_REASON[int(reason)]}.", f"I gave May's local elections a miss - {codes.NONVOTE_REASON[int(reason)]}.")
        return ("I didn't vote in May's local elections.", "I didn't turn out for the local elections in May.", "I gave May's local elections a miss.")
    return None


def holyrood_vote(row, country: int) -> str | None:
    """The May 2026 Scottish Parliament election (two ballots)."""
    turnout = value(row, "scotTurnoutW31")  # 1 = voted, 2 = did not, despite the stored labels
    if turnout == 2:
        return ("I didn't vote in May's Holyrood election.", "I didn't turn out for the Scottish Parliament election in May.", "I gave May's Holyrood election a miss.")
    if turnout != 1:
        return None
    const, lst = value(row, "scotElectionVoteConstW31"), value(row, "scotElectionVoteListW31")
    c = codes.SCOTTISH_PARTY.get(int(const)) if const is not None else None
    l = codes.SCOTTISH_PARTY.get(int(lst)) if lst is not None else None
    if c and l and c == l:
        return (f"In May's Holyrood election I voted {c} on both ballots.", f"I voted {c} on both ballots in May's Scottish Parliament election.", f"At the Holyrood election in May, I voted {c} on both the constituency and the list ballot.")
    if c and l:
        return (f"In May's Holyrood election I voted {c} on the constituency ballot and {l} on the list.", f"I voted {c} for my constituency MSP and {l} on the regional list in May's Holyrood election.", f"At the Scottish Parliament election in May, I went {c} on the constituency ballot and {l} on the list.")
    if c or l:
        return (f"In May's Holyrood election I voted {c or l}.", f"I voted {c or l} in May's Scottish Parliament election.", f"At the Holyrood election in May, I voted {c or l}.")
    return None


def senedd_vote(row, country: int) -> str | None:
    """The May 2026 Senedd election."""
    turnout = value(row, "welshTurnoutW31")
    vote = value(row, "senvoteW31")
    if turnout == 0 or vote == 0:
        return ("I didn't vote in May's Senedd election.", "I didn't turn out for the Senedd election in May.", "I gave May's Senedd election a miss.")
    if turnout == 1 and vote is not None and int(vote) in codes.SENEDD_PARTY:
        return (f"In May's Senedd election I voted {codes.SENEDD_PARTY[int(vote)]}.", f"I voted {codes.SENEDD_PARTY[int(vote)]} in May's Senedd election.", f"At the Senedd election in May, I voted {codes.SENEDD_PARTY[int(vote)]}.")
    return None


def trust_mps(answer: float) -> str | None:
    return {1: ("I don't trust MPs one bit.", "I have no trust in MPs at all.", "I don't trust MPs in the slightest."), 2: ("I trust MPs very little.", "I've got very little trust in MPs.", "I hardly trust MPs at all."), 3: ("I don't have much trust in MPs.", "I don't trust MPs all that much.", "My trust in MPs is fairly low."),
            5: ("I trust MPs a fair amount.", "I have a fair amount of trust in MPs.", "On the whole, I've a reasonable amount of trust in MPs."), 6: ("I trust MPs a good deal.", "I've got a good deal of trust in MPs.", "I trust MPs quite a lot."), 7: ("I trust MPs a great deal.", "I have a great deal of trust in MPs.", "I trust MPs very much indeed.")}.get(int(answer))


def _party_noun(code: int) -> str | None:
    """A party as a noun that takes 'against', 'for' and 'preferred': the Conservatives, Labour, the SNP, an independent."""
    return codes.PARTY_NOUN.get(code) or {9: "another party", 13: "an independent"}.get(code)


def vote_against(row, country: int) -> tuple[str, ...] | None:
    """Wave 29: "Imagine that you had a vote against - instead of for - a party at the General Election on July 4th." """
    code = value(row, "disapprovalVoteW29")
    party = _party_noun(int(code)) if code is not None else None
    if not party:
        return None
    return (f"If I'd had a vote against a party in 2024, I'd have used it against {party}.",
            f"Given a vote against a party at the 2024 election, I'd have cast it against {party}.",
            f"In 2024, if I could have voted against one party, it would have been {party}.")


def party_really_preferred(row, country: int) -> tuple[str, ...] | None:
    """Wave 29: tactical voters - "I really preferred another party but it had no chance of winning".

    The party they preferred stays unsaid: the vote band is the reveal at the foot of the card.
    """
    code = value(row, "partyPreferredW29")
    if code is None or int(code) == 0 or not _party_noun(int(code)):
        return None
    return ("I voted tactically in 2024.",
            "My 2024 vote was a tactical one.",
            "In 2024 I voted tactically - the party I really wanted had no chance where I live.")


def wished_vote(row, country: int) -> tuple[str, ...] | None:
    """Wave 29: those with regrets about their 2024 vote. How they wish they had voted stays unsaid."""
    code = value(row, "votingWishW29")
    if code is None:
        return None
    if int(code) == 0:
        return ("I wish I hadn't voted at all in 2024.",
                "Looking back at 2024, I wish I'd stayed at home rather than voting the way I did.",
                "I've regrets about 2024 - I'd rather not have voted at all.")
    if not _party_noun(int(code)):
        return None
    return ("I wish I'd voted differently to how I voted in 2024.",
            "I've regrets about my 2024 vote - I wish I'd voted differently.",
            "If I could do 2024 again, I'd vote differently.")

def _plural(what: str) -> bool:
    return what.endswith("s") and not what.endswith(("'s", "ss", "economy"))


def brexit_effect5(what: str) -> Phraser:
    """The wave-27 'has Brexit made X better or worse' items: much worse ... much better."""
    cap, pl = f"{what[0].upper()}{what[1:]}", _plural(what)
    be = "are" if pl else "is"
    return by_code({
        1: (f"Brexit has made {what} much worse.", f"{cap} {be} much worse because of Brexit.", f"Brexit has done {what} a great deal of harm."),
        2: (f"Brexit has made {what} worse.", f"{cap} {be} worse because of Brexit.", f"Brexit has done {what} harm."),
        3: (f"Brexit hasn't made much difference to {what}.", f"{cap} {be} about the same as before Brexit.", f"Brexit has left {what} about where {'they were' if pl else 'it was'}."),
        4: (f"Brexit has made {what} better.", f"{cap} {be} better because of Brexit.", f"Brexit has done {what} good."),
        5: (f"Brexit has made {what} much better.", f"{cap} {be} much better because of Brexit.", f"Brexit has done {what} a great deal of good."),
    })


def remain_effect5(what: str) -> Phraser:
    """The 2021-23 'if Britain had stayed in the EU, would X be better or worse' items."""
    pl = _plural(what)
    be = "would be"
    return by_code({
        1: (f"If Britain had stayed in the EU, {what} {be} much worse.", f"Had we stayed in the EU, {what} {be} a lot worse.", f"Staying in the EU would have left {what} much worse off."),
        2: (f"If Britain had stayed in the EU, {what} {be} worse.", f"Had we stayed in the EU, {what} {be} worse.", f"Staying in the EU would have left {what} worse off."),
        3: (f"If Britain had stayed in the EU, {what} {be} about the same.", f"Staying in the EU would have made little difference to {what}.", f"Had we stayed in the EU, {what} {be} much as {'they are' if pl else 'it is'} now."),
        4: (f"If Britain had stayed in the EU, {what} {be} better.", f"Had we stayed in the EU, {what} {be} better.", f"Staying in the EU would have left {what} better off."),
        5: (f"If Britain had stayed in the EU, {what} {be} much better.", f"Had we stayed in the EU, {what} {be} a lot better.", f"Staying in the EU would have left {what} much better off."),
    })


def globalisation5(what: str) -> Phraser:
    """The 2020-21 globalisation grid: is X mainly bad ... mainly good for Britain? The middle sits on the fence."""
    cap, pl = f"{what[0].upper()}{what[1:]}", _plural(what)
    has, does, be = ("have", "do", "are") if pl else ("has", "does", "is")
    return by_code({
        1: (f"{cap} {has} been mainly bad for Britain.", f"On the whole, {what} {has} been a bad thing for Britain.", f"{cap} {does} Britain more harm than good, by a long way."),
        2: (f"{cap} {has} been slightly more bad than good for Britain.", f"On balance, {what} {has} done Britain a bit more harm than good.", f"{cap} {be} a little more of a bad thing than a good thing for Britain."),
        3: (f"{cap} {has} been good and bad for Britain in equal measure.", f"{cap} {has} done Britain good and harm in equal measure."),
        4: (f"{cap} {has} been slightly more good than bad for Britain.", f"On balance, {what} {has} done Britain a bit more good than harm.", f"{cap} {be} a little more of a good thing than a bad thing for Britain."),
        5: (f"{cap} {has} been mainly good for Britain.", f"On the whole, {what} {has} been a good thing for Britain.", f"{cap} {does} Britain far more good than harm."),
    })


def vote_difference(answer: float) -> tuple[str, ...] | None:
    """0-10: how likely it is that their vote makes a difference in their constituency."""
    n = int(answer)
    if n <= 2:
        return ("My vote makes no difference at all where I live.", "Where I live, my vote is very unlikely to change anything.", "There's next to no chance my vote makes a difference in my constituency.")
    if n <= 4:
        return ("My vote is unlikely to make much difference where I live.", "Where I live, my vote probably doesn't change anything.", "I doubt my vote makes much difference in my constituency.")
    if n >= 8:
        return ("My vote really can make a difference where I live.", "Where I live, my vote is very likely to count.", "There's every chance my vote makes a difference in my constituency.")
    if n >= 6:
        return ("My vote probably makes a difference where I live.", "Where I live, my vote is fairly likely to count.", "I think my vote makes some difference in my constituency.")
    return None


# ---------------------------------------------------------------------------
# The library. Column lists start with wave 31 and fall back to earlier waves
# (wave 20 onwards) so the freshest answer each person gave is used.


IMPACT_BATTERY = {  # the "how much impact on Britain's economy" grid, per wave, for spotting straight-liners
    "W31": ("brexitEconImpactW31", "globalEconomyEconImpactW31", "conflictEconImpactW31", "ukGovtEconImpactW31", "ukLastGovtEconImpactW31"),
    "W30": ("brexitEconImpactW30", "globalEconomyEconImpactW30", "ukraineEconImpactW30", "ukGovtEconImpactW30", "ukLastGovtEconImpactW30"),
}


MISREAD_CHECK = {  # a positive score for wars means the slider was read as sheer size of impact, not negative-to-positive
    "W31": ("conflictEconImpactW31", "conflictEconImpactScotW31", "conflictEconImpactWalesW31"),
    "W30": ("ukraineEconImpactW30", "ukraineEconImpactScotW30", "ukraineEconImpactWalesW30"),
}


def impact_item(cols: tuple[str, ...], lot_damage: str, some_damage: str, good: str, very_good: str,
                mixed: str | tuple[str, ...] | None = None) -> Callable:
    """BES economic-impact scale, 0 (large negative impact) to 100 (large positive).

    The middle (41-59) reads as the `mixed` wordings, which is_neutral() picks up
    so they are drawn at NEUTRAL_WEIGHT. Two kinds of answer are dropped outright:
    a straight-liner who gave the identical answer to every item in the grid, and
    anyone who scored global conflicts (in 2025, the invasion of Ukraine) as a
    positive for the economy. Nobody believes wars have done Britain's economy
    good: a 60+ there means the slider was read as "how much impact" rather than
    negative-to-positive, so none of that person's impact answers can be trusted
    (76% of rejoin supporters who put Brexit at 60+ also put conflicts at 60+,
    against 14% of stay-out supporters).
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
        if any((value(row, c) or 0) >= 60 for c in MISREAD_CHECK.get(wave, ())):
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
        return mixed
    return custom


def scot_ref_bond(row, country: int) -> str | None:
    """Identity with the Yes or No side of 2014, from the referendum-identity battery (Scotland, 2024)."""
    side = {1: "the Yes side", 2: "the No side"}.get(int(value(row, "scotRefIDW27") or 0))
    if side is None:
        return None
    if value(row, "scotRefID3W27") == 4:
        return (f"When people criticise {side}, it feels like a personal insult.", f"If someone has a go at {side}, I take it personally.", f"Criticism of {side} feels like an insult aimed at me.")
    if value(row, "scotRefID1W27") == 4:
        return (f"I still say 'we' when I talk about {side}.", f"When I talk about {side}, it's still 'we' rather than 'they'.", f"Even now, I say 'we' when I'm talking about {side}.")
    if value(row, "scotRefID6W27") == 4:
        return (f"When I meet someone else from {side}, I feel a connection.", f"I feel connected to anyone I meet who backs {side}.", f"Meeting another supporter of {side} gives me a sense of connection.")
    return None


def eu_ref_bond(row, country: int) -> str | None:
    """Identity with Remain or Leave, from the EU-referendum-identity battery (2023)."""
    side = {1: "Remainers", 2: "Leavers"}.get(int(value(row, "euIDW24") or 0))
    if side is None:
        return None
    if value(row, "euID3W24") == 4:
        return (f"When people criticise {side}, it feels like a personal insult.", f"If someone has a go at {side}, I take it personally.", f"Criticism of {side} feels like an insult aimed at me.")
    if value(row, "euID1W24") == 4:
        return (f"I still say 'we' when I talk about {side}.", f"When I talk about {side}, it's still 'we' rather than 'they'.", f"Even now, I say 'we' when I'm talking about {side}.")
    if value(row, "euID6W24") == 4:
        return (f"When I meet another of the {side}, I feel a connection.", f"I feel a bond with any of the {side} I meet.", f"When I come across one of the other {side}, I feel connected to them.")
    return None


def eu_regret(row, country: int) -> str | None:
    regret = value(row, "regretsIHaveAFewEUW26")
    if regret == 1:
        return ("I regret how I voted in the EU referendum.", "I wish I'd voted differently in the EU referendum.", "Looking back, I do have regrets about the way I voted in the Brexit referendum.")
    if regret == 0:
        return ("I've no regrets about how I voted in the EU referendum.", "I don't regret the way I voted in the EU referendum one bit.", "Looking back, I've got no regrets about my vote in the Brexit referendum.")
    return None


def social_circle_vote(row, country: int) -> str | None:
    party = value(row, "normPartyVoteW28")
    if party is None:
        return None
    if int(party) == 0:
        return ("Most people I know weren't going to vote in 2024.", "Most of the people I know had no plans to vote in 2024.", "In 2024, most people I know weren't planning to vote at all.")
    if int(party) in codes.PARTIES:
        return (f"Most people I know were voting {codes.PARTIES[int(party)]} in 2024.", f"Most of the people I know were backing {codes.PARTIES[int(party)]} in 2024.", f"Most people in my circle were going to vote {codes.PARTIES[int(party)]} in 2024.")
    return None





def warmth_item(group: str) -> Phraser:
    """The 0-100 feeling thermometer: cold below 20, cool to 40, warm from 60, very warm from 80."""
    def phrase(answer: float) -> str | None:
        n = int(answer)
        if n < 20:
            return (f"I feel cold towards {group}.", f"My feelings towards {group} are pretty cold.", f"I've no warmth towards {group}.")
        if n <= 40:
            return (f"I don't feel warmly towards {group}.", f"I don't have warm feelings towards {group}.", f"I'm not especially warm towards {group}.")
        if n >= 80:
            return (f"I feel very warmly towards {group}.", f"I have very warm feelings towards {group}.", f"I'm very warm towards {group}.")
        if n >= 60:
            return (f"I feel warmly towards {group}.", f"I have warm feelings towards {group}.", f"I'm warm towards {group}.")
        return None
    return phrase


def gone_too_far_item(what: str) -> Phraser:
    cap = f"{what[0].upper()}{what[1:]}"
    return by_code({
        1: (f"{cap} haven't gone nearly far enough.", f"There's a long way still to go on {what}.", f"{cap} have a very long way to go yet."),
        2: (f"{cap} haven't gone far enough.", f"There's further to go on {what}.", f"{cap} need to go further."),
        3: (f"{cap} are about right.", f"Things are about right on {what}.", f"{cap} have gone about right, as far as I'm concerned."),
        4: (f"{cap} have gone too far.", f"Things have gone too far on {what}.", f"{cap} have been pushed too far."),
        5: (f"{cap} have gone much too far.", f"Things have gone much too far on {what}.", f"{cap} have been pushed much too far."),
    })


ITEMS: list[Item] = [
    # Economic values (lr1-5)
    Item("lr1", "redistribution", ("lr1W31",),
         agree5(("The government should do far more to redistribute income from the better off to those with less.", "The government should take a lot more from the well-off and give it to those with less."),
                ("The government should take more from the well-off and give it to those with less.", "I'd like to see more redistribution from the well-off to people who have less."),
                ("I'm not keen on the government taking from the well-off to give to others.", "I don't think it's the government's job to redistribute income."),
                ("The government has no business redistributing income from the well-off.", "Taking from the better off to give to the less well off is wrong."))),
    Item("lr2", "big-business", ("lr2W31",),
         agree5(("Big business takes advantage of ordinary people at every turn.", "Big business walks all over ordinary people."),
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
         agree5(("Far too many people are easily offended these days over the words others use.", "Far too many people these days get offended far too easily over the words others use.", "These days, far too many people get offended at the drop of a hat over the words others use."),
                ("Too many people are easily offended these days over the language others use.", "These days, too many people take offence too easily at the words others use.", "I think too many people get offended too easily over language these days."),
                ("I don't think people are too easily offended by language - words matter.", "I don't think people are too quick to take offence at the language others use.", "I wouldn't say people are too easily offended by the words others use."),
                ("People aren't too easily offended over language - far from it.", "I really don't think people are too easily offended by the language others use.", "The idea that people get offended too easily over language is nonsense."))),
    Item("cwStatues", "statues", ("cwStatuesW31", "cwStatuesW26W27", "cwStatuesW25"),
         agree5(("Statues of historical figures should stay up, even if they profited from slavery.", "Statues of historical figures must not come down, even if they profited from the slave trade.", "Statues of historical figures should absolutely stay up, even those of people who profited from slavery."),
                ("I'd keep statues of historical figures up, even if they profited from slavery.", "I wouldn't take down statues of historical figures just because they profited from slavery.", "Statues of historical figures should be left standing, even if they made money from the slave trade."),
                ("Statues of people who profited from slavery shouldn't necessarily stay up.", "I don't think statues of people who profited from slavery automatically deserve to stay up.", "I'm not convinced statues of people who profited from the slave trade should be left standing."),
                ("Statues of people who profited from slavery should come down.", "Statues of people who made their money from the slave trade should be taken down.", "If someone profited from slavery, their statue should come down."))),
    Item("cwTraining", "diversity-training", ("cwTrainingW31", "cwTrainingW26W27", "cwTrainingW25"),
         agree5(("Workplaces should scrap mandatory diversity training altogether.", "Mandatory diversity training at work should be done away with completely.", "Workplaces should get rid of compulsory diversity training once and for all."),
                ("Workplaces should end mandatory diversity training.", "I think it's time workplaces stopped making diversity training compulsory.", "Diversity training at work shouldn't be mandatory any more."),
                ("I'd keep mandatory diversity training at work.", "I don't think workplaces should end mandatory diversity training.", "Mandatory diversity training at work should carry on."),
                ("Mandatory diversity training at work should definitely stay.", "Workplaces should absolutely keep mandatory diversity training.", "There's no way workplaces should end mandatory diversity training."))),
    Item("cwAuthors", "curriculum", ("cwAuthorsW31", "cwAuthorsW26W27", "cwAuthorsW25"),
         agree5(("School and university reading lists need far more female and non-white authors.", "Reading lists at schools and universities badly need more female and non-white authors.", "Schools and universities should be putting far more female and non-white authors on their reading lists."),
                ("Reading lists should include more female and non-white authors.", "I'd like school and university reading lists to include more female and non-white authors.", "There should be more female and non-white authors on the curriculum."),
                ("I don't see the need to change reading lists to add more female and non-white authors.", "I don't think reading lists need more female and non-white authors added to them.", "Reading lists are fine as they are without adding more female and non-white authors."),
                ("I'm firmly against changing reading lists to add more female and non-white authors.", "I'm dead against rewriting school and university reading lists to add more female and non-white authors.", "There's no way reading lists should be changed to include more female and non-white authors."))),
    Item("cwTrans", "trans-sport", ("cwTransW31", "cwTransW26W27", "cwTransW25"),
         agree5(("Transgender women have every right to compete in women's sport.", "Transgender women absolutely should be allowed to compete in women's sport.", "Of course transgender women should be able to compete in women's sport."),
                ("Transgender women should be allowed to compete in women's sport.", "I think transgender women should be able to take part in women's sport.", "Women's sport should be open to transgender women."),
                ("Transgender women shouldn't compete in women's sport.", "I don't think transgender women should be allowed to compete in women's sport.", "Women's sport shouldn't be open to transgender women."),
                ("Transgender women should not be competing in women's sport at all.", "There's no place for transgender women in women's sport, full stop.", "Transgender women have no business competing in women's sport."))),
    Item("cwParents", "same-sex-parents", ("cwParentsW31", "cwParentsW30", "cwParentsW26W27", "cwParentsW25"),
         agree5(("Children's TV should show far more families with same-sex parents.", "Children's TV should be showing a lot more families with same-sex parents.", "I'd love to see far more families with same-sex parents on children's TV."),
                ("Children's TV should show more families with same-sex parents.", "I'd like to see more families with same-sex parents on children's TV.", "Children's programmes should include more families with same-sex parents."),
                ("I don't think children's TV needs to show more families with same-sex parents.", "I don't see why children's TV should show more families with same-sex parents.", "Children's TV doesn't need any more families with same-sex parents than it has."),
                ("Children's TV certainly doesn't need more families with same-sex parents.", "There's absolutely no need for more families with same-sex parents on children's TV.", "Children's TV definitely shouldn't be showing more families with same-sex parents."))),
    # Spending and the state
    Item("cutsNational", "spending-cuts", ("cutsTooFarNationalW31", "cutsTooFarNationalW30", "cutsTooFarNationalW26"),
         too_far5(("Cuts to public spending have gone much too far.", "Public spending has been cut far too much.", "The cuts to public spending have gone way too far."), ("Cuts to public spending have gone too far.", "Public spending has been cut too much.", "The cuts to public spending have gone further than they should have."),
                  ("Public spending cuts have been about right.", "The level of public spending cuts has been about right.", "I'd say cuts to public spending have been about right."), ("Cuts to public spending haven't gone far enough.", "Public spending should have been cut more than it has been.", "I don't think the cuts to public spending have gone far enough."),
                  ("Cuts to public spending haven't gone nearly far enough.", "Public spending cuts haven't gone anywhere near far enough.", "Public spending needs cutting a great deal more than it has been.")), fallback=False),
    Item("cutsNHS", "nhs-cuts", ("cutsTooFarNHSW31", "cutsTooFarNHSW30", "cutsTooFarNHSW26"),
         too_far5(("Cuts to NHS spending have gone much too far.", "NHS spending has been cut far too much.", "The cuts to the NHS have gone way too far."), ("Cuts to NHS spending have gone too far.", "NHS spending has been cut too much.", "The cuts to the NHS have gone further than they should have."),
                  ("NHS spending cuts have been about right.", "The cuts to NHS spending have been about right.", "I'd say NHS spending cuts have been about right."), ("NHS spending cuts haven't gone far enough.", "I don't think the cuts to NHS spending have gone far enough.", "NHS spending should have been cut more than it has been."),
                  ("NHS spending cuts haven't gone nearly far enough.", "Cuts to NHS spending haven't gone anywhere near far enough.", "NHS spending needs cutting a great deal more than it has been.")), fallback=False),
    Item("cutsLocal", "local-cuts", ("cutsTooFarLocalW31", "cutsTooFarLocalW30", "cutsTooFarLocalW26"),
         too_far5(("Cuts to local services where I live have gone much too far.", "Local services in my area have been cut far too much.", "The cuts to local services round here have gone way too far."),
                  ("Cuts to local services where I live have gone too far.", "Local services in my area have been cut too much.", "The cuts to local services round here have gone further than they should have."),
                  ("Cuts to local services round here have been about right.", "The cuts to local services in my area have been about right.", "I'd say cuts to local services where I live have been about right."),
                  ("Cuts to local services where I live haven't gone far enough.", "I don't think the cuts to local services in my area have gone far enough.", "Local services round here should have been cut more than they have been."),
                  ("Cuts to local services where I live haven't gone nearly far enough.", "Local services in my area need cutting a great deal more than they have been.", "Cuts to local services round here haven't gone anywhere near far enough.")), fallback=False),
    Item("privatisation", "privatisation", ("privatTooFarW31", "privatTooFarW26"),
         too_far5(("Private companies have far too big a role in running public services.", "Having private companies run public services has gone much too far.", "Far too many of our public services are being run by private companies."),
                  ("Private companies have too big a role in running public services.", "Having private companies run public services has gone too far.", "Too many of our public services are being run by private companies."),
                  ("The role of private companies in public services is about right.", "The involvement of private companies in running public services is about right.", "I'd say the amount of public services run by private companies is about right."),
                  ("Private firms should be running more of our public services.", "Having private companies run public services hasn't gone far enough.", "I'd like to see more of our public services run by private companies."),
                  ("Private firms should be running far more of our public services.", "Having private companies run public services hasn't gone anywhere near far enough.", "A great deal more of our public services should be run by private companies."))),
    Item("enviroProtection", "green-rules", ("enviroProtectionW31", "enviroProtectionW30", "enviroProtectionW26"),
         too_far5(("Measures to protect the environment have gone much too far.", "Environmental protection has gone much too far.", "We've gone way too far with measures to protect the environment."),
                  ("Measures to protect the environment have gone too far.", "Environmental protection has gone too far.", "We've gone too far with measures to protect the environment."),
                  ("Environmental protection is about right as it is.", "Measures to protect the environment have been about right.", "I'd say the amount we do to protect the environment is about right."),
                  ("Measures to protect the environment haven't gone far enough.", "I don't think environmental protection measures have gone far enough.", "We should be doing more to protect the environment than we are."),
                  ("Measures to protect the environment haven't gone nearly far enough.", "Environmental protection hasn't gone anywhere near far enough.", "We need to be doing a great deal more to protect the environment than we are."))),
    Item("taxSpend", "tax-and-spend", ("taxSpendSelfW31", "taxSpendSelfW30", "taxSpendSelfW28", "taxSpendSelfW27"),
         scale11(("Cut taxes a lot, even if it means spending much less on health and social services.", "I'd cut taxes a lot, even if that means spending much less on health and social services.", "Taxes should come down a lot, and spending on health and social services should come down a lot too."),
                 ("I'd cut taxes a bit and trim spending on health and social services.", "I'd like taxes cut a little, even if it means slightly less spending on health and social services.", "On balance, I'd cut taxes a bit and spend a bit less on health and social services."),
                 ("I'd pay a bit more tax for better health and social services.", "I'd be willing to pay a little more tax to get better health and social services.", "On balance, I'd raise taxes a bit and spend a bit more on health and social services."),
                 ("Raise taxes a lot and spend much more on health and social services.", "I'd raise taxes a lot and spend much more on health and social services.", "Taxes should go up a lot so we can spend much more on health and social services."),
                 ("Tax and spending on health and social services should stay about where they are.", "I'd leave taxes and spending on health and social services roughly as they are.", "I wouldn't change taxes or spending on health and social services much either way."))),
    Item("redist", "redistribution", ("redistSelfW31", "redistSelfW30", "redistSelfW29"),
         scale11(("Government should be doing much more to make incomes equal.", "The government should make a much bigger effort to make people's incomes more equal.", "I want the government to do much more to even out people's incomes."),
                 ("Government should do a bit more to even out incomes.", "The government should make a bit more effort to make incomes more equal.", "On balance, I'd like the government to do a little more to make incomes equal."),
                 ("Government should worry less about making incomes equal.", "The government should be a bit less concerned with how equal people's incomes are.", "On balance, I think the government should care less about evening out incomes."),
                 ("Making incomes more equal shouldn't be the government's concern at all.", "The government should be much less concerned about how equal people's incomes are.", "It's not the government's job to even out people's incomes.")), weight=0.7),
    # BES: "Do you think that the amount of money families on welfare receive is too high or too low?"
    Item("welfare", "benefits", ("welfarePreferenceW31", "welfarePreferenceW27"),
         by_code({1: ("Families on welfare get far too much money.", "Welfare payments to families are much too high.",
                      "Families on benefits get much more than they should."),
                  2: ("Families on welfare get too much money.", "Welfare payments to families are too high.",
                      "Families on benefits get more than they should."),
                  3: ("The money families on welfare get is about right.", "Welfare payments to families are about right."),
                  4: ("Families on welfare get too little money.", "Welfare payments to families are too low.",
                      "Families on benefits get less than they should."),
                  5: ("Families on welfare get far too little money.", "Welfare payments to families are much too low.",
                      "Families on benefits get much less than they should.")})),
    Item("enviroGrowth", "growth-v-environment", ("enviroGrowthW31", "enviroGrowthW30", "enviroGrowthW28"),
         scale11(("Economic growth has to come first, ahead of the environment.", "Economic growth should take priority, even if it gets in the way of protecting the environment.", "Growth comes first for me, even if the environment suffers for it."),
                 ("Growth should come first, but the environment matters too.", "On balance, I'd put economic growth ahead of the environment, though not by much.", "I lean towards growth over the environment, but both count."),
                 ("Protecting the environment should come first, though growth matters.", "On balance, I'd put protecting the environment ahead of growth, though not by much.", "I lean towards the environment over growth, but both count."),
                 ("Protecting the environment must come before economic growth.", "Protecting the environment should take priority, even if it means less economic growth.", "The environment comes first for me, even if growth suffers for it."))),
    # Immigration and Europe
    Item("immigSelf", "immigration", ("immigSelfW31", "immigSelfW30", "immigSelfW29"),
         scale11(("Britain should let in far fewer immigrants.", "The UK should allow many fewer immigrants to come here to live.", "We should be letting far fewer immigrants into this country."), ("I'd like to see fewer immigrants coming in.", "On balance, I'd let somewhat fewer immigrants into the UK.", "I'd rather Britain allowed slightly fewer immigrants in than it does now."),
                 ("I'd be happy for a few more immigrants to come.", "On balance, I'd let somewhat more immigrants into the UK.", "I'd rather Britain allowed slightly more immigrants in than it does now."), ("Britain should let in many more immigrants.", "The UK should allow many more immigrants to come here to live.", "We should be letting far more immigrants into this country."),
                 ("Immigration levels are about right as they are.", "The number of immigrants we let in is about right.", "I'd say the level of immigration into Britain is about right."))),
    Item("immigEcon", "immigration", ("immigEconW31", "immigEconW30", "immigEconW27"),
         by_code({1: ("Immigration is clearly bad for the economy.", "Immigration is bad for Britain's economy, no question.", "There's no doubt in my mind that immigration is bad for the economy."), 2: ("Immigration is bad for the economy.", "I think immigration does the economy harm.", "Immigration is bad news for Britain's economy."),
                  3: ("On balance, immigration is slightly bad for the economy.", "If anything, immigration does the economy a bit of harm.", "Immigration is probably a little bit bad for the economy, on balance."),
                  5: ("On balance, immigration is slightly good for the economy.", "If anything, immigration does the economy a bit of good.", "Immigration is probably a little bit good for the economy, on balance."),
                  6: ("Immigration is good for the economy.", "I think immigration does the economy good.", "Immigration is good news for Britain's economy."), 7: ("Immigration is clearly good for the economy.", "Immigration is good for Britain's economy, no question.", "There's no doubt in my mind that immigration is good for the economy.")}),
         weight=0.6),
    Item("euIntegration", "europe", ("EUIntegrationSelfW31", "EUIntegrationSelfW29"),
         scale11(("Britain should unite fully with the European Union.", "I'd like Britain to be fully part of the European Union.", "Britain should go all the way and unite fully with the EU."), ("I'd like Britain much closer to the EU.", "I'd like to see Britain a lot closer to the EU than it is now.", "I lean towards Britain getting much closer to the European Union."),
                 ("I'd keep Britain at arm's length from the EU.", "I lean towards Britain keeping its distance from the European Union.", "I'd rather Britain kept a bit of distance from the EU."), ("Britain must protect its independence from the EU.", "Britain should guard its independence from the European Union.", "I want Britain to stay fully independent of the EU.")),
         weight=0.6),
    Item("euRef", "europe", (), custom=eu_statement, weight=1.3),
    # Democracy and politicians
    Item("strongLeader", "strong-leader", ("strongLeaderW31",),
         agree5(("Britain would be better run by a strong leader who ignores parliament and elections.", "The best way to run this country would be a strong leader who doesn't bother with parliament or elections.", "Britain definitely needs a strong leader who doesn't have to bother with parliament or elections."),
                ("A strong leader who didn't have to bother with parliament would run things better.", "I think the country would do better with a strong leader who didn't have to bother with parliament.", "We'd be better off with a strong leader who didn't have to answer to parliament or elections."),
                ("I don't want a strong leader who ignores parliament and elections.", "I don't think a strong leader who ignored parliament and elections would be a good way to run the country.", "A strong leader who didn't bother with parliament or elections isn't what I want."),
                ("I'd never want a leader who ignored parliament and elections.", "The last thing Britain needs is a strong leader who ignores parliament and elections.", "I'm dead against the idea of a strong leader who doesn't have to bother with parliament or elections."))),
    Item("trustMPs", "trust", ("trustMPsW31",), trust_mps),
    Item("efficacyPolCare", "politicians", ("efficacyPolCareW31", "efficacyPolCareW30", "efficacyPolCareW27"),
         agree5(("Politicians couldn't care less what people like me think.", "Politicians aren't the least bit interested in what people like me think.", "Politicians have absolutely no interest in what people like me think."),
                ("Politicians don't care what people like me think.", "Politicians aren't interested in what people like me think.", "I don't think politicians care what people like me think."),
                ("I think politicians do care what people like me think.", "I'd say politicians do care what people like me think.", "On the whole, politicians care what people like me think."),
                ("Politicians really do care what people like me think.", "I'm certain politicians care what people like me think.", "Politicians absolutely do care what people like me think."))),
    Item("efficacyNoMatter", "politicians", ("efficacyNoMatterW31", "efficacyNoMatterW30", "efficacyNoMatterW27"),
         agree5(("It makes no difference which party is in power.", "It doesn't matter one bit which party is in power.", "Which party is in power makes no difference whatsoever."),
                ("It doesn't much matter which party is in power.", "It doesn't make much difference which party is in power.", "Which party is in power doesn't really matter."),
                ("It does matter which party is in power.", "I think it makes a difference which party is in power.", "Which party is in power does matter."),
                ("It matters enormously which party is in power.", "It makes a huge difference which party is in power.", "Which party is in power matters a great deal.")), weight=0.7),
    Item("efficacyUnderstand", "political-interest", ("efficacyUnderstandW31", "efficacyUnderstandW30"),
         agree5(("I've got a good grasp of the big political issues facing the country.", "I understand the big political issues facing the country very well.", "I have a really good understanding of the big political issues facing the country."),
                ("I understand the big political issues facing the country pretty well.", "I've got a pretty good understanding of the big political issues facing the country.", "I understand the important political issues facing the country reasonably well."),
                ("I don't really understand the big political issues facing the country.", "I wouldn't say I understand the big political issues facing the country.", "I don't have much of a grasp of the big political issues facing the country."),
                ("I struggle to understand the big political issues facing the country.", "I really don't understand the big political issues facing the country.", "The big political issues facing the country go over my head.")), weight=0.5),
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
         worse_better5(("The NHS is getting a lot worse.", "The NHS is getting much worse.", "The NHS is going downhill fast."), ("The NHS is getting a bit worse.", "The NHS is getting a little worse.", "The NHS is slipping a bit, I'd say."),
                       ("The NHS is getting a bit better.", "The NHS is getting a little better.", "The NHS is improving a bit, I'd say."), ("The NHS is getting a lot better.", "The NHS is getting much better.", "The NHS is improving a great deal.")), fallback=False),
    Item("changeEconomy", "economy-direction", ("changeEconomyW31", "changeEconomyW30"),
         worse_better5(("The economy is getting a lot worse.", "The economy is getting much worse.", "The economy is going downhill fast."), ("The economy is getting a bit worse.", "The economy is getting a little worse.", "The economy is slipping a bit, I'd say."),
                       ("The economy is getting a bit better.", "The economy is getting a little better.", "The economy is picking up a bit, I'd say."), ("The economy is getting a lot better.", "The economy is getting much better.", "The economy is improving a great deal.")), weight=0.7, fallback=False),
    Item("changeSchools", "schools", ("changeSchoolsW31", "changeSchoolsW30"),
         worse_better5(("Schools are getting a lot worse.", "Schools are getting much worse.", "Our schools are going downhill fast."), ("Schools are getting a bit worse.", "Schools are getting a little worse.", "Our schools are slipping a bit, I'd say."),
                       ("Schools are getting a bit better.", "Schools are getting a little better.", "Our schools are improving a bit, I'd say."), ("Schools are getting a lot better.", "Schools are getting much better.", "Our schools are improving a great deal.")), weight=0.6, fallback=False),
    Item("changeCostLive", "cost-of-living", ("changeCostLiveW31", "changeCostLiveW30"),
         by_code({5: ("The cost of living is still going up a lot.", "The cost of living is getting a lot higher.", "Living costs are still rising sharply."), 4: ("The cost of living is still creeping up.", "The cost of living is getting a little higher.", "Living costs are still rising a bit."),
                  2: ("The cost of living is starting to come down a little.", "The cost of living is getting a little lower.", "Living costs are easing off a bit."), 1: ("The cost of living is coming down a lot.", "The cost of living is getting a lot lower.", "Living costs are falling a lot.")}), fallback=False),
    Item("changeImmig", "immigration-direction", ("changeImmigW31", "changeImmigW30"),
         by_code({5: ("Immigration is going up a lot.", "Immigration is getting a lot higher.", "The level of immigration is rising a lot."), 4: ("Immigration is going up a bit.", "Immigration is getting a little higher.", "The level of immigration is rising a bit."),
                  2: ("Immigration is coming down a bit.", "Immigration is getting a little lower.", "The level of immigration is falling a bit."), 1: ("Immigration is coming down a lot.", "Immigration is getting a lot lower.", "The level of immigration is falling a lot.")}), weight=0.5, fallback=False),
    Item("changeCrime", "crime-direction", ("changeCrimeW31", "changeCrimeW30"),
         by_code({5: ("Crime is going up a lot.", "Crime is getting a lot higher.", "The level of crime is rising a lot."), 4: ("Crime is going up a bit.", "Crime is getting a little higher.", "The level of crime is rising a bit."),
                  2: ("Crime is falling a bit.", "Crime is getting a little lower.", "The level of crime is coming down a bit."), 1: ("Crime is falling a lot.", "Crime is getting a lot lower.", "The level of crime is coming down a lot.")}), weight=0.6, fallback=False),
    Item("econGenRetro", "economy-direction", ("econGenRetroW31", "econGenRetroW30"),
         worse_better5(("The economy has got a lot worse over the past year.", "The economy has got much worse in the last twelve months.", "Over the last year, the economy has gone downhill a lot."), ("The economy has got a bit worse over the past year.", "The economy has got a little worse in the last twelve months.", "Over the last year, the economy has slipped a bit."),
                       ("The economy has got a bit better over the past year.", "The economy has got a little better in the last twelve months.", "Over the last year, the economy has picked up a bit."), ("The economy has got a lot better over the past year.", "The economy has got much better in the last twelve months.", "Over the last year, the economy has picked up a great deal.")),
         weight=0.5, fallback=False),
    Item("econGenProsp", "economy-outlook", ("econGenProspW31",),
         worse_better5(("The economy is going to get a lot worse over the next year.", "I expect the economy to get much worse over the next twelve months.", "Over the next year, I think the economy will go downhill a lot."), ("I expect the economy to get a bit worse next year.", "The economy is going to get a little worse over the next year.", "Over the next twelve months, I think the economy will slip a bit."),
                       ("I expect the economy to pick up a bit next year.", "The economy is going to get a little better over the next year.", "Over the next twelve months, I think the economy will improve a bit."), ("The economy is going to get a lot better over the next year.", "I expect the economy to get much better over the next twelve months.", "Over the next year, I think the economy will pick up a great deal.")),
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
         by_code({1: ("My sympathies lie firmly with Israel over the Palestinians.", "I sympathise much more with the Israeli side than the Palestinian side.", "On Israel and Palestine, I'm very much on Israel's side."),
                  2: ("I sympathise a little more with the Israeli side.", "My sympathies lean slightly towards Israel.", "On Israel and Palestine, I'm a little more on the Israeli side."),
                  3: ("On Israel and Palestine, I don't take either side.", "I don't favour either side over the other on Israel and Palestine.", "On Israel and Palestine, I sympathise with neither side more than the other."),
                  4: ("I sympathise a little more with the Palestinian side.", "My sympathies lean slightly towards the Palestinians.", "On Israel and Palestine, I'm a little more on the Palestinian side."),
                  5: ("My sympathies lie firmly with the Palestinians.", "I sympathise much more with the Palestinian side than the Israeli side.", "On Israel and Palestine, I'm very much on the Palestinians' side.")})),
    Item("happyTrump", "trump", ("happyTrumpW31", "happyTrumpW30"),
         scale11(("Trump back in the White House is a disaster.", "I'm gutted that Trump is back in the White House.", "Trump being back in the White House is terrible news."), ("I'm disappointed Trump is back in the White House.", "I'm not happy that Trump is back in the White House.", "It's a shame Trump is back in the White House."),
                 ("I'm fairly pleased Trump is back in the White House.", "I'm quite happy that Trump is back in the White House.", "On the whole, I'm glad Trump is back in the White House."), ("I'm delighted Trump is back in the White House.", "I'm thrilled that Trump is back in the White House.", "Trump being back in the White House is brilliant news.")), fallback=False),
    Item("automationSelf", "automation", ("automationEffectsSelfW31",),
         by_code({1: ("Robots and AI taking over work would be very bad for me.", "Robots and computers doing more of the work would be very bad for me personally.", "Automation taking over jobs would be terrible for me."), 2: ("Automation taking over jobs would be bad for me.", "Robots and AI doing more of the work would be bad for me personally.", "Robots and computers taking over jobs would be bad news for me."),
                  4: ("Automation taking over jobs would be good for me.", "Robots and AI doing more of the work would be good for me personally.", "Robots and computers taking over jobs would be good news for me."), 5: ("Robots and AI doing more of the work would be very good for me.", "Automation taking over jobs would be very good for me personally.", "Robots and computers taking over more of the work would be great for me.")}),
         weight=0.6),
    Item("automationCountry", "automation", ("automationEffectsCountryW31",),
         by_code({1: ("Robots and AI taking over work would be very bad for the country.", "Robots and computers doing more of the work would be very bad for the country as a whole.", "Automation taking over jobs would be terrible for the country."),
                  2: ("Automation taking over jobs would be bad for the country.", "Robots and AI doing more of the work would be bad for the country as a whole.", "Robots and computers taking over jobs would be bad news for the country."),
                  4: ("Automation taking over jobs would be good for the country.", "Robots and AI doing more of the work would be good for the country as a whole.", "Robots and computers taking over jobs would be good news for the country."),
                  5: ("Robots and AI doing more of the work would be very good for the country.", "Automation taking over jobs would be very good for the country as a whole.", "Robots and computers taking over more of the work would be great for the country.")}), weight=0.6),
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
         agree5(("Sixteen-year-olds should definitely get the vote.", "I'm strongly in favour of votes at sixteen.", "I'd absolutely lower the voting age to sixteen."), ("I'd give sixteen-year-olds the vote.", "I'm in favour of lowering the voting age to sixteen.", "I think sixteen-year-olds should be able to vote."),
                ("I'd keep the voting age at 18.", "I don't think sixteen-year-olds should get the vote.", "I'm against lowering the voting age to sixteen."), ("Sixteen is far too young to vote.", "I'm dead against giving sixteen-year-olds the vote.", "There's no way sixteen-year-olds should be voting."))),
    Item("militaryService", "national-service", ("militaryServiceW28",),
         agree5(("Every 18-year-old should do a year of national service, military or community.", "I strongly support every 18-year-old doing a year in the forces or serving their community.", "All 18-year-olds should have to do a year of service, whether in the military or in the community."),
                ("I'd back a year of national service for 18-year-olds.", "I support 18-year-olds doing a year of national service.", "I'm in favour of a year of national service for every 18-year-old."),
                ("I'm against making 18-year-olds do a year of national service.", "I don't support a year of compulsory national service for 18-year-olds.", "I'd oppose requiring 18-year-olds to spend a year doing national service."),
                ("I'm firmly against compulsory national service for 18-year-olds.", "I strongly oppose forcing every 18-year-old to do a year of national service.", "I'm dead against making 18-year-olds do compulsory national service."))),
    Item("breakfastClub", "breakfast-clubs", ("breakfastClubW28",),
         agree5(("Every primary school should have a free breakfast club.", "I strongly support free breakfast clubs for every primary school child.", "Every primary pupil should get a free breakfast club, no question about it."),
                ("I'm in favour of free breakfast clubs in every primary school.", "I support free breakfast clubs for all primary pupils.", "I'd back giving every primary school a free breakfast club."),
                ("I'm against free breakfast clubs for all primary pupils.", "I don't support free breakfast clubs for every primary school child.", "I'd oppose putting free breakfast clubs in every primary school."),
                ("Free breakfast clubs for every primary pupil are a waste of money.", "I strongly oppose free breakfast clubs for every primary school child.", "I'm dead against giving every primary pupil a free breakfast club.")), weight=0.7),
    Item("inheritanceTax", "inheritance-tax", ("inheritanceTaxW28",),
         agree5(("Inheritance tax should be abolished altogether.", "I strongly support scrapping inheritance tax completely.", "I'd get rid of inheritance tax altogether."), ("I'd abolish inheritance tax.", "I support scrapping inheritance tax.", "I'm in favour of getting rid of inheritance tax."),
                ("I'd keep inheritance tax.", "I don't support scrapping inheritance tax.", "I'm against abolishing inheritance tax."), ("Inheritance tax should stay - scrapping it would be wrong.", "I strongly oppose abolishing inheritance tax.", "Getting rid of inheritance tax would be a serious mistake, so it should stay."))),
    Item("tripleLock", "pensions", ("tripleLockW28",),
         agree5(("Pensions should keep rising even when wages and prices don't.", "Pensions must keep going up even if wages and prices are standing still.", "I strongly believe pensions should rise even when wages and prices don't."), ("I'd keep the pensions triple lock.", "I support keeping the triple lock on pensions.", "I think pensions should go up even if wages and prices don't."),
                ("Pensions shouldn't rise faster than wages and prices.", "I don't think pensions should go up if wages and prices aren't.", "Pensions shouldn't be going up when wages and prices are standing still."), ("The pensions triple lock should go.", "I strongly disagree with pensions rising when wages and prices aren't.", "Scrap the triple lock, because pensions shouldn't go up when wages and prices don't."))),
    Item("privVAT", "private-schools", ("privVATW28",),
         agree5(("Private school fees should never have had VAT put on them.", "I strongly believe private school fees should stay tax free.", "Private school fees absolutely should be tax free, and putting VAT on them was wrong."),
                ("I'd take VAT back off private school fees.", "I think private school fees should be tax free.", "Private school fees shouldn't have VAT on them."),
                ("Private school fees should be taxed like anything else.", "I don't think private school fees should be tax free.", "I'd keep VAT on private school fees."),
                ("Putting VAT on private school fees was the right call.", "I strongly disagree that private school fees should be tax free.", "Private school fees absolutely should have VAT on them."))),
    Item("abolishPrivSchool", "private-schools", ("abolishPrivSchoolW27",),
         agree5(("Private schools should be abolished altogether.", "I strongly support getting rid of private schools.", "Private education should go completely - I'd abolish every private school."), ("I'd get rid of private schools.", "I support abolishing private schools.", "I'm in favour of getting rid of private education."),
                ("I'm against abolishing private schools.", "I don't support getting rid of private education.", "I'd oppose scrapping private schools."), ("Abolishing private schools would be completely wrong.", "I strongly oppose getting rid of private schools.", "I'm dead against abolishing private education."))),
    Item("banSmoke", "smoking-ban", ("banSmokeW27",),
         agree5(("Nobody born after 2009 should ever be sold cigarettes.", "I strongly support banning smoking for everyone born after 2009.", "Anyone born after 2009 should never be allowed to buy cigarettes, full stop."),
                ("I back the ban on selling cigarettes to anyone born after 2009.", "I support banning smoking for people born after 2009.", "I'm in favour of the smoking ban for anyone born after 2009."),
                ("I'm against banning cigarette sales by year of birth.", "I don't support banning smoking for people born after 2009.", "I'd oppose a smoking ban for those born after 2009."),
                ("A smoking ban by year of birth is the nanny state at its worst.", "I strongly oppose banning smoking for anyone born after 2009.", "I'm dead against a smoking ban based on when you were born.")), weight=0.7),
    Item("govtEnergy", "public-energy", ("govtEnergyW27",),
         agree5(("A publicly owned renewable energy company is exactly what we need.", "I strongly support a government-owned renewable energy company.", "We absolutely should have a publicly owned renewable energy company."),
                ("I back a publicly owned renewable energy company.", "I support the government creating a renewable energy company.", "I'm in favour of a state-owned renewable energy company."),
                ("I'm against a publicly owned energy company.", "I don't support a government-owned renewable energy company.", "I'd oppose the state creating its own energy company."),
                ("The state has no business running an energy company.", "I strongly oppose a government-owned renewable energy company.", "I'm dead against the government setting up its own energy company.")), weight=0.7),
    Item("newTown", "housing", ("newTownW27",),
         agree5(("We should be building new towns - we need the houses.", "I strongly support building new towns to provide more housing.", "Build the new towns, because we badly need the homes."),
                ("I'm in favour of building new towns to get more houses built.", "I support building new towns to provide more homes.", "I'd back new towns as a way of getting more houses built."),
                ("I'm against building new towns.", "I don't support building new towns to provide more homes.", "I'd oppose building new towns for housing."), ("Building new towns is entirely the wrong answer.", "I strongly oppose building new towns to provide more houses.", "I'm dead against building new towns for housing."))),
    Item("monarch", "monarchy", ("monarchW25",),
         agree5(("Britain should definitely keep the monarchy.", "I strongly believe Britain should keep its monarchy.", "Britain absolutely must carry on having a monarchy."), ("I'd keep the monarchy.", "I think Britain should carry on having a monarchy.", "I'm for keeping the monarchy."),
                ("I'd rather we did away with the monarchy.", "I don't think Britain should carry on having a monarchy.", "I'd be happy to see the monarchy go."), ("The monarchy should go.", "I strongly disagree that Britain should keep the monarchy.", "Britain should definitely get rid of the monarchy."))),
    Item("keepNukes", "nuclear-weapons", ("keepNukesW23",),
         agree5(("Britain must keep its nuclear submarines.", "I strongly believe Britain should keep its nuclear weapons.", "Britain absolutely has to keep its nuclear submarines."), ("I'd keep Britain's nuclear weapons.", "I think Britain should keep its nuclear submarines.", "I'm for Britain holding on to its nuclear weapons."),
                ("I'd give up Britain's nuclear weapons.", "I don't think Britain should keep its nuclear submarines.", "I'd rather Britain got rid of its nuclear weapons."), ("Britain should scrap its nuclear weapons altogether.", "I strongly disagree with Britain keeping its nuclear submarines.", "Britain should definitely get rid of its nuclear weapons."))),
    Item("overseasAid", "foreign-aid", ("overseasAidW30", "overseasAidW27"),
         agree5(("Britain should stop all overseas aid spending, every penny of it.", "I strongly believe Britain should stop all overseas aid spending.", "Britain should end overseas aid spending completely, not a penny more."), ("Britain should stop spending on overseas aid.", "I think Britain should stop all government spending on overseas aid.", "I'd end Britain's overseas aid spending."),
                ("Britain should keep spending on overseas aid.", "I don't think Britain should stop spending on overseas aid.", "I'd keep the overseas aid spending going."), ("Cutting overseas aid to nothing would be shameful.", "I strongly disagree with stopping all overseas aid spending.", "Britain should definitely not stop spending on overseas aid."))),
    Item("natSecuritySpending", "defence", ("natSecuritySpendingW30", "natSecuritySpendingW25"),
         by_code({5: ("Britain should spend a lot more on defence.", "I'd spend a lot more on defence.", "The government should be putting a lot more money into defence."), 4: ("I'd spend a bit more on defence.", "The government should spend somewhat more on defence.", "I'd put a little more money into defence."), 3: ("Defence spending is about right.", "I think the amount we spend on defence is about right.", "Defence spending is about right as it is, so I'd keep it the same."),
                  2: ("I'd spend a bit less on defence.", "The government should spend somewhat less on defence.", "I'd trim defence spending a little."), 1: ("Britain should spend a lot less on defence.", "I'd cut defence spending by a lot.", "The government should spend a lot less on defence.")})),
    Item("renationaliseRail", "nationalisation", ("renationaliseRailW26",),
         agree5(("Bringing the railways back into public ownership is right, and about time too.", "I strongly believe Britain should renationalise the railways.", "The railways absolutely should be back in public ownership."), ("Bringing the railways back into public ownership is the right thing to do.", "I think Britain should renationalise the railways.", "I support bringing the railways back into public ownership."),
                ("I'm against bringing the railways back into public ownership.", "I don't think Britain should renationalise the railways.", "I wouldn't bring the railways back into public ownership."), ("Taking the railways back into public ownership is a big mistake.", "I strongly disagree with renationalising the railways.", "Renationalising the railways is completely the wrong move."))),
    Item("nationaliseUtilities", "nationalisation", ("nationalizeUtilitiesW26",),
         by_code({1: ("Gas, electricity and water should be run entirely by the public sector.", "Gas, electricity and water should be completely in public hands.", "I think the public sector alone should provide gas, electricity and water."),
                  2: ("Gas, electricity and water should be mostly in public hands.", "Gas, electricity and water should be provided mostly by the public sector.", "I'd have the public sector running most of our gas, electricity and water."),
                  3: ("Gas, electricity and water should be a mix of public and private.", "Gas, electricity and water should be provided equally by the public and private sectors.", "I'd split gas, electricity and water evenly between public and private."),
                  4: ("Gas, electricity and water should be mostly run by private firms.", "Gas, electricity and water should be provided mostly by the private sector.", "I'd have private companies running most of our gas, electricity and water."),
                  5: ("Gas, electricity and water should be run entirely by private firms.", "Gas, electricity and water should be completely in private hands.", "I think the private sector alone should provide gas, electricity and water.")})),
    Item("nationaliseHospitals", "nationalisation", ("nationalizeHospitalsW26",),
         by_code({1: ("Hospitals should be run entirely by the public sector.", "Hospitals should be completely in public hands.", "I think the public sector alone should run hospitals."), 2: ("Hospitals should be mostly in public hands.", "Hospitals should be run mostly by the public sector.", "I'd have the public sector running most hospitals."),
                  4: ("Hospitals should be mostly run by private firms.", "Hospitals should be run mostly by the private sector.", "I'd have private companies running most hospitals."), 5: ("Hospitals should be run entirely by private firms.", "Hospitals should be completely in private hands.", "I think the private sector alone should run hospitals.")}), weight=0.6),
    Item("nationaliseSchools", "nationalisation", ("nationalizeSchoolsW26",),
         by_code({1: ("Schools should be run entirely by the public sector.", "Schools should be completely in public hands.", "I think the public sector alone should run schools."), 2: ("Schools should be mostly in public hands.", "Schools should be run mostly by the public sector.", "I'd have the public sector running most schools."),
                  4: ("Schools should be mostly run by private firms.", "Schools should be run mostly by the private sector.", "I'd have private companies running most schools."), 5: ("Schools should be run entirely by private firms.", "Schools should be completely in private hands.", "I think the private sector alone should run schools.")}), weight=0.5),
    Item("pubPrivEfficient", "nationalisation", ("pubPrivEfficientW26",),
         scale11(("Private companies give better value on gas, water and electricity.", "Private firms offer consumers better value on gas, water and electricity.", "When it comes to utilities, the private sector gives the better value."),
                 ("Private firms probably give better value on utilities.", "I'd say the private sector probably offers better value on gas, water and electricity.", "On balance, private companies probably give better value on utilities."),
                 ("The public sector probably gives better value on utilities.", "I'd say the public sector probably offers better value on gas, water and electricity.", "On balance, public ownership probably gives better value on utilities."),
                 ("The public sector gives far better value on gas, water and electricity.", "Public ownership gives much better value on gas, water and electricity.", "On utilities, the public sector offers far better value than private companies.")), weight=0.6),
    Item("privateHospChoice", "private-health", ("privateHospChoiceW26",),
         agree5(("People should have every right to pay to be seen faster in healthcare.", "I strongly believe people should be able to pay privately to be seen faster.", "People absolutely should have the choice to pay for quicker healthcare."),
                ("People should be able to pay to be seen faster if they want to.", "I think people should have the choice to pay privately for quicker healthcare.", "If someone wants to pay to get seen sooner, that should be their choice."),
                ("Nobody should be able to jump the healthcare queue by paying.", "I don't think people should be able to pay for quicker healthcare.", "I'm against people paying privately to be seen faster."),
                ("Paying to jump the healthcare queue is plain wrong.", "I strongly disagree that people should be able to pay to be seen faster.", "Nobody should get quicker healthcare just because they can pay, and I feel strongly about that."))),
    Item("privateHospAfford", "private-health", ("privateHospAffordW26",),
         agree5(("Private healthcare is unfair - only the rich can afford it.", "I strongly believe private healthcare is unfair because only the rich can afford it.", "Private healthcare is deeply unfair when only rich people can afford it."), ("Private healthcare isn't fair when only the rich can afford it.", "I think private healthcare is unfair because only rich people can afford it.", "It's not fair that only the well-off can afford private healthcare."),
                ("I don't see private healthcare as unfair.", "I don't think private healthcare is unfair because only the rich can afford it.", "Private healthcare isn't unfair in my view."), ("There's nothing unfair about private healthcare.", "I strongly disagree that private healthcare is unfair.", "Private healthcare definitely isn't unfair just because only the rich can afford it.")), weight=0.7),
    Item("zeroHours", "zero-hours", ("zeroHourContractW27",),
         by_code({1: ("Zero-hours contracts should definitely be illegal.", "Zero-hours contracts should be banned, no question.", "I'd definitely make zero-hours contracts illegal."), 2: ("Zero-hours contracts should probably be banned.", "Zero-hours contracts should probably be made illegal.", "On balance, I'd make zero-hours contracts illegal."),
                  3: ("Zero-hours contracts should probably stay legal.", "Zero-hours contracts should probably be allowed.", "On balance, I'd keep zero-hours contracts legal."), 4: ("Zero-hours contracts should definitely stay legal.", "Zero-hours contracts should be allowed, no question.", "I'd definitely keep zero-hours contracts legal.")})),
    Item("deficit", "deficit", ("deficitReduceW27",),
         by_code({4: ("Getting rid of the deficit is completely necessary.", "Eliminating the deficit is absolutely essential.", "We have to get rid of the deficit - it's completely necessary."), 3: ("Cutting the deficit matters, but it isn't everything.", "Eliminating the deficit is important, but not absolutely necessary.", "Getting the deficit down matters, but it's not an absolute must."),
                  2: ("Cutting the deficit would be nice but it isn't necessary.", "Getting rid of the deficit isn't necessary, though it would be desirable.", "I'd like to see the deficit gone, but it's not something we have to do."), 1: ("There's no need to eliminate the deficit at all.", "Eliminating the deficit is completely unnecessary.", "I don't think there's any need whatsoever to get rid of the deficit.")})),
    Item("howToReduceDeficit", "deficit", ("howToReduceDeficitW27",),
         by_code({1: ("If the deficit has to come down, do it through taxes, not cuts.", "Cut the deficit purely through tax rises, with no spending cuts.", "If we're cutting the deficit, it should be done only by raising taxes."),
                  2: ("Cut the deficit mainly with tax rises, with some spending cuts.", "Reduce the deficit mostly by raising taxes, with a bit of spending cut too.", "I'd bring the deficit down mainly through higher taxes, plus some cuts."),
                  3: ("Cut the deficit with an even mix of tax rises and spending cuts.", "Reduce the deficit with an equal balance of spending cuts and tax rises.", "I'd bring the deficit down half through tax rises and half through cuts."),
                  4: ("Cut the deficit mainly through spending cuts, with a few tax rises.", "Reduce the deficit mostly by cutting spending, with some tax rises too.", "I'd bring the deficit down mainly through cuts, plus a bit of extra tax."),
                  5: ("Cut the deficit through spending cuts alone - no tax rises.", "Reduce the deficit purely by cutting spending, not by raising taxes.", "If we're cutting the deficit, it should be done only through spending cuts.")}), weight=0.6),
    Item("inequalityLevel", "inequality", ("inequalityLevelW25",),
         by_code({1: ("The gap between rich and poor is much too wide.", "The income gap between rich and poor is far too big.", "Income inequality in the UK is much too high."), 2: ("The gap between rich and poor is too wide.", "The income gap between rich and poor is too big.", "Income inequality in the UK is too high."),
                  3: ("The gap between rich and poor is about right.", "The income gap between rich and poor is about right as it is.", "I think the difference in incomes between rich and poor is about right."), 4: ("The gap between rich and poor is too small.", "The income gap between rich and poor is too narrow.", "Income inequality in the UK is too low."),
                  5: ("The gap between rich and poor is far too small.", "The income gap between rich and poor is much too narrow.", "Income inequality in the UK is much too low.")})),
    Item("changeInequality", "inequality", ("changeInequalityW21",),
         by_code({5: ("The gap between rich and poor is getting much wider.", "Inequality in Britain is getting much higher.", "The gap between rich and poor is growing a lot."), 4: ("The gap between rich and poor is getting wider.", "Inequality in Britain is getting higher.", "The gap between rich and poor is growing."),
                  2: ("The gap between rich and poor is getting smaller.", "Inequality in Britain is getting lower.", "The gap between rich and poor is narrowing."), 1: ("The gap between rich and poor is closing fast.", "Inequality in Britain is getting much lower.", "The gap between rich and poor is shrinking a lot.")}), weight=0.5),
    Item("climateChange", "climate", ("climateChangeW26",),
         by_code({1: ("Climate change is real and it's us causing it.", "The climate is changing and human activity is behind it.", "I think the world's climate is changing because of what humans are doing."),
                  2: ("The climate is changing, but I don't think humans are the cause.", "The world's climate is changing, but not because of human activity.", "I think the climate is changing, just not because of us."),
                  3: ("I don't believe the climate is changing.", "The world's climate isn't changing.", "I don't think the climate is changing at all.")})),
    # Values and outlook
    Item("britishPride", "pride", ("britishPrideW27", "britishPrideW25"),
         agree5(("I'm very proud to be British.", "I feel really proud to be British.", "I'm extremely proud of being British."), ("I'm proud to be British.", "I feel proud of being British.", "Being British is something I'm proud of."),
                ("I'm not especially proud to be British.", "I don't feel particularly proud to be British.", "I wouldn't say I'm proud to be British."), ("I'm not proud to be British.", "I feel no pride in being British.", "I'm really not proud of being British."))),
    Item("radical", "change", ("radicalW27", "radicalW25"),
         agree5(("We need to fundamentally change how society works in Britain.", "I strongly believe British society needs to be fundamentally changed.", "The way society works in Britain absolutely has to change from the ground up."), ("Britain needs big changes to how society works.", "I think we need to fundamentally change how society works in Britain.", "The way society works in Britain needs fundamental change."),
                ("I don't think society in Britain needs fundamental change.", "I don't see the need to fundamentally change how society works in Britain.", "I'd say British society doesn't need changing in any fundamental way."), ("Society doesn't need fundamental change - it mostly works.", "I strongly disagree that we need to fundamentally change how society works in Britain.", "British society definitely doesn't need a fundamental overhaul."))),
    Item("harkBack", "change", ("harkBackW27", "harkBackW25"),
         agree5(("Things in Britain were definitely better in the past.", "I strongly believe things in Britain were better in the past.", "There's no doubt things in Britain used to be better."), ("Things in Britain were better in the past.", "I think things in Britain used to be better.", "Britain was a better place in the past."),
                ("I don't think things were better in the past.", "I'd say things in Britain weren't better in the past.", "Things in Britain weren't better back in the day, in my view."), ("Things in Britain were not better in the past - that's rose-tinted thinking.", "I strongly disagree that things in Britain were better in the past.", "Things in Britain definitely weren't better back then."))),
    Item("populismPeople", "populism", ("populism2W27", "populism2W26"),
         agree5(("The people, not politicians, should be making the big decisions.", "I strongly believe the people, not politicians, should make the most important policy decisions.", "The most important decisions absolutely should be made by the people, not politicians."),
                ("I'd rather the people made the big decisions than politicians.", "I think the people, not politicians, should make the most important policy decisions.", "The biggest policy decisions should be for the people to make, not politicians."),
                ("Big decisions are better left to elected politicians than to the public.", "I don't think the public should make the big policy decisions rather than politicians.", "The big policy decisions should be made by politicians, not the public."),
                ("The public shouldn't be making the big policy decisions instead of politicians.", "I strongly disagree that the people rather than politicians should make the big policy decisions.", "The most important policy decisions definitely shouldn't be taken out of politicians' hands.")), weight=0.7),
    Item("populismTalk", "populism", ("populism5W27", "populism5W26"),
         agree5(("Politicians talk far too much and do far too little.", "I strongly believe politicians talk too much and do far too little.", "Politicians are all talk and hardly any action."), ("Politicians talk too much and act too little.", "I think politicians talk too much and don't do enough.", "Politicians are too much talk and not enough action."),
                ("I don't think politicians are all talk.", "I don't think politicians talk too much and do too little.", "I wouldn't say politicians are all talk and no action."), ("Politicians aren't all talk.", "I strongly disagree that politicians talk too much and do too little.", "Politicians definitely aren't all talk and no action.")), weight=0.6),
    Item("populismCompromise", "populism", ("populism6W27", "populism6W26"),
         agree5(("Compromise in politics is just selling out your principles.", "I strongly believe political compromise is nothing but selling out your principles.", "What politicians call compromise is really just a sell-out of their principles."), ("Political compromise usually means selling out.", "I think what people call compromise in politics is really selling out your principles.", "Compromise in politics is mostly just selling out."),
                ("Compromise in politics isn't selling out - it's how things get done.", "I don't think compromise in politics is just selling out your principles.", "I wouldn't call political compromise a sell-out."), ("Compromise is the heart of politics, not a sell-out.", "I strongly disagree that political compromise is just selling out your principles.", "Compromise in politics definitely isn't a sell-out.")),
         weight=0.6),
    Item("antiIntellectual", "experts", ("antiIntellectualW23", "antiIntellectualW21"),
         agree5(("I'd trust the common sense of ordinary people over the experts any day.", "I'd much rather trust the wisdom of ordinary people than the opinions of experts.", "Give me the wisdom of ordinary people over the experts every time."),
                ("I'd rather trust ordinary people's wisdom than the experts.", "I'd sooner put my trust in ordinary people than in the opinions of experts.", "I think the wisdom of ordinary people is more trustworthy than the experts."),
                ("I'd rather trust the experts than the wisdom of the crowd.", "I'd sooner trust the opinions of experts than the wisdom of ordinary people.", "I don't think ordinary people's wisdom beats expert opinion."),
                ("Give me the experts over the wisdom of ordinary people every time.", "I strongly disagree with trusting ordinary people's wisdom over the experts.", "I'd much rather trust expert opinion than the wisdom of ordinary people."))),
    Item("dutyToVote", "voting-duty", ("dutyToVote2W27", "dutyToVote2W26"),
         agree5(("Voting is every citizen's duty, without exception.", "I strongly believe it's every citizen's duty to vote.", "Every single citizen has a duty to vote, no excuses."), ("It's every citizen's duty to vote.", "I think everyone has a duty to vote in an election.", "Voting is a duty for every citizen."),
                ("I don't think people have a duty to vote.", "I don't think it's every citizen's duty to vote.", "I wouldn't say voting is a duty."), ("Nobody has a duty to vote - it's a choice.", "I strongly disagree that voting is every citizen's duty.", "Voting definitely isn't a duty - it's up to each person.")), weight=0.7),
    Item("wastedVote", "tactical-voting", ("smallPartyWastedVoteW27", "smallPartyWastedVoteW25"),
         agree5(("Voting for a small party is throwing your vote away.", "I strongly believe a vote for a small party is a wasted vote.", "Vote for a small party and you've definitely thrown your vote away."), ("A vote for a small party is a wasted vote.", "I think people who vote for small parties are throwing their vote away.", "Voting for a small party means wasting your vote."),
                ("A vote for a small party isn't wasted.", "I don't think people who vote for small parties are throwing their vote away.", "Voting for a small party isn't throwing your vote away."), ("Voting for a small party is never a wasted vote.", "I strongly disagree that voting for a small party is throwing your vote away.", "A vote for a small party is definitely not wasted.")), weight=0.7),
    Item("smallVoterPref", "tactical-voting", ("smallVoterPrefW27", "smallVoterPrefW25"),
         agree5(("Always vote for the party you like best, even if they can't win.", "I strongly believe people should vote for the party they like most, even if it can't win.", "Vote for the party you really want, no matter whether it can win."), ("Vote for the party you like best, whether or not they can win.", "I think people should vote for the party they like most, even if it's unlikely to win.", "You should back the party you like best, even if they're not likely to win."),
                ("There's not much point voting for a party that can't win.", "I don't think people should vote for the party they like most if it's unlikely to win.", "Voting for a party you like that can't win doesn't make much sense."), ("There's no point at all voting for a party that can't win.", "I strongly disagree that people should vote for their favourite party if it can't win.", "There's absolutely no point voting for a party that isn't going to win.")), weight=0.7),
    Item("polPreferToFight", "politicians", ("polPreferToFightW28",),
         agree5(("Politicians care far more about fighting each other than about the public.", "I strongly believe parties care more about fighting each other than about the public interest.", "Politicians are far more interested in fighting each other than in what's good for the public."),
                ("Parties are more interested in fighting each other than in the public interest.", "I think politicians care more about fighting each other than about serving the public.", "Parties are more bothered about scrapping with each other than about the public interest."),
                ("Parties aren't just in it to fight each other.", "I don't think parties are more concerned with fighting each other than with the public interest.", "I wouldn't say politicians care more about fighting each other than about the public."), ("I don't think politicians are just fighting each other.", "I strongly disagree that politicians care more about fighting each other than the public interest.", "Politicians definitely aren't more interested in fighting each other than serving the public.")), weight=0.6),
    Item("partyDifference", "party-difference", ("partydiffconlabW28",),
         by_code({1: ("There's a world of difference between Labour and the Tories.", "There's a great difference between the Conservatives and Labour.", "Labour and the Conservatives are worlds apart."),
                  2: ("There's some difference between Labour and the Tories.", "There's some difference between the Conservatives and Labour.", "There are some differences between Labour and the Conservatives."),
                  3: ("There's not much difference between Labour and the Tories.", "There isn't a lot of difference between the Conservatives and Labour.", "Labour and the Tories are pretty much the same.")}), weight=0.7),
    Item("prPreference", "electoral-system", ("prPreferenceW29",),
         by_code({1: ("I'd rather one party won outright and governed alone than have proportional representation.", "I'd rather one party got a majority and governed on its own than have seats match votes.", "What matters to me is one party winning enough seats to govern on its own."),
                  2: ("Seats in parliament should match votes - I want proportional representation.", "Every party's share of seats should match its share of the vote.", "I'd rather parties got seats in line with their share of the vote than one party governing alone.")})),
    Item("voterID", "voter-id", ("voterIDSupportW29", "voterIDSupportW25"),
         agree5(("Photo ID at polling stations is the right thing.", "I strongly support making people show photo ID to vote.", "People absolutely should have to show photo ID before they vote."), ("I support needing photo ID to vote.", "I'm in favour of people having to show photo ID to vote.", "I'd back requiring photo ID at polling stations."),
                ("I'm against needing photo ID to vote.", "I don't support requiring photo ID to vote.", "I'd oppose making people show photo ID before they vote."), ("Making people show photo ID to vote is wrong.", "I strongly oppose making people show photo ID to vote.", "I'm dead against requiring photo ID at the polling station.")), weight=0.7),
    Item("satDemUK", "democracy", ("satDemUKW29", "satDemUKW27"),
         by_code({1: ("I'm very dissatisfied with how democracy works in the UK.", "The way democracy works in the UK leaves me very dissatisfied.", "I'm really unhappy with how democracy works in the UK.", "I'm really unhappy with the way democracy works in the UK."), 2: ("I'm a bit dissatisfied with how democracy works in the UK.", "I'm a little dissatisfied with the way democracy works in the UK.", "How democracy works in the UK leaves me a bit dissatisfied."),
                  3: ("I'm fairly satisfied with how democracy works in the UK.", "On the whole, I'm fairly happy with how democracy works in the UK.", "I'm reasonably satisfied with the way democracy works in the UK.", "On the whole, I'm reasonably happy with how democracy works in the UK.", "I'm pretty satisfied with the way democracy works in the UK."), 4: ("I'm very satisfied with how democracy works in the UK.", "I'm very happy with the way democracy works in the UK.", "On the whole, I'm very satisfied with the way democracy works in the UK.", "As far as I'm concerned, democracy in the UK works very well.")})),
    Item("satDemScot", "democracy", ("satDemScotW29",),
         by_code({1: ("I'm very dissatisfied with how democracy works in Scotland.", "The way democracy works in Scotland leaves me very dissatisfied.", "I'm really unhappy with how democracy works in Scotland."), 2: ("I'm a bit dissatisfied with how democracy works in Scotland.", "I'm a little dissatisfied with the way democracy works in Scotland.", "How democracy works in Scotland leaves me a bit dissatisfied."),
                  3: ("I'm fairly satisfied with how democracy works in Scotland.", "On the whole, I'm fairly happy with how democracy works in Scotland.", "I'm reasonably satisfied with the way democracy works in Scotland."), 4: ("I'm very satisfied with how democracy works in Scotland.", "I'm very happy with the way democracy works in Scotland.", "On the whole, I'm very satisfied with the way democracy works in Scotland.")}),
         nations=(2,)),
    Item("satDemWales", "democracy", ("satDemWalesW29",),
         by_code({1: ("I'm very dissatisfied with how democracy works in Wales.", "The way democracy works in Wales leaves me very dissatisfied.", "I'm really unhappy with how democracy works in Wales."), 2: ("I'm a bit dissatisfied with how democracy works in Wales.", "I'm a little dissatisfied with the way democracy works in Wales.", "How democracy works in Wales leaves me a bit dissatisfied."),
                  3: ("I'm fairly satisfied with how democracy works in Wales.", "On the whole, I'm fairly happy with how democracy works in Wales.", "I'm reasonably satisfied with the way democracy works in Wales."), 4: ("I'm very satisfied with how democracy works in Wales.", "I'm very happy with the way democracy works in Wales.", "On the whole, I'm very satisfied with the way democracy works in Wales.")}),
         nations=(3,)),
    Item("trustYourMP", "trust", ("trustYourMPW27",),
         by_code({1: ("I don't trust my local MP one bit.", "I've no trust at all in my local MP.", "I don't trust my local MP at all."), 2: ("I've little trust in my local MP.", "I don't trust my local MP much.", "I've not got much trust in my local MP."), 5: ("I trust my local MP a fair amount.", "I trust my local MP a fair bit.", "I've a fair amount of trust in my local MP."),
                  6: ("I trust my local MP a good deal.", "I trust my local MP quite a lot.", "I've a good deal of trust in my local MP."), 7: ("I trust my local MP a great deal.", "I've a great deal of trust in my local MP.", "I trust my local MP very much.")}), weight=0.6),
    Item("genTrust", "social-trust", ("genTrustW27", "genTrustW23"),
         by_code({1: ("Most people can be trusted.", "Generally speaking, most people can be trusted.", "On the whole, people can be trusted."), 2: ("You can't be too careful in dealing with people.", "You can't be too careful with people.", "When it comes to dealing with people, you can't be too careful.")})),
    Item("homenorm", "home-ownership", ("homenormW23",),
         agree5(("If you haven't bought a home by 40, you haven't made it.", "Anyone who hasn't bought a home by 40 hasn't made it.", "If you're 40 and still haven't bought a home, you haven't made it."),
                ("To count as a success you need to own a home by 40.", "Owning a home by 40 is part of being a success in life.", "You need to own your own home by 40 to count as successful."),
                ("You don't need to own a home by 40 to be a success.", "You can be a success without owning a home by 40.", "Not owning a home by 40 doesn't mean you haven't made it."),
                ("Owning a home by 40 has nothing to do with success in life.", "Whether you own a home by 40 has nothing to do with success in life.", "Success in life has nothing to do with owning a home by 40.")), weight=0.6),
    Item("econSecurityFuture", "personal-outlook", ("EconSecurityFutureW25", "EconSecurityFutureW23"),
         by_code({1: ("I expect to be a lot better off in ten years' time.", "In ten years, I expect to be a lot better off.", "I think I'll be much better off ten years from now."), 2: ("I expect to be a little better off in ten years.", "In ten years' time, I expect to be a bit better off.", "I think I'll be slightly better off ten years from now."),
                  4: ("I expect to be a little worse off in ten years.", "In ten years' time, I expect to be a bit worse off.", "I think I'll be slightly worse off ten years from now."), 5: ("I expect to be a lot worse off in ten years' time.", "In ten years, I expect to be a lot worse off.", "I think I'll be much worse off ten years from now.")}), weight=0.6),
    Item("statusLadder", "status", ("statusTopBottomW30", "statusTopBottomW21"),
         by_code({1: ("I'd put myself right at the bottom of the pile in society.", "In society's pecking order, I'm right at the bottom.", "I'm at the very bottom of the ladder in society."), 2: ("I'd put myself near the bottom of the pile in society.", "I'm near the bottom of the ladder in society.", "In society's pecking order, I'm close to the bottom."),
                  3: ("I'd put myself near the bottom of the pile in society.", "I'm near the bottom of the ladder in society.", "In society's pecking order, I'm close to the bottom."), 4: ("I'd put myself a bit below the middle of society.", "I'm a little below the middle of the ladder in society.", "In society's pecking order, I'm just below the middle."),
                  7: ("I'd put myself a bit above the middle of society.", "I'm a little above the middle of the ladder in society.", "In society's pecking order, I'm just above the middle."), 8: ("I'd put myself near the top of the pile in society.", "I'm near the top of the ladder in society.", "In society's pecking order, I'm close to the top."),
                  9: ("I'd put myself near the top of the pile in society.", "I'm near the top of the ladder in society.", "In society's pecking order, I'm close to the top."), 10: ("I'd put myself right at the top of the pile in society.", "I'm at the very top of the ladder in society.", "In society's pecking order, I'm right at the top.")}),
         weight=0.5),
    # Welfare and work (wave 20 values battery)
    Item("jobForAll", "state-role", ("jobForAllW20",),
         agree5(("It's the government's job to make sure everyone who wants work has it.", "The government is definitely responsible for providing a job for everyone who wants one.", "Making sure everyone who wants a job has one is absolutely the government's job."),
                ("Government should provide a job for everyone who wants one.", "It's the government's responsibility to provide a job for everyone who wants one.", "The government ought to make sure there's a job for everyone who wants one."),
                ("It isn't the government's job to find everyone work.", "Providing a job for everyone who wants one isn't the government's responsibility.", "I don't think it's up to the government to find everyone a job."), ("Providing jobs for everyone is not the government's job at all.", "It's definitely not the government's job to provide work for everyone.", "Finding everyone a job is not the government's responsibility at all."))),
    Item("stateOwnership", "state-role", ("stateOwnershipW20",),
         agree5(("Major public services and industries should definitely be in state hands.", "I strongly believe major public services and industries should be state-owned.", "There's no question major public services and industries ought to be state-owned."),
                ("Major public services and industries ought to be state-owned.", "Major public services and industries should be in state hands.", "I think the state should own the major public services and industries."),
                ("Major industries shouldn't be in state hands.", "I don't think major public services and industries should be state-owned.", "Major public services and industries are better off out of state hands."), ("State ownership of major industries is the wrong way to go.", "Major public services and industries definitely shouldn't be state-owned.", "I'm firmly against state ownership of major industries.")), weight=0.7),
    Item("privateEnterprise", "state-role", ("privateEnterpriseW20",),
         agree5(("Private enterprise is definitely the best way to fix Britain's economic problems.", "There's no doubt private enterprise is the best way to solve Britain's economic problems.", "I strongly believe private enterprise is the answer to Britain's economic problems."),
                ("Private enterprise is the best way to solve Britain's economic problems.", "Private enterprise is the best answer to Britain's economic problems.", "The best way to fix Britain's economy is through private enterprise."),
                ("Private enterprise isn't the answer to Britain's economic problems.", "I don't think private enterprise is the best way to solve Britain's economic problems.", "Britain's economic problems won't be solved by private enterprise."),
                ("Leaving our economic problems to private enterprise would be a disaster.", "Private enterprise is definitely not the answer to Britain's economic problems.", "I strongly disagree that private enterprise is the way to fix Britain's economy.")), weight=0.7),
    Item("govtHandouts", "welfare-attitudes", ("govtHandoutsW20",),
         agree5(("Far too many people like living off government handouts.", "There are far too many people these days who like to rely on handouts.", "Far too many people are content to live off government handouts."), ("Too many people rely on government handouts these days.", "These days, too many people like to rely on government handouts.", "Too many people are happy to live off government handouts."),
                ("I don't think too many people rely on handouts.", "I don't think too many people like to rely on government handouts.", "I wouldn't say too many people rely on government handouts these days."), ("The idea people choose to live off handouts is a myth.", "It's simply not true that too many people like living off government handouts.", "I strongly disagree that people these days like to rely on handouts."))),
    Item("benefitsNotDeserved", "welfare-attitudes", ("benefitsNotDeservedW20",),
         agree5(("Plenty of people on benefits don't really deserve the help.", "Lots of people on benefits don't deserve any help at all.", "Far too many people on benefits don't really deserve the help."), ("Many people on benefits don't really deserve help.", "A lot of people on benefits don't really deserve the help.", "Many people getting benefits don't genuinely deserve them."),
                ("Most people on benefits genuinely need the help.", "Most people getting benefits really do need the help.", "I don't think people on benefits are undeserving of help."), ("People on benefits fully deserve the help they get.", "People on benefits deserve every bit of help they get.", "I strongly disagree that people on benefits don't deserve help."))),
    Item("reasonForUnemployment", "welfare-attitudes", ("reasonForUnemploymentW20",),
         agree5(("When someone's out of work, it's almost never their own fault.", "People who are out of work are hardly ever to blame for it.", "Unemployment is almost never the person's own doing."), ("Unemployment is usually through no fault of the person's own.", "People out of work usually aren't to blame for it.", "Most of the time, unemployment isn't the person's own fault."),
                ("Being out of work is often the person's own doing.", "People out of work often have themselves to blame.", "Quite often, unemployment is the person's own fault."), ("People out of work usually have themselves to blame.", "When people are out of work, it's usually their own fault.", "Unemployment is mostly the person's own doing.")), weight=0.7),
    Item("immigrantsWelfare", "immigration", ("immigrantsWelfareStateW20",),
         agree5(("Immigrants are clearly a burden on the welfare state.", "There's no doubt immigrants are a burden on the welfare state.", "Immigrants are a real burden on the welfare state."), ("Immigrants are a burden on the welfare state.", "Immigrants put a burden on the welfare state.", "I think immigrants are a burden on the welfare state."),
                ("I don't think immigrants are a burden on the welfare state.", "I wouldn't say immigrants are a burden on the welfare state.", "Immigrants aren't really a burden on the welfare state."), ("Immigrants are no burden on the welfare state at all.", "Immigrants aren't a burden on the welfare state in the slightest.", "I strongly disagree that immigrants are a burden on the welfare state.")), weight=0.6),
    Item("immigCultural", "immigration", ("immigCulturalW27", "immigCulturalW24"),
         by_code({1: ("Immigration undermines Britain's culture - badly.", "Immigration does real damage to Britain's cultural life.", "Britain's cultural life is badly undermined by immigration."), 2: ("Immigration undermines British cultural life.", "Immigration is bad for British cultural life.", "British cultural life is undermined by immigration."),
                  3: ("On balance, immigration takes something away from British culture.", "On balance, immigration does British cultural life more harm than good.", "Immigration slightly undermines British cultural life, on balance."),
                  5: ("On balance, immigration adds something to British culture.", "On balance, immigration does British cultural life more good than harm.", "Immigration slightly enriches British cultural life, on balance."),
                  6: ("Immigration enriches British cultural life.", "Immigration is good for British cultural life.", "British cultural life is enriched by immigration."), 7: ("Immigration enriches Britain's culture enormously.", "Immigration does a great deal for Britain's cultural life.", "Britain's cultural life is hugely enriched by immigration.")}), weight=0.6),
    Item("studentsMore", "immigration", ("studentsMoreW26", "studentsMoreW25"),
         scale11(("Britain should take far fewer foreign students.", "Far fewer foreign students should be allowed to come to Britain.", "Britain should cut the number of foreign students right back."), ("I'd take fewer foreign students.", "I'd let fewer foreign students into Britain.", "Britain should take in fewer foreign students."),
                 ("I'd happily take more foreign students.", "I'd let more foreign students into Britain.", "Britain should take in more foreign students."), ("Britain should welcome many more foreign students.", "Far more foreign students should be allowed to come to Britain.", "I'd let in many more foreign students.")), weight=0.4),
    Item("euMore", "immigration", ("euMoreW26", "euMoreW25"),
         scale11(("Far fewer workers from the EU should be let in.", "Britain should let in far fewer EU workers.", "The number of workers coming from the EU should be cut right back."), ("I'd let in fewer workers from the EU.", "Britain should let in fewer workers from the EU.", "I'd cut the number of EU workers coming in."),
                 ("I'd let in more workers from the EU.", "Britain should let in more workers from the EU.", "I'd have more workers coming in from the EU."), ("Britain should let in many more workers from the EU.", "Far more workers from the EU should be let in.", "I'd let in many more EU workers.")), weight=0.4),
    Item("familiesMore", "immigration", ("familiesMoreW26", "familiesMoreW25"),
         scale11(("Far fewer relatives of people already here should be let in.", "Britain should let in far fewer relatives of people already settled here.", "The number of relatives joining people already here should be cut right back."), ("I'd let in fewer relatives of people already here.", "Britain should let in fewer relatives of people already settled here.", "I'd cut the number of relatives joining people already here."),
                 ("I'd let in more relatives of people already settled here.", "Britain should let in more relatives of people already here.", "I'd have more relatives of people already settled here coming in."), ("Families of people already here should be welcomed in.", "Britain should let in many more relatives of people already settled here.", "I'd let in far more relatives of people already here.")), weight=0.4),
    # Brexit, looking back
    Item("brexitEcon", "brexit-effects", ("effectsEUEconRetroW27",),
         by_code({1: ("Brexit has made the economy much worse.", "The economy is much worse off because of Brexit.", "Brexit has done the economy a lot of harm."), 2: ("Brexit has made the economy worse.", "The economy is worse off because of Brexit.", "Brexit has done the economy harm."),
                  3: ("Brexit hasn't made much difference to the economy.", "The economy is neither better nor worse for Brexit.", "Brexit has made little difference to the economy either way."), 4: ("Brexit has made the economy better.", "The economy is better off because of Brexit.", "Brexit has done the economy good."),
                  5: ("Brexit has made the economy much better.", "The economy is much better off because of Brexit.", "Brexit has done the economy a lot of good.")})),
    Item("brexitNHS", "brexit-effects", ("effectsNHSRetroW27",),
         by_code({1: ("Brexit has made the NHS much worse.", "The NHS is much worse off because of Brexit.", "Brexit has done the NHS a lot of harm."), 2: ("Brexit has made the NHS worse.", "The NHS is worse off because of Brexit.", "Brexit has done the NHS harm."),
                  3: ("Brexit hasn't made much difference to the NHS.", "The NHS is about the same as it was before Brexit.", "Brexit has made little difference to the NHS either way."),
                  4: ("Brexit has been good for the NHS.", "The NHS is better off because of Brexit.", "Brexit has done the NHS good."), 5: ("Brexit has been very good for the NHS.", "The NHS is much better off because of Brexit.", "Brexit has done the NHS a lot of good.")}), weight=0.6),
    # The wave-27 questionnaire (effectsEURetro grid) asks whether immigration is higher or
    # lower because the UK left the EU; the SPSS value labels ("Much worse ... Much better")
    # are a copy-paste error from the neighbouring better/worse grid.
    Item("brexitImmigration", "brexit-effects", ("effectsEUImmigrationRetroW27",),
         by_code({1: ("Brexit has made immigration to Britain much lower.", "Immigration is much lower because of Brexit.", "Brexit has cut immigration a great deal."),
                  2: ("Brexit has made immigration to Britain lower.", "Immigration is lower because of Brexit.", "Brexit has brought immigration down."),
                  3: ("Brexit hasn't made much difference to immigration levels.", "Immigration is about the same as it was before Brexit.", "Brexit has left immigration levels about the same."),
                  4: ("Brexit has made immigration to Britain higher.", "Immigration is higher because of Brexit.", "Brexit has pushed immigration up."),
                  5: ("Brexit has made immigration to Britain much higher.", "Immigration is much higher because of Brexit.", "Brexit has pushed immigration up a great deal.")}), weight=0.6),
    Item("brexitVoice", "brexit-effects", ("euLeaveVoiceRetroW27",),
         by_code({1: ("Brexit has left Britain with far less clout in the world.", "Britain has much less of a voice in the world since Brexit.", "Brexit has badly weakened Britain's voice in the world."), 2: ("Brexit has left Britain with less clout in the world.", "Britain has less of a voice in the world since Brexit.", "Brexit has weakened Britain's voice in the world."),
                  3: ("Brexit hasn't made much difference to Britain's influence in the world.", "Britain has about the same influence in the world as before Brexit.", "Brexit has made little difference to Britain's clout either way."),
                  4: ("Brexit has given Britain more clout in the world.", "Britain has more of a voice in the world since Brexit.", "Brexit has strengthened Britain's voice in the world."), 5: ("Brexit has given Britain far more clout in the world.", "Britain has much more of a voice in the world since Brexit.", "Brexit has greatly strengthened Britain's voice in the world.")}), weight=0.6),
    Item("brexitFinance", "brexit-effects", ("effectsEUFinanceRetroW27",),
         by_code({1: ("Brexit has left me personally much worse off.", "My own finances are much worse because of Brexit.", "Brexit has hit my own finances hard."), 2: ("Brexit has left me personally worse off.", "My own finances are worse because of Brexit.", "Brexit has left my own finances worse off."),
                  3: ("Brexit hasn't made any difference to my own finances.", "My own finances are neither better nor worse for Brexit.", "Brexit has made no difference to my own finances."), 4: ("Brexit has left me personally better off.", "My own finances are better because of Brexit.", "Brexit has left my own finances better off."),
                  5: ("Brexit has left me personally much better off.", "My own finances are much better because of Brexit.", "Brexit has done my own finances a lot of good.")}), weight=0.6),
    Item("handleEUPost", "brexit-effects", ("handleEUPostW27",),
         by_code({1: ("The government made a complete mess of taking Britain out of the EU.", "The government handled Britain's exit from the EU very badly.", "Britain's exit from the EU was handled terribly by the government."), 2: ("The government made a mess of taking Britain out of the EU.", "The government handled Britain's exit from the EU badly.", "Britain's exit from the EU was handled badly by the government."),
                  3: ("The government handled leaving the EU neither well nor badly.", "The government's handling of Brexit was neither good nor bad.", "The government took Britain out of the EU neither well nor badly, as I see it."),
                  4: ("The government handled leaving the EU well.", "The government did a good job of taking Britain out of the EU.", "Britain's exit from the EU was handled well by the government."), 5: ("The government handled leaving the EU very well.", "The government did a very good job of taking Britain out of the EU.", "Britain's exit from the EU was handled very well by the government.")}), weight=0.5),
    Item("euRefDoOver", "europe", ("euRefDoOverW29",),
         by_code({1: ("I'd like another referendum on EU membership.", "There should be another referendum on EU membership.", "I want another EU referendum."), 0: ("I don't want another EU referendum.", "There shouldn't be another referendum on EU membership.", "I'm against holding another EU referendum.")}), weight=0.7),
    Item("euID", "europe", ("euIDW27", "euIDW25"),
         by_code({1: ("I still think of myself as a Remainer.", "I'd still call myself a Remainer.", "I still see myself as a Remainer."), 2: ("I still think of myself as a Leaver.", "I'd still call myself a Leaver.", "I still see myself as a Leaver."),
                  3: ("I don't think of myself as a Leaver or a Remainer.", "I don't see myself as either a Leaver or a Remainer.", "I'm neither a Leaver nor a Remainer, as far as I'm concerned.")}), weight=0.8),
    # America, free speech and the wider world
    Item("usTies", "usa", ("selfUSTie1W30",),
         scale11(("Britain should get much closer to the United States economically.", "Britain should build much closer economic ties with the United States.", "I'd get Britain much closer to the US economically."), ("I'd like closer economic ties with the US.", "Britain should get a bit closer to the United States economically.", "I'd build closer economic ties with the United States."),
                 ("I'd keep the United States at arm's length.", "Britain should keep some distance from the United States economically.", "I'd protect Britain's independence from the US a bit more."), ("Britain must protect its independence from the United States.", "Britain should put its independence from the United States first.", "Protecting Britain's independence from the US matters more than close ties."))),
    Item("freeSpeechRacistTV", "free-speech", ("freeSpeechRacistTVW30",),
         by_code({1: ("Someone who thinks white people are superior should never be given airtime on TV.", "A white supremacist should definitely not be allowed on TV to put their case.", "There's no way someone who thinks white people are superior should get airtime on TV."),
                  2: ("A white supremacist probably shouldn't be given airtime on TV.", "Someone who thinks white people are superior probably shouldn't be allowed on TV.", "I'd probably not let a white supremacist on TV to put their case."),
                  3: ("Even a white supremacist should probably be allowed on TV to put their case.", "Someone who thinks white people are superior should probably be allowed on TV to put their case.", "I'd probably let even a white supremacist on TV to put their case."),
                  4: ("Even a white supremacist should be allowed on TV to put their case - that's free speech.", "Someone who thinks white people are superior should definitely be allowed on TV to put their case.", "Free speech means even a white supremacist should be allowed on TV to put their case.")}), weight=0.6),
    Item("freeSpeechIslamistTV", "free-speech", ("freeSpeechIslamistTVW30",),
         by_code({1: ("A preacher who preaches hatred of the West should never be given airtime on TV.", "A preacher of hatred of the West should definitely not be allowed on TV to put their case.", "There's no way a preacher who preaches hatred of the West should get airtime on TV."),
                  2: ("A preacher who preaches hatred of the West probably shouldn't be on TV.", "I'd probably not let a preacher who preaches hatred of the West on TV.", "A preacher of hatred of the West probably shouldn't be given airtime on TV."),
                  3: ("Even a preacher who preaches hatred of the West should probably be allowed on TV.", "I'd probably let even a preacher who preaches hatred of the West on TV to put their case.", "A preacher of hatred of the West should probably still be allowed on TV to put their case."),
                  4: ("Even a preacher who preaches hatred of the West should be allowed on TV - that's free speech.", "A preacher who preaches hatred of the West should definitely be allowed on TV to put their case.", "Free speech means even a preacher of hatred of the West should be allowed on TV.")}), weight=0.6),
    Item("freeSpeechLeaderElection", "free-speech", ("freeSpeechLeaderElectionW30",),
         by_code({1: ("Someone who wants to scrap elections for a strongman should never be allowed to stand for office.", "Anyone who wants to scrap elections in favour of a strongman should definitely not be allowed to stand.", "There's no way someone who wants to do away with elections should be allowed to stand for office."),
                  2: ("Someone who wants to scrap elections probably shouldn't be allowed to stand for office.", "I'd probably not let someone who wants to scrap elections stand for office.", "Anyone who wants to do away with elections probably shouldn't be allowed to stand."),
                  3: ("Even someone who wants to scrap elections should probably be allowed to stand.", "I'd probably let even someone who wants to scrap elections stand for office.", "Someone who wants to do away with elections should probably still be allowed to stand."),
                  4: ("Even someone who wants to scrap elections should be free to stand for office.", "Someone who wants to scrap elections should definitely be allowed to stand for office.", "Anyone who wants to do away with elections should still be free to stand for office.")}), weight=0.5),
    # Local area
    Item("amenities", "local-area", ("amenitiesW21",),
         by_code({5: ("My area is very well served by shops, schools and services.", "Shops, schools and services round here are very good.", "Where I live is very well served for shops, schools and services."), 4: ("My area is fairly well served by shops, schools and services.", "Shops, schools and services round here are fairly good.", "Where I live is fairly well served for shops, schools and services."),
                  2: ("My area is fairly poorly served by shops, schools and services.", "Shops, schools and services round here are fairly poor.", "Where I live is fairly badly served for shops, schools and services."), 1: ("My area is very poorly served by shops, schools and services.", "Shops, schools and services round here are very poor.", "Where I live is very badly served for shops, schools and services.")}),
         weight=0.6),
    Item("mapRepresent", "local-voice", ("mapRepresentW21",),
         by_code({1: ("Nobody in national government listens to people round here.", "National government doesn't listen to people round here at all.", "People round here aren't listened to at all by national government."), 2: ("National government doesn't listen much to people round here.", "People round here aren't listened to much by national government.", "National government doesn't pay much attention to people round here."),
                  3: ("National government listens to people round here a bit.", "People round here get listened to a bit by national government.", "National government pays a bit of attention to people round here."), 4: ("National government listens to people round here a great deal.", "People round here get listened to a great deal by national government.", "National government pays a great deal of attention to people round here.")}),
         weight=0.6),
    Item("areaRichPoor", "local-area", ("areaRichPoorW21",), max_valid=101,
         phrase=lambda a: (("My area is among the poorest in the country.", "Where I live is one of the poorest areas in the country.", "My area is about as poor as it gets in this country.") if a <= 25 else ("My area is poorer than most.", "Where I live is poorer than most places.", "My area is on the poorer side compared with most of the country.") if a <= 40
                           else ("My area is better off than most.", "Where I live is better off than most places.", "My area is on the wealthier side compared with most of the country.") if 60 <= a < 75 else ("My area is one of the richest in the country.", "Where I live is among the richest areas in the country.", "My area is about as well off as anywhere in the country.") if a >= 75 else None),
         weight=0.6),
    Item("areaSpirit", "local-area", ("statusAreaSpiritW30", "statusAreaSpiritW25"),
         agree5(("There's no community spirit round here any more.", "Community spirit where I live is completely gone.", "My area has no sense of community at all."), ("There's a lack of community spirit where I live.", "My area is short on community spirit.", "There isn't much community spirit round here."),
                ("There's a decent community spirit where I live.", "My area has a fair bit of community spirit.", "There's a reasonable sense of community round here."), ("Community spirit round here is strong.", "There's a real sense of community where I live.", "We've got plenty of community spirit round here.")), weight=0.6),
    Item("areaCrime", "local-area", ("statusAreaCrimeW30", "statusAreaCrimeW25"),
         agree5(("There's a lot of crime round where I live.", "Crime is a serious problem in my area.", "My area has a real crime problem."), ("Crime is a real problem in my area.", "There's a crime problem where I live.", "Crime is an issue round here."),
                ("Crime isn't much of a problem where I live.", "There isn't much crime round here.", "Crime isn't really an issue in my area."), ("There's hardly any crime round here.", "Crime is no problem at all where I live.", "We get next to no crime in my area.")), weight=0.6),
    Item("areaShops", "local-area", ("statusAreaShopsW30", "statusAreaShopsW25"),
         agree5(("My area is full of interesting restaurants, bars and shops.", "Where I live has loads of interesting restaurants, bars and shops.", "There are plenty of great restaurants, bars and shops round here."), ("There are good restaurants, bars and shops round here.", "My area has some interesting restaurants, bars and shops.", "Where I live has decent restaurants, bars and shops."),
                ("There's not much in the way of restaurants, bars and shops round here.", "My area doesn't have many interesting restaurants, bars or shops.", "Where I live is a bit short of decent restaurants, bars and shops."),
                ("There's nowhere worth going round here - no decent bars, shops or restaurants.", "My area has no interesting restaurants, bars or shops at all.", "Where I live, there's nothing in the way of decent bars, shops or restaurants.")), weight=0.5),
    # Scotland and Wales
    Item("scotRefID", "independence", ("scotRefIDW27",),
         by_code({1: ("I'm firmly on the Yes side of the independence debate.", "I'm squarely on the Yes side of the independence debate.", "When it comes to independence, I'm a Yes supporter."), 2: ("I'm on the No side of the independence debate.", "When it comes to independence, I'm a No supporter.", "I see myself as being on the No side of the independence debate."),
                  3: ("I don't feel on either side of the independence debate.", "I'm not on either side of the independence debate.", "I don't see myself as a Yes or a No on independence.")}), nations=(2,), weight=0.8),
    Item("referendumSettled", "independence", ("referendumSettledW29", "referendumSettledW27"),
         by_code({1: ("There should be another independence referendum within ten years.", "Another independence referendum should happen within the next ten years.", "I want another independence referendum within ten years."),
                  0: ("There shouldn't be another independence referendum for at least ten years.", "Another independence referendum shouldn't happen for at least ten years.", "I don't want another independence referendum within the next ten years.")}), nations=(2,), weight=0.8),
    Item("sovereignty", "independence", ("sovereignty1W29",),
         agree5(("People in Scotland, and nobody else, should have the final say on how Scotland is governed.", "Nobody but the people in Scotland should have the final say on how Scotland is governed.", "How Scotland is governed should be decided by people in Scotland alone, and nobody else."),
                ("People in Scotland should have the final say on how Scotland is governed.", "How Scotland is governed should be up to the people in Scotland.", "The final say on how Scotland is governed should rest with people in Scotland."),
                ("I don't think Scotland alone should decide how it's governed.", "People in Scotland shouldn't be the only ones with a say in how Scotland is governed.", "I don't agree that the final say on how Scotland is governed belongs to Scotland alone."),
                ("Scotland shouldn't decide alone how it's governed - we're part of the UK.", "As part of the UK, Scotland shouldn't have the final say on how it's governed on its own.", "I strongly disagree that people in Scotland alone should decide how Scotland is governed.")), nations=(2,), weight=0.6),
    Item("scotIndepEconomy", "independence", ("scotIndepEconomyW25", "scotIndepEconomyW23"),
         by_code({5: ("Scotland's economy would certainly be worse off under independence.", "I've no doubt independence would leave Scotland's economy worse off.", "Scotland's economy would definitely suffer if we went independent."), 4: ("Scotland's economy would probably be worse off under independence.", "I think independence would probably leave Scotland's economy worse off.", "Chances are Scotland's economy would suffer if we went independent."),
                  2: ("I don't think independence would hurt Scotland's economy.", "Scotland's economy probably wouldn't be any worse off under independence.", "I doubt independence would do Scotland's economy any harm."), 1: ("Independence wouldn't hurt Scotland's economy at all.", "There's no chance independence would do Scotland's economy any harm.", "I really can't see independence doing Scotland's economy any harm at all.")}),
         nations=(2,), weight=0.6),
    Item("scotIndepBetterOff", "independence", ("scotIndepMeBetterOffW25", "scotIndepMeBetterOffW23"),
         by_code({5: ("I'd definitely be better off if Scotland were independent.", "I've no doubt I'd be better off personally if Scotland went independent.", "Independence would certainly leave me better off."), 4: ("I'd probably be better off if Scotland were independent.", "I reckon independence would probably leave me personally better off.", "Chances are I'd be better off under Scottish independence."),
                  2: ("I probably wouldn't be better off under independence.", "I doubt independence would leave me personally any better off.", "I can't see myself being better off if Scotland went independent."), 1: ("I'd be worse off if Scotland went independent.", "Personally, I'd be worse off under Scottish independence.", "Personally, I'd lose out if Scotland went independent.")}),
         nations=(2,), weight=0.6),
    Item("happyScotIndep", "independence", ("happyScotIndepResultW21",),
         scale11(("I'd be gutted if Scotland left the UK.", "It would break my heart to see Scotland leave the UK.", "I'd be absolutely devastated if Scotland left the UK."), ("I'd be disappointed if Scotland left the UK.", "I'd be sorry to see Scotland leave the UK.", "It'd be a shame if Scotland ended up leaving the UK."),
                 ("I'd be fairly happy to see Scotland go independent.", "I'd be quite pleased if Scotland became independent.", "I'd be reasonably happy if Scotland went independent."), ("I'd be delighted to see Scotland become independent.", "I'd be over the moon if Scotland became independent.", "I'd be thrilled to bits if Scotland went independent.")), weight=0.5),
    Item("scotDevoMax", "devolution", ("scotDevoMaxW21",),
         by_code({5: ("Holyrood should have many more powers.", "The Scottish Parliament should have a lot more powers than it does now.", "I'd hand Holyrood many more powers."), 4: ("Holyrood should have some more powers.", "I'd give the Scottish Parliament a few more powers.", "Holyrood could do with some more powers than it has now."), 3: ("Holyrood's powers are about right.", "The powers Holyrood has now are about right.", "I'd say the Scottish Parliament's powers are about right as they are."),
                  2: ("Holyrood should have fewer powers.", "The Scottish Parliament should have fewer powers than it does now.", "I'd take some powers away from Holyrood."), 1: ("Holyrood should have far fewer powers.", "The Scottish Parliament should have many fewer powers than it does now.", "I'd strip Holyrood of a great many of its powers.")}), nations=(2,), weight=0.8),
    Item("devoPrefWales", "devolution", ("devoPrefWalesW27", "devoPrefWalesW21"),
         by_code({1: ("Wales shouldn't have a devolved government at all.", "There should be no devolved government in Wales.", "I'd scrap devolution in Wales altogether."), 2: ("The Senedd should have fewer powers.", "I'd take some powers away from the Senedd.", "The Welsh Parliament should have fewer powers than it does now."),
                  3: ("I'd leave Welsh devolution as it is.", "I'd keep Welsh devolution just as it is now.", "I'd leave things as they are with the Senedd."), 4: ("The Senedd should have more powers.", "I'd give the Senedd more powers.", "The Welsh Parliament should have more powers than it does now."), 5: ("Wales should be independent.", "I'd like to see Wales become an independent country.", "Wales should go independent.")}),
         nations=(3,), weight=1.0),

    # ------------------------------------------------------------------
    # What they actually did: the May 2026 elections and the 2024 general election
    Item("localVote", "recent-vote", (), custom=local_vote, nations=(1,), weight=1.2),
    Item("holyroodVote", "recent-vote", (), custom=holyrood_vote, nations=(2,), weight=1.6),
    Item("seneddVote", "recent-vote", (), custom=senedd_vote, nations=(3,), weight=1.6),
    Item("turnoutLikely", "turnout", ("turnoutUKGeneralW31",),
         by_code({1: ("If there were an election tomorrow, I very probably wouldn't vote.", "It's very unlikely I'd vote if there were a general election tomorrow.", "If a general election were held tomorrow, I almost certainly wouldn't turn out."),
                  2: ("If there were an election tomorrow, I probably wouldn't bother voting.", "I probably wouldn't turn out if there were a general election tomorrow.", "If a general election were held tomorrow, I doubt I'd vote."),
                  3: ("If there were an election tomorrow, I'm not sure I'd bother voting.", "If a general election were held tomorrow, I'm not sure I'd bother turning out.", "Honestly, if there were an election tomorrow I'm not sure I'd bother voting.")}), weight=0.6, fallback=False),
    # Parties: likes, bonds, unity, who they look after
    Item("regionFairShare", "fair-share", ("regionFairShareW31", "regionFairShareW21"),
         fair_share5("My region", "of government spending"), nations=(1,), weight=0.4),
    # Attitudes to gender (wave 27)
    Item("benevolentSexism", "gender-attitudes", ("benevolentSexism1W27",),
         agree5(("Women should always be cherished and protected by men.", "I strongly believe men should cherish and protect women.", "Men should always cherish and protect women, no question."), ("Women should be cherished and protected by men.", "I think men should cherish and protect women.", "I agree that men ought to cherish and protect women."),
                ("I don't think women need men to cherish and protect them.", "I disagree that women should be cherished and protected by men.", "Women don't need cherishing and protecting by men, as far as I'm concerned."), ("The idea that women need protecting by men is outdated.", "I strongly disagree that women need men to cherish and protect them.", "Women don't need men to cherish and protect them - that's an old-fashioned idea.")),
         weight=0.4),
    Item("hostileSexism", "gender-attitudes", ("hostileSexism3W27",),
         agree5(("Most women really do take innocent remarks as sexist.", "I strongly agree that most women take innocent remarks as sexist.", "There's no doubt most women read sexism into perfectly innocent remarks."), ("Most women take innocent remarks as sexist.", "I think most women read sexism into innocent remarks.", "In my view, most women treat innocent remarks or acts as sexist."),
                ("I don't think women go round taking innocent remarks as sexist.", "I disagree that most women take innocent remarks or acts as sexist.", "I don't believe most women read sexism into innocent remarks."), ("Women don't take innocent remarks as sexist - that's a myth.", "I strongly disagree that most women take innocent remarks as sexist.", "The idea that most women see innocent remarks as sexist is nonsense.")),
         weight=0.4),

    # --- added after the wave-20+ audit (docs/unused-questions.md) ---
    Item("brexitEcon", "economy-blame", (), custom=impact_item(("brexitEconImpactW31", "brexitEconImpactW30"),
         ("Brexit has done the economy a lot of damage.", "Brexit has had a big negative impact on Britain's economy.", "Brexit has really hurt the economy."), ("Brexit has done the economy some damage.", "Brexit has had a fairly negative impact on Britain's economy.", "Brexit has hurt the economy somewhat."),
         ("Brexit has been good for the economy.", "Brexit has had a positive impact on Britain's economy.", "Brexit has helped the economy."), ("Brexit has been very good for the economy.", "Brexit has had a big positive impact on Britain's economy.", "Brexit has done the economy a lot of good."),
         ("Brexit has had mixed effects on the economy.", "Brexit has done the economy about as much good as harm.", "Brexit hasn't had much impact on the economy either way.")), weight=0.8),
    Item("worldEcon", "economy-blame", (), custom=impact_item(("globalEconomyEconImpactW31", "globalEconomyEconImpactW30"),
         ("The state of the world economy has hit Britain hard.", "The global economy has had a big negative impact on Britain.", "Britain has been badly hurt by the state of the global economy."), ("The state of the world economy has hurt Britain a bit.", "The global economy has had a fairly negative impact on Britain.", "Britain has suffered somewhat from the state of the global economy."),
         ("The world economy has been good for Britain.", "The global economy has had a positive impact on Britain.", "Britain has done well out of the state of the world economy."), ("The world economy has been very good for Britain.", "The global economy has had a big positive impact on Britain.", "Britain has done really well out of the state of the world economy."),
         ("The state of the world economy has cut both ways for Britain.", "The global economy has done Britain about as much good as harm.", "The world economy hasn't had much impact on Britain either way.")), weight=0.5),
    Item("conflictEcon", "economy-blame", (), custom=impact_item(("conflictEconImpactW31",),
         ("Global conflicts like Iran and Ukraine have hit the economy hard.", "Conflicts around the world, like Iran and Ukraine, have had a big negative impact on our economy.", "The economy has been badly hurt by global conflicts like Iran and Ukraine."), ("Global conflicts like Iran and Ukraine have hurt the economy a bit.", "Conflicts around the world, like Iran and Ukraine, have had a fairly negative impact on our economy.", "The economy has suffered somewhat because of global conflicts like Iran and Ukraine."),
         ("Global conflicts like Iran and Ukraine have been good for the economy.", "Conflicts around the world, like Iran and Ukraine, have had a positive impact on our economy.", "The economy has benefited from global conflicts like Iran and Ukraine."), ("Global conflicts like Iran and Ukraine have been very good for the economy.", "Conflicts around the world, like Iran and Ukraine, have had a big positive impact on our economy.", "The economy has benefited a great deal from global conflicts like Iran and Ukraine."),
         ("Global conflicts like Iran and Ukraine haven't had much impact on our economy either way.", "Conflicts around the world, like Iran and Ukraine, have done our economy about as much good as harm.", "Global conflicts like Iran and Ukraine have had mixed effects on our economy.")), weight=0.7),
    Item("govtEconImpact", "economy-blame", (), custom=impact_item(("ukGovtEconImpactW31", "ukGovtEconImpactW30"),
         ("The UK government has done the economy a lot of damage.", "The current UK government has had a big negative impact on the economy.", "The UK government has really hurt the economy."), ("The UK government has done the economy some damage.", "The current UK government has had a fairly negative impact on the economy.", "The UK government has hurt the economy somewhat."),
         ("The UK government has been good for the economy.", "The current UK government has had a positive impact on the economy.", "The UK government has helped the economy."), ("The UK government has been very good for the economy.", "The current UK government has had a big positive impact on the economy.", "The UK government has done the economy a lot of good."),
         ("The UK government has had mixed effects on the economy.", "The current UK government has done the economy about as much good as harm.", "The UK government hasn't had much impact on the economy either way.")), weight=0.7),
    Item("lastGovtEconImpact", "economy-blame", (), custom=impact_item(("ukLastGovtEconImpactW31", "ukLastGovtEconImpactW30"),
         ("The last UK government did the economy a lot of damage.", "The previous UK government had a big negative impact on the economy.", "The last UK government really hurt the economy."), ("The last UK government did the economy some damage.", "The previous UK government had a fairly negative impact on the economy.", "The last UK government hurt the economy somewhat."),
         ("The last UK government was good for the economy.", "The previous UK government had a positive impact on the economy.", "The last UK government helped the economy."), ("The last UK government was very good for the economy.", "The previous UK government had a big positive impact on the economy.", "The last UK government did the economy a lot of good."),
         ("The last UK government had mixed effects on the economy.", "The previous UK government did the economy about as much good as harm.", "The last UK government didn't have much impact on the economy either way.")), weight=0.6),
    Item("brexitEconScot", "economy-blame", (), custom=impact_item(("brexitEconImpactScotW31", "brexitEconImpactScotW30"),
         ("Brexit has done Scotland's economy a lot of damage.", "Brexit has had a big negative impact on the Scottish economy.", "Brexit has really hurt Scotland's economy."), ("Brexit has done Scotland's economy some damage.", "Brexit has had a fairly negative impact on the Scottish economy.", "Brexit has hurt Scotland's economy somewhat."),
         ("Brexit has been good for Scotland's economy.", "Brexit has had a positive impact on the Scottish economy.", "Brexit has helped Scotland's economy."), ("Brexit has been very good for Scotland's economy.", "Brexit has had a big positive impact on the Scottish economy.", "Brexit has done Scotland's economy a lot of good."),
         ("Brexit has had mixed effects on Scotland's economy.", "Brexit has done the Scottish economy about as much good as harm.", "Brexit hasn't had much impact on Scotland's economy either way.")), nations=(2,), weight=0.6),
    Item("scotGovtEcon", "scottish-government", (), custom=impact_item(("scotGovtEconImpactScotW31", "scotGovtEconImpactScotW30"),
         ("The Scottish Government has done Scotland's economy a lot of damage.", "The Scottish Government has had a big negative impact on Scotland's economy.", "The Scottish Government has really hurt the Scottish economy."), ("The Scottish Government has done Scotland's economy some damage.", "The Scottish Government has had a fairly negative impact on Scotland's economy.", "The Scottish Government has hurt the Scottish economy somewhat."),
         ("The Scottish Government has been good for Scotland's economy.", "The Scottish Government has had a positive impact on Scotland's economy.", "The Scottish Government has helped the Scottish economy."), ("The Scottish Government has been very good for Scotland's economy.", "The Scottish Government has had a big positive impact on Scotland's economy.", "The Scottish Government has done the Scottish economy a lot of good."),
         ("The Scottish Government has had mixed effects on Scotland's economy.", "The Scottish Government has done Scotland's economy about as much good as harm.", "The Scottish Government hasn't had much impact on the Scottish economy either way.")), nations=(2,), weight=0.7),
    Item("conflictEconScot", "economy-blame", (), custom=impact_item(("conflictEconImpactScotW31",),
         ("Global conflicts like Iran and Ukraine have hit Scotland's economy hard.", "Conflicts around the world, like Iran and Ukraine, have had a big negative impact on Scotland's economy.", "Scotland's economy has been badly hurt by global conflicts like Iran and Ukraine."), ("Global conflicts like Iran and Ukraine have hurt Scotland's economy a bit.", "Conflicts around the world, like Iran and Ukraine, have had a fairly negative impact on Scotland's economy.", "Scotland's economy has suffered somewhat because of global conflicts like Iran and Ukraine."),
         ("Global conflicts like Iran and Ukraine have been good for Scotland's economy.", "Conflicts around the world, like Iran and Ukraine, have had a positive impact on Scotland's economy.", "Scotland's economy has benefited from global conflicts like Iran and Ukraine."), ("Global conflicts like Iran and Ukraine have been very good for Scotland's economy.", "Conflicts around the world, like Iran and Ukraine, have had a big positive impact on Scotland's economy.", "Scotland's economy has benefited a great deal from global conflicts like Iran and Ukraine."),
         ("Global conflicts like Iran and Ukraine haven't had much impact on Scotland's economy either way.", "Conflicts around the world, like Iran and Ukraine, have done Scotland's economy about as much good as harm.", "Global conflicts like Iran and Ukraine have had mixed effects on Scotland's economy.")), nations=(2,), weight=0.5),
    Item("conflictEconWales", "economy-blame", (), custom=impact_item(("conflictEconImpactWalesW31",),
         ("Global conflicts like Iran and Ukraine have hit Wales's economy hard.", "Conflicts around the world, like Iran and Ukraine, have had a big negative impact on the Welsh economy.", "Wales's economy has been badly hurt by global conflicts like Iran and Ukraine."), ("Global conflicts like Iran and Ukraine have hurt Wales's economy a bit.", "Conflicts around the world, like Iran and Ukraine, have had a fairly negative impact on the Welsh economy.", "Wales's economy has suffered somewhat because of global conflicts like Iran and Ukraine."),
         ("Global conflicts like Iran and Ukraine have been good for Wales's economy.", "Conflicts around the world, like Iran and Ukraine, have had a positive impact on the Welsh economy.", "Wales's economy has benefited from global conflicts like Iran and Ukraine."), ("Global conflicts like Iran and Ukraine have been very good for Wales's economy.", "Conflicts around the world, like Iran and Ukraine, have had a big positive impact on the Welsh economy.", "Wales's economy has benefited a great deal from global conflicts like Iran and Ukraine."),
         ("Global conflicts like Iran and Ukraine haven't had much impact on Wales's economy either way.", "Conflicts around the world, like Iran and Ukraine, have done the Welsh economy about as much good as harm.", "Global conflicts like Iran and Ukraine have had mixed effects on Wales's economy.")), nations=(3,), weight=0.5),
    Item("brexitEconWales", "economy-blame", (), custom=impact_item(("brexitEconImpactWalesW31", "brexitEconImpactWalesW30"),
         ("Brexit has done Wales's economy a lot of damage.", "Brexit has had a big negative impact on the Welsh economy.", "Brexit has really hurt Wales's economy."), ("Brexit has done Wales's economy some damage.", "Brexit has had a fairly negative impact on the Welsh economy.", "Brexit has hurt Wales's economy somewhat."),
         ("Brexit has been good for Wales's economy.", "Brexit has had a positive impact on the Welsh economy.", "Brexit has helped Wales's economy."), ("Brexit has been very good for Wales's economy.", "Brexit has had a big positive impact on the Welsh economy.", "Brexit has done Wales's economy a lot of good."),
         ("Brexit has had mixed effects on Wales's economy.", "Brexit has done the Welsh economy about as much good as harm.", "Brexit hasn't had much impact on Wales's economy either way.")), nations=(3,), weight=0.6),
    Item("welshGovtEcon", "welsh-government", (), custom=impact_item(("welshGovtEconImpactWalesW31", "welshGovtEconImpactWalesW30"),
         ("The Welsh Government has done Wales's economy a lot of damage.", "The Welsh Government has had a big negative impact on Wales's economy.", "The Welsh Government has really hurt the Welsh economy."), ("The Welsh Government has done Wales's economy some damage.", "The Welsh Government has had a fairly negative impact on Wales's economy.", "The Welsh Government has hurt the Welsh economy somewhat."),
         ("The Welsh Government has been good for Wales's economy.", "The Welsh Government has had a positive impact on Wales's economy.", "The Welsh Government has helped the Welsh economy."), ("The Welsh Government has been very good for Wales's economy.", "The Welsh Government has had a big positive impact on Wales's economy.", "The Welsh Government has done the Welsh economy a lot of good."),
         ("The Welsh Government has had mixed effects on Wales's economy.", "The Welsh Government has done Wales's economy about as much good as harm.", "The Welsh Government hasn't had much impact on the Welsh economy either way.")), nations=(3,), weight=0.7),
    Item("freeSpeechRacistElection", "free-speech", ("freeSpeechRacistElectionW30",),
         by_code({1: ("A white supremacist should never be allowed to stand for election.", "I'd never let a white supremacist stand as a candidate in an election.", "There's no way a white supremacist should be allowed to stand for election."), 2: ("A white supremacist probably shouldn't be allowed to stand for election.", "I probably wouldn't let a white supremacist stand as a candidate in an election.", "On balance, a white supremacist shouldn't be allowed to stand for election."),
                  3: ("Even a white supremacist should probably be allowed to stand for election.", "I'd probably let even a white supremacist stand as a candidate in an election.", "On balance, even a white supremacist should be allowed to stand for election."), 4: ("Even a white supremacist should be free to stand for election.", "Even a white supremacist should definitely be allowed to stand as a candidate.", "A white supremacist has every right to stand for election, as far as I'm concerned.")}), weight=0.4),
    Item("freeSpeechRacistSpeech", "free-speech", ("freeSpeechRacistSpeechW30",),
         by_code({1: ("A white supremacist should never be allowed to hold a public meeting round here.", "I'd never let a white supremacist make a speech in my community.", "There's no way a white supremacist should be allowed to give a speech round here."), 2: ("A white supremacist probably shouldn't be allowed to speak in public round here.", "I probably wouldn't let a white supremacist make a speech in my community.", "On balance, a white supremacist shouldn't be allowed to give a speech round here."),
                  3: ("Even a white supremacist should probably be allowed to speak in public round here.", "I'd probably let even a white supremacist make a speech in my community.", "On balance, even a white supremacist should be allowed to give a speech round here."), 4: ("Even a white supremacist should be allowed to hold a public meeting round here.", "Even a white supremacist should definitely be allowed to make a speech in my community.", "A white supremacist has every right to give a speech round here, as far as I'm concerned.")}), weight=0.4),
    Item("freeSpeechRacistTeach", "free-speech", ("freeSpeechRacistTeachW30",),
         by_code({1: ("A white supremacist should never be allowed to teach in a school.", "I'd never let a white supremacist teach 15-year-olds in a school.", "There's no way a white supremacist should be allowed to teach in schools."), 2: ("A white supremacist probably shouldn't be allowed to teach in a school.", "I probably wouldn't let a white supremacist teach 15-year-olds in a school.", "On balance, a white supremacist shouldn't be allowed to teach in schools."),
                  3: ("Even a white supremacist should probably be allowed to teach in a school.", "I'd probably let even a white supremacist teach 15-year-olds in a school.", "On balance, even a white supremacist should be allowed to teach in schools."), 4: ("Even a white supremacist should be allowed to teach in a school.", "Even a white supremacist should definitely be allowed to teach 15-year-olds in a school.", "A white supremacist has every right to teach in schools, as far as I'm concerned.")}), weight=0.4),
    Item("freeSpeechIslamistElection", "free-speech", ("freeSpeechIslamistElectionW30",),
         by_code({1: ("A preacher who preaches hatred of the West should never be allowed to stand for election.", "I'd never let a preacher who preaches hatred of the West stand as an election candidate.", "There's no way a preacher who preaches hatred of the West should be allowed to stand for election."), 2: ("A preacher who preaches hatred of the West probably shouldn't stand for election.", "I probably wouldn't let a preacher who preaches hatred of the West stand for election.", "On balance, a preacher who preaches hatred of the West shouldn't be allowed to stand for election."),
                  3: ("Even a preacher who preaches hatred of the West should probably be allowed to stand for election.", "I'd probably let even a preacher who preaches hatred of the West stand for election.", "On balance, even a preacher who preaches hatred of the West should be allowed to stand for election."), 4: ("Even a preacher who preaches hatred of the West should be free to stand for election.", "Even a preacher who preaches hatred of the West should definitely be allowed to stand for election.", "A preacher who preaches hatred of the West has every right to stand for election, as far as I'm concerned.")}), weight=0.4),
    Item("freeSpeechIslamistSpeech", "free-speech", ("freeSpeechIslamistSpeechW30",),
         by_code({1: ("A preacher who preaches hatred of the West should never be allowed to speak in public round here.", "I'd never let a preacher who preaches hatred of the West make a speech in my community.", "There's no way a preacher who preaches hatred of the West should be allowed to speak round here."), 2: ("A preacher who preaches hatred of the West probably shouldn't speak in public round here.", "I probably wouldn't let a preacher who preaches hatred of the West make a speech in my community.", "On balance, a preacher who preaches hatred of the West shouldn't be allowed to speak round here."),
                  3: ("Even a preacher who preaches hatred of the West should probably be allowed to speak round here.", "I'd probably let even a preacher who preaches hatred of the West make a speech in my community.", "On balance, even a preacher who preaches hatred of the West should be allowed to speak in public round here."), 4: ("Even a preacher who preaches hatred of the West should be allowed to speak round here.", "Even a preacher who preaches hatred of the West should definitely be allowed to make a speech round here.", "A preacher who preaches hatred of the West has every right to speak in my community, as far as I'm concerned.")}), weight=0.4),
    Item("freeSpeechIslamistTeach", "free-speech", ("freeSpeechIslamistTeachW30",),
         by_code({1: ("A preacher who preaches hatred of the West should never be allowed to teach in a school.", "I'd never let a preacher who preaches hatred of the West teach 15-year-olds in a school.", "There's no way a preacher who preaches hatred of the West should be allowed to teach in schools."), 2: ("A preacher who preaches hatred of the West probably shouldn't teach in a school.", "I probably wouldn't let a preacher who preaches hatred of the West teach 15-year-olds in a school.", "On balance, a preacher who preaches hatred of the West shouldn't be allowed to teach in schools."),
                  3: ("Even a preacher who preaches hatred of the West should probably be allowed to teach in a school.", "I'd probably let even a preacher who preaches hatred of the West teach 15-year-olds in a school.", "On balance, even a preacher who preaches hatred of the West should be allowed to teach in schools."), 4: ("Even a preacher who preaches hatred of the West should be allowed to teach in a school.", "Even a preacher who preaches hatred of the West should definitely be allowed to teach in schools.", "A preacher who preaches hatred of the West has every right to teach in a school, as far as I'm concerned.")}), weight=0.4),
    Item("freeSpeechLeaderSpeech", "free-speech", ("freeSpeechLeaderSpeechW30",),
         by_code({1: ("Someone who wants to scrap elections should never be allowed to speak in public round here.", "I'd never let someone who wants to do away with elections make a speech in my community.", "There's no way someone who wants to scrap elections should be allowed to speak round here."), 2: ("Someone who wants to scrap elections probably shouldn't speak in public round here.", "I probably wouldn't let someone who wants to do away with elections make a speech in my community.", "On balance, someone who wants to scrap elections shouldn't be allowed to speak round here."),
                  3: ("Even someone who wants to scrap elections should probably be allowed to speak round here.", "I'd probably let even someone who wants to do away with elections make a speech in my community.", "On balance, even someone who wants to scrap elections should be allowed to speak in public round here."), 4: ("Even someone who wants to scrap elections should be allowed to speak round here.", "Even someone who wants to do away with elections should definitely be allowed to make a speech round here.", "Someone who wants to scrap elections has every right to speak in my community, as far as I'm concerned.")}), weight=0.4),
    Item("freeSpeechLeaderTeach", "free-speech", ("freeSpeechLeaderTeachW30",),
         by_code({1: ("Someone who wants to scrap elections should never be allowed to teach in a school.", "I'd never let someone who wants to do away with elections teach 15-year-olds in a school.", "There's no way someone who wants to scrap elections should be allowed to teach in schools."), 2: ("Someone who wants to scrap elections probably shouldn't teach in a school.", "I probably wouldn't let someone who wants to do away with elections teach 15-year-olds in a school.", "On balance, someone who wants to scrap elections shouldn't be allowed to teach in schools."),
                  3: ("Even someone who wants to scrap elections should probably be allowed to teach in a school.", "I'd probably let even someone who wants to do away with elections teach 15-year-olds in a school.", "On balance, even someone who wants to scrap elections should be allowed to teach in schools."), 4: ("Even someone who wants to scrap elections should be allowed to teach in a school.", "Even someone who wants to do away with elections should definitely be allowed to teach in schools.", "Someone who wants to scrap elections has every right to teach in a school, as far as I'm concerned.")}), weight=0.4),
    Item("freeSpeechLeaderTV", "free-speech", ("freeSpeechLeaderTVW30",),
         by_code({1: ("Someone who wants to scrap elections should never be given airtime on TV.", "I'd never let someone who wants to do away with elections put their case on television.", "There's no way someone who wants to scrap elections should be interviewed on TV."), 2: ("Someone who wants to scrap elections probably shouldn't be on TV.", "I probably wouldn't let someone who wants to do away with elections put their case on television.", "On balance, someone who wants to scrap elections shouldn't be given TV interviews."),
                  3: ("Even someone who wants to scrap elections should probably be allowed on TV.", "I'd probably let even someone who wants to do away with elections put their case on television.", "On balance, even someone who wants to scrap elections should be allowed to give TV interviews."), 4: ("Even someone who wants to scrap elections should be allowed on TV - that's free speech.", "Even someone who wants to do away with elections should definitely be allowed to put their case on TV.", "Someone who wants to scrap elections has every right to give TV interviews, as far as I'm concerned.")}), weight=0.4),
    Item("efficacyEffort", "political-interest", ("efficacyTooMuchEffortW31", "efficacyTooMuchEffortW30"),
         agree5(("Being active in politics takes far too much time and effort.", "I strongly agree that being active in politics takes too much time and effort.", "It takes far too much time and effort to be involved in politics and public affairs."), ("Getting involved in politics takes too much time and effort.", "Being active in politics and public affairs takes more time and effort than it should.", "I think it takes too much time and effort to be active in politics."),
                ("Getting involved in politics isn't too much effort.", "I don't think being active in politics takes too much time and effort.", "Being involved in politics and public affairs isn't too demanding, in my view."), ("It's no great effort to get involved in politics.", "I strongly disagree that being active in politics takes too much time and effort.", "Being active in politics and public affairs really doesn't take much time or effort.")), weight=0.5),
    Item("asylum", "immigration", ("asylumMoreW26", "asylumMoreW25"),
         scale11(("Britain should take in far fewer asylum seekers.", "I'd let many fewer asylum seekers come and live in Britain.", "Britain should allow in a lot fewer asylum seekers than it does."), ("I'd let in fewer asylum seekers.", "Britain should allow fewer asylum seekers to come and live here.", "I'd have Britain take in somewhat fewer asylum seekers."),
                 ("I'd take in a few more asylum seekers.", "Britain should allow somewhat more asylum seekers to come and live here.", "I'd let a few more asylum seekers into Britain."), ("Britain should take in many more asylum seekers.", "I'd let many more asylum seekers come and live in Britain.", "Britain should allow in a lot more asylum seekers than it does.")), weight=0.7),
    Item("nonEuWorkers", "immigration", ("noneuMoreW26", "noneuMoreW25"),
         scale11(("Britain should let in far fewer workers from outside the EU.", "I'd let many fewer workers from outside the EU come and live in Britain.", "Britain should allow in a lot fewer non-EU workers than it does."), ("I'd let in fewer workers from outside the EU.", "Britain should allow fewer workers from outside the EU to come and live here.", "I'd have Britain take in somewhat fewer non-EU workers."),
                 ("I'd let in a few more workers from outside the EU.", "Britain should allow somewhat more workers from outside the EU to come and live here.", "I'd let a few more non-EU workers into Britain."), ("Britain should let in many more workers from outside the EU.", "I'd let many more workers from outside the EU come and live in Britain.", "Britain should allow in a lot more non-EU workers than it does.")), weight=0.5),
    Item("trains", "privatisation", ("nationalizeTrainsW26", "nationalizeTrainsW25"),
         by_code({1: ("The railways should be run entirely by the public sector.", "Train services should be entirely in public hands.", "I'd have the railways run wholly by the public sector."), 2: ("The railways should mostly be publicly run.", "Train services should be provided mostly by the public sector.", "I'd have the railways mainly in public hands."),
                  4: ("The railways should mostly be privately run.", "Train services should be provided mostly by the private sector.", "I'd have the railways mainly in private hands."), 5: ("The railways should be run entirely by private companies.", "Train services should be entirely in private hands.", "I'd have the railways run wholly by the private sector.")}), weight=0.7),
    Item("globalisation", "globalisation", ("globalGoodOverallW21", "globalGoodOverallW20"),
         by_code({1: ("Globalisation has been mainly bad for Britain.", "I think globalisation is mainly a bad thing.", "On the whole, globalisation has been a bad thing for Britain."), 2: ("Globalisation has done Britain more harm than good.", "Globalisation has been somewhat more of a bad thing than a good thing for Britain.", "On balance, globalisation has been a bit more of a bad thing than a good one for Britain."),
                  4: ("Globalisation has done Britain more good than harm.", "Globalisation has been somewhat more of a good thing than a bad thing for Britain.", "On balance, globalisation has been a bit more of a good thing than a bad one for Britain."), 5: ("Globalisation has been mainly good for Britain.", "I think globalisation is mainly a good thing.", "On the whole, globalisation has been a good thing for Britain.")}), weight=0.5),
    Item("fairElections", "elections", ("expectGoodConductGeneralW29", "expectGoodConductGeneralW27"),
         by_code({1: ("I'm confident our general elections are run fairly.", "I've every confidence that our general elections are conducted fairly.", "I'm sure general elections in this country are run fairly."), 2: ("I'm fairly confident our elections are run fairly.", "On the whole, I think our general elections are conducted fairly.", "I'm reasonably confident that general elections here are run fairly."),
                  4: ("I'm not convinced our elections are run fairly.", "I have my doubts about how fairly our general elections are conducted.", "I'm not that confident our general elections are run fairly."), 5: ("I don't believe our general elections are run fairly.", "I've no confidence that our general elections are conducted fairly.", "General elections in this country aren't run fairly, as far as I'm concerned.")}), weight=0.5),
    Item("voterIdDifficult", "voter-id", ("voterIDDifficultW25",),
         agree5(("Having to show ID makes voting a lot harder.", "I strongly agree that voter ID makes voting more difficult.", "Showing ID at the polling station makes voting much more difficult."), ("Having to show ID makes voting harder.", "I think voter ID makes voting more difficult.", "Showing ID at the polling station makes voting that bit more difficult."),
                ("Showing ID doesn't make voting any harder.", "I don't think voter ID makes voting more difficult.", "Having to show ID at the polling station isn't really a problem."), ("Showing ID at the polling station is no bother at all.", "I strongly disagree that voter ID makes voting more difficult.", "Having to show ID doesn't make voting one bit harder.")), weight=0.4),
    Item("voterIdFraud", "voter-id", ("voterIDFraudW25",),
         agree5(("Voter ID stops fraud.", "I strongly agree that voter ID prevents fraud.", "Having to show ID at the polling station definitely prevents fraud."), ("Voter ID helps stop fraud.", "I think voter ID prevents fraud.", "Having to show ID at the polling station helps prevent fraud."), ("Voter ID doesn't stop fraud.", "I don't think voter ID prevents fraud.", "Having to show ID at the polling station doesn't really prevent fraud."), ("Voter ID does nothing to stop fraud.", "I strongly disagree that voter ID prevents fraud.", "Having to show ID doesn't stop fraud in the slightest.")), weight=0.4),
    Item("populismWill", "populism", ("populism1W27", "populism1W26"),
         agree5(("MPs should follow the will of the people.", "MPs have to do what the people want.", "It's the job of MPs to follow the will of the people."), ("MPs should generally follow the will of the people.", "On the whole, MPs ought to follow what the people want.", "MPs should go along with the will of the people most of the time."),
                ("MPs shouldn't just follow the will of the people.", "I don't think MPs should simply do whatever the public wants.", "MPs shouldn't just go along with whatever the people want."), ("MPs are there to use their judgement, not just follow the will of the people.", "MPs are meant to use their own judgement rather than simply go along with what the public wants.", "I'd far rather MPs thought for themselves than just followed the will of the people.")), weight=0.6),
    Item("populismCitizen", "populism", ("populism4W27", "populism4W26"),
         agree5(("I'd much rather be represented by an ordinary citizen than a career politician.", "I'd far rather have an ordinary person representing me than a career politician.", "Give me an ordinary citizen over a career politician as my representative any day."), ("I'd rather be represented by an ordinary citizen than a career politician.", "I'd sooner have an ordinary person representing me than a career politician.", "I'd prefer to be represented by an ordinary member of the public rather than a career politician."),
                ("I'd rather be represented by a professional politician than an ordinary citizen.", "I'd sooner have a professional politician representing me than an ordinary member of the public.", "I prefer being represented by someone who does politics for a living rather than an ordinary citizen."), ("Give me a professional politician over an ordinary citizen any day.", "I'd far rather have a professional politician representing me than an ordinary citizen.", "I'd take a professional politician over an ordinary citizen as my representative every time.")), weight=0.6),
    Item("privateHealthEfficient", "private-healthcare", ("privateHospEfficientW26",),
         agree5(("Private companies run healthcare far more efficiently than the NHS.", "Private firms deliver healthcare a great deal more efficiently than the NHS.", "There's no doubt private companies are far more efficient at providing healthcare than the NHS."), ("Private companies provide healthcare more efficiently than the NHS.", "Private firms deliver healthcare more efficiently than the NHS does.", "I think healthcare is run more efficiently by private companies than by the NHS."),
                ("Private companies don't provide healthcare any more efficiently than the NHS.", "I don't think private firms deliver healthcare any more efficiently than the NHS does.", "Private companies aren't any more efficient at providing healthcare than the NHS."), ("The idea that private companies run healthcare better than the NHS is nonsense.", "I don't buy for a second that private companies deliver healthcare more efficiently than the NHS.", "It's rubbish to say private firms run healthcare more efficiently than the NHS.")), weight=0.6),
    Item("privateHealthTax", "private-healthcare", ("privateHospTaxW26",),
         agree5(("Private healthcare takes a lot of pressure off the taxpayer, so it benefits everyone.", "Private healthcare eases the burden on taxpayers enormously, so it's good for all of us.", "Everyone gains from private healthcare because it takes so much strain off the taxpayer."), ("Private healthcare takes pressure off the taxpayer, so it benefits everyone.", "Private healthcare eases the burden on taxpayers, and that's good for everyone.", "Because private healthcare reduces the strain on taxpayers, everyone benefits from it."),
                ("Private healthcare doesn't benefit everyone just because it eases the burden on taxpayers.", "I don't think private healthcare benefits everyone just because it takes some strain off taxpayers.", "Easing the burden on taxpayers doesn't mean private healthcare is good for everyone."), ("I don't accept that private healthcare helps everyone by easing the tax burden.", "I completely reject the idea that private healthcare benefits everyone by easing the burden on taxpayers.", "It's nonsense to say private healthcare helps us all because it takes the strain off taxpayers.")), weight=0.5),
    Item("sexismWomenAppreciate", "sexism", ("hostileSexism1W27",),
         agree5(("Most women don't appreciate all that men do for them.", "Most women just don't appreciate everything men do for them.", "Most women fail to appreciate all the things men do for them."), ("Most women don't fully appreciate what men do for them.", "Most women don't really appreciate everything men do for them.", "I think most women underappreciate what men do for them."),
                ("It's not true that women don't appreciate what men do for them.", "I don't think women fail to appreciate what men do for them.", "I don't agree that most women overlook what men do for them."), ("The idea that women don't appreciate what men do for them is rubbish.", "It's nonsense to say most women don't appreciate what men do for them.", "I totally reject the idea that women fail to appreciate what men do for them.")), weight=0.4),
    Item("sexismWomenPower", "sexism", ("hostileSexism2W27",),
         agree5(("Women seek power by getting control over men.", "Women go after power by getting control over men.", "Women try to gain power by taking control of men."), ("Women tend to seek power by getting control over men.", "Women do tend to go after power by getting control over men.", "I think women often seek power by taking control of men."),
                ("Women don't seek power by controlling men.", "I don't think women try to gain power by controlling men.", "Women aren't out to get power by taking control of men."), ("The idea that women seek power by controlling men is rubbish.", "It's nonsense to say women go after power by controlling men.", "I completely reject the idea that women try to get power by controlling men.")), weight=0.4),
    Item("sexismMenAppreciate", "sexism", ("hostileSexismM1W27",),
         agree5(("Most men don't appreciate all that women do for them.", "Most men just don't appreciate everything women do for them.", "Most men fail to appreciate all the things women do for them."), ("Most men don't fully appreciate what women do for them.", "Most men don't really appreciate everything women do for them.", "I think most men underappreciate what women do for them."),
                ("It's not true that men don't appreciate what women do for them.", "I don't think men fail to appreciate what women do for them.", "I don't agree that most men overlook what women do for them."), ("The idea that men don't appreciate what women do for them is rubbish.", "It's nonsense to say most men don't appreciate what women do for them.", "I totally reject the idea that men fail to appreciate what women do for them.")), weight=0.4),
    Item("sexismMenPower", "sexism", ("hostileSexismM2W27",),
         agree5(("Men seek power by getting control over women.", "Men go after power by getting control over women.", "Men try to gain power by taking control of women."), ("Men tend to seek power by getting control over women.", "Men do tend to go after power by getting control over women.", "I think men often seek power by taking control of women."),
                ("Men don't seek power by controlling women.", "I don't think men try to gain power by controlling women.", "Men aren't out to get power by taking control of women."), ("The idea that men seek power by controlling women is rubbish.", "It's nonsense to say men go after power by controlling women.", "I completely reject the idea that men try to get power by controlling women.")), weight=0.4),
    Item("sexismPurity", "sexism", ("benevolentSexism2W27",),
         agree5(("Many women have a quality of purity that few men possess.", "There's definitely a purity many women have that few men do.", "Many women have a real purity to them that very few men possess."), ("A lot of women have a purity about them that few men do.", "Many women have a certain purity that you rarely find in men.", "There's a purity to a lot of women that few men have."),
                ("Women aren't any purer than men.", "I don't think women have some purity that men lack.", "I don't agree that many women have a purity few men have."), ("The idea that women have some special purity men lack is nonsense.", "It's rubbish to say women have some kind of purity that men don't.", "I completely reject the idea that women have a purity men lack.")), weight=0.3),
    Item("sexismPedestal", "sexism", ("benevolentSexism3W27",),
         agree5(("A good woman should be set on a pedestal by her man.", "A good woman absolutely deserves to be put on a pedestal by her man.", "A man should always put a good woman on a pedestal."), ("A good woman deserves to be put on a pedestal by her man.", "A good woman ought to be put on a pedestal by her man.", "A man should put a good woman on a pedestal."),
                ("No woman needs putting on a pedestal by her man.", "I don't think a man should put a good woman on a pedestal.", "A good woman doesn't need her man to put her on a pedestal."), ("Putting a woman on a pedestal is the last thing a good man should do.", "It's completely wrong to think a man should put a good woman on a pedestal.", "The idea that a good woman should be put on a pedestal by her man is nonsense.")), weight=0.3),
    Item("scotRefBond", "independence", (), custom=scot_ref_bond, nations=(2,), weight=0.8),
    Item("scotRejoinEU", "independence", ("scotIndepRejoinEUW25", "scotIndepRejoinEUW23"),
         by_code({1: ("An independent Scotland would have no chance of rejoining the EU.", "There's no way an independent Scotland would get back into the EU.", "It's very unlikely an independent Scotland could rejoin the EU."), 2: ("An independent Scotland probably couldn't rejoin the EU.", "I doubt an independent Scotland would be able to rejoin the EU.", "It's fairly unlikely an independent Scotland would get back into the EU."),
                  4: ("An independent Scotland would probably be able to rejoin the EU.", "I think an independent Scotland would most likely be able to get back into the EU.", "It's fairly likely an independent Scotland could rejoin the EU."), 5: ("An independent Scotland would be able to rejoin the EU.", "I've no doubt an independent Scotland could rejoin the EU.", "It's very likely an independent Scotland would be able to get back into the EU.")}), nations=(2,), weight=0.6),
    Item("scotSovereignty", "europe", ("sovereignty2W29",),
         agree5(("The UK as a whole voted to leave the EU, and Scotland has to accept that.", "Most people across the UK voted to leave the EU, and Scotland simply has to accept that.", "The whole UK voted to leave, and Scotland absolutely has to accept the result."), ("The UK voted to leave, and Scotland should accept that.", "The majority across the UK voted for Brexit, so people in Scotland ought to accept it.", "Scotland should respect the UK-wide vote to leave the EU."),
                ("Scotland shouldn't have to accept Brexit just because the UK as a whole voted for it.", "I don't think a UK-wide vote means people in Scotland have to accept leaving the EU.", "Just because the rest of the UK voted to leave doesn't mean Scotland should have to go along with it."), ("Scotland should never have been dragged out of the EU against its will.", "There's no way Scotland should have to accept Brexit just because the UK as a whole voted for it.", "Taking Scotland out of the EU against its will was completely wrong.")), nations=(2,), weight=0.6),
    Item("euRefBond", "europe", (), custom=eu_ref_bond, weight=0.5),
    Item("euRegret", "europe", (), custom=eu_regret, weight=0.6),
    Item("socialCircle", "social-circle", (), custom=social_circle_vote, weight=0.5),
    Item("satDemUK", "democracy", ("satDemUKW29", "satDemUKW27"),
         by_code({1: ("I'm very dissatisfied with how democracy works in the UK.", "The way democracy works in the UK leaves me very dissatisfied.", "I'm really unhappy with how democracy works in the UK.", "I'm really unhappy with the way democracy works in the UK."), 2: ("I'm a little dissatisfied with how democracy works in the UK.", "I'm somewhat unhappy with the way democracy works in the UK.", "I'm a bit dissatisfied with the way democracy works in the UK."),
                  3: ("I'm fairly satisfied with how democracy works in the UK.", "On the whole, I'm fairly happy with how democracy works in the UK.", "I'm reasonably satisfied with the way democracy works in the UK.", "On the whole, I'm reasonably happy with how democracy works in the UK.", "I'm pretty satisfied with the way democracy works in the UK."), 4: ("I'm very satisfied with how democracy works in the UK.", "I'm very happy with the way democracy works in the UK.", "On the whole, I'm very satisfied with the way democracy works in the UK.", "As far as I'm concerned, democracy in the UK works very well.")}), weight=0.5),
    Item("satDemEng", "democracy", ("satDemEngW29",),
         by_code({1: ("I'm very dissatisfied with how democracy works in England.", "I'm really unhappy with the way democracy works in England.", "The way democracy works in England leaves me very dissatisfied."), 2: ("I'm a little dissatisfied with how democracy works in England.", "I'm somewhat unhappy with the way democracy works in England.", "I'm a bit dissatisfied with the way democracy works in England."),
                  3: ("I'm fairly satisfied with how democracy works in England.", "On the whole, I'm reasonably happy with how democracy works in England.", "I'm pretty satisfied with the way democracy works in England."), 4: ("I'm very satisfied with how democracy works in England.", "I'm very happy with the way democracy works in England.", "As far as I'm concerned, democracy in England works very well.")}), nations=(1,), weight=0.4),
    Item("localSchools", "local-area", ("statusAreaEduW30", "statusAreaEduW25"),
         agree5(("The schools round here are excellent.", "The local schools are first-rate.", "The schools in my area provide a really high quality education."), ("The schools round here are good.", "The local schools are decent.", "The schools in my area give kids a good education."), ("The schools round here aren't up to much.", "The local schools aren't very good.", "I don't think the schools in my area give kids a particularly good education."), ("The schools round here are poor.", "The schools in my area are rubbish.", "The local schools really don't provide a decent education.")), weight=0.5),
    Item("localSpaces", "local-area", ("statusAreaSpacesW30", "statusAreaSpacesW25"),
         agree5(("The buildings and public spaces round here are really well kept.", "The buildings and public spaces in my area are kept in excellent condition.", "The buildings and public spaces near me are looked after really well."), ("The buildings and public spaces round here are well kept.", "The buildings and public spaces in my area are well looked after.", "The buildings and public spaces near me are kept in good condition."),
                ("The buildings and public spaces round here are a bit run down.", "The buildings and public spaces in my area could do with better upkeep.", "The buildings and public spaces near me aren't that well looked after."), ("The buildings and public spaces round here are badly run down.", "The buildings and public spaces in my area are in a terrible state.", "The buildings and public spaces near me are seriously neglected.")), weight=0.5),
    Item("ukGovtEconScot", "economy-blame", (), custom=impact_item(("ukGovtEconImpactScotW31", "ukGovtEconImpactScotW30"),
         ("The UK government has done Scotland's economy a lot of damage.", "The UK government has been really bad for Scotland's economy.", "The UK government has done serious harm to Scotland's economy."), ("The UK government has done Scotland's economy some damage.", "The UK government has been fairly bad for Scotland's economy.", "The UK government has harmed Scotland's economy somewhat."),
         ("The UK government has been good for Scotland's economy.", "The UK government has had a positive effect on Scotland's economy.", "The UK government has helped Scotland's economy."), ("The UK government has been very good for Scotland's economy.", "The UK government has had a really positive effect on Scotland's economy.", "The UK government has done Scotland's economy a lot of good."),
         ("The UK government has had mixed effects on Scotland's economy.", "The UK government has done Scotland's economy about as much good as harm.", "The UK government hasn't had much impact on Scotland's economy either way.")), nations=(2,), weight=0.6),
    Item("lastGovtEconScot", "economy-blame", (), custom=impact_item(("ukLastGovtEconImpactScotW31", "ukLastGovtEconImpactScotW30"),
         ("The last UK government did Scotland's economy a lot of damage.", "The last UK government was really bad for Scotland's economy.", "The last UK government did serious harm to Scotland's economy."), ("The last UK government did Scotland's economy some damage.", "The last UK government was fairly bad for Scotland's economy.", "The last UK government harmed Scotland's economy somewhat."),
         ("The last UK government was good for Scotland's economy.", "The last UK government had a positive effect on Scotland's economy.", "The last UK government helped Scotland's economy."), ("The last UK government was very good for Scotland's economy.", "The last UK government had a really positive effect on Scotland's economy.", "The last UK government did Scotland's economy a lot of good."),
         ("The last UK government had mixed effects on Scotland's economy.", "The last UK government did Scotland's economy about as much good as harm.", "The last UK government didn't have much impact on Scotland's economy either way.")), nations=(2,), weight=0.5),
    Item("ukGovtEconWales", "economy-blame", (), custom=impact_item(("ukGovtEconImpactWalesW31", "ukGovtEconImpactWalesW30"),
         ("The UK government has done Wales's economy a lot of damage.", "The UK government has been really bad for Wales's economy.", "The UK government has done serious harm to Wales's economy."), ("The UK government has done Wales's economy some damage.", "The UK government has been fairly bad for Wales's economy.", "The UK government has harmed Wales's economy somewhat."),
         ("The UK government has been good for Wales's economy.", "The UK government has had a positive effect on Wales's economy.", "The UK government has helped Wales's economy."), ("The UK government has been very good for Wales's economy.", "The UK government has had a really positive effect on Wales's economy.", "The UK government has done Wales's economy a lot of good."),
         ("The UK government has had mixed effects on Wales's economy.", "The UK government has done Wales's economy about as much good as harm.", "The UK government hasn't had much impact on Wales's economy either way.")), nations=(3,), weight=0.6),
    Item("lastGovtEconWales", "economy-blame", (), custom=impact_item(("ukLastGovtEconImpactWalesW31", "ukLastGovtEconImpactWalesW30"),
         ("The last UK government did Wales's economy a lot of damage.", "The last UK government was really bad for Wales's economy.", "The last UK government did serious harm to Wales's economy."), ("The last UK government did Wales's economy some damage.", "The last UK government was fairly bad for Wales's economy.", "The last UK government harmed Wales's economy somewhat."),
         ("The last UK government was good for Wales's economy.", "The last UK government had a positive effect on Wales's economy.", "The last UK government helped Wales's economy."), ("The last UK government was very good for Wales's economy.", "The last UK government had a really positive effect on Wales's economy.", "The last UK government did Wales's economy a lot of good."),
         ("The last UK government had mixed effects on Wales's economy.", "The last UK government did Wales's economy about as much good as harm.", "The last UK government didn't have much impact on Wales's economy either way.")), nations=(3,), weight=0.5),
    Item("warmMuslim", "warmth", ("warmMuslimW26",), warmth_item("Muslims"), weight=0.4),
    Item("warmJewish", "warmth", ("warmJewishW26",), warmth_item("Jewish people"), weight=0.4),
    Item("warmChristian", "warmth", ("warmChristianW26",), warmth_item("Christians"), weight=0.4),
    Item("warmAtheist", "warmth", ("warmAtheistW26",), warmth_item("non-religious people"), weight=0.4),
    Item("equalityBME", "equality", ("blackEqualityW27", "blackEqualityW23"), gone_too_far_item("equal opportunities for ethnic minorities"), weight=0.5),
    Item("equalityWomen", "equality", ("femaleEqualityW27", "femaleEqualityW23"), gone_too_far_item("equal opportunities for women"), weight=0.5),
    Item("equalityGay", "equality", ("gayEqualityW27", "gayEqualityW23"), gone_too_far_item("equal opportunities for gay and lesbian people"), weight=0.5),
    # The 2024 vote, one step on from the band (wave 29): one bubble at most, since all three share a topic
    Item("voteAgainst", "vote-2024", ("disapprovalVoteW29",), custom=vote_against, weight=0.8),
    Item("partyPreferred", "vote-2024", ("partyPreferredW29",), custom=party_really_preferred, weight=0.8),
    Item("votingWish", "vote-2024", ("votingWishW29",), custom=wished_vote, weight=0.8),
    # Brexit's effects beyond the headline ones (wave 27, 2024), and what staying in would have meant (2021-23)
    Item("brexitWorkers", "brexit-effects", ("effectsEUWorkersRetroW27",), brexit_effect5("working conditions for British workers"), weight=0.8),
    Item("brexitUnemployment", "brexit-effects", ("effectsEUUnemploymentRetroW27",), brexit_effect5("unemployment"), weight=0.8),
    Item("brexitTrade", "brexit-effects", ("effectsEUTradeRetroW27",), brexit_effect5("Britain's international trade"), weight=0.8),
    Item("brexitEconScotland", "brexit-effects", ("effectsEUEconScotRetroW27",), brexit_effect5("Scotland's economy"), nations=(codes.SCOTLAND,), weight=0.8),
    Item("brexitEconWales", "brexit-effects", ("effectsEUEconWalesRetroW27",), brexit_effect5("the Welsh economy"), nations=(codes.WALES,), weight=0.8),
    Item("remainEcon", "remain-effects", ("effectsRemainEconW23", "effectsRemainEconW22", "effectsRemainEconW21"), remain_effect5("the economy"), weight=0.6),
    Item("remainFinance", "remain-effects", ("effectsRemainFinanceW23", "effectsRemainFinanceW22", "effectsRemainFinanceW21"), remain_effect5("my own finances"), weight=0.6),
    Item("remainTrade", "remain-effects", ("effectsRemainTradeW21",), remain_effect5("Britain's international trade"), weight=0.6),
    Item("euCertain", "europe", ("selfEUCertainW30",),
         by_code({1: ("I'm not at all certain where I stand on the EU.", "Where I stand on the EU is far from settled in my mind.", "I haven't got a firm view on the EU either way."),
                  2: ("I'm fairly certain where I stand on the EU.", "I've a reasonably settled view on the EU.", "Where I stand on the EU is more or less settled in my mind."),
                  3: ("I'm very certain where I stand on the EU.", "My mind is completely made up on the EU.", "Where I stand on the EU is beyond doubt, as far as I'm concerned.")}), weight=0.6),
    # Globalisation, aspect by aspect (2020-21)
    Item("globalMigration", "globalisation", ("globalMigrationW21", "globalMigrationW20"), globalisation5("international migration"), weight=0.6),
    Item("globalTrade", "globalisation", ("globalTradeW21", "globalTradeW20"), globalisation5("international trade"), weight=0.6),
    Item("globalBanks", "globalisation", ("globalBanksW21", "globalBanksW20"), globalisation5("international banking"), weight=0.6),
    Item("globalBrands", "globalisation", ("globalBrandsW21", "globalBrandsW20"), globalisation5("multinational brands"), weight=0.6),
    Item("globalFilms", "globalisation", ("globalFilmsW21", "globalFilmsW20"), globalisation5("worldwide access to film, TV, music and sport"), weight=0.6),
    Item("globalOrgs", "globalisation", ("globalOrgsW21", "globalOrgsW20"), globalisation5("the influence of bodies like the UN"), weight=0.6),
    Item("globalPlanes", "globalisation", ("globalPlanesW21", "globalPlanesW20"), globalisation5("international air travel"), weight=0.6),
    Item("globalTalk", "globalisation", ("globalTalkW21", "globalTalkW20"), globalisation5("fast, cheap communication across the world"), weight=0.6),
    Item("globalTourism", "globalisation", ("globalTourismW21", "globalTourismW20"), globalisation5("global tourism"), weight=0.6),
    # Elections: whether a vote counts
    Item("voteDifference", "vote-difference", ("voteMakesDifferenceW27",), vote_difference, weight=0.8),
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
    "elections": {"democracy", "elections", "electoral-system", "voter-id", "voting-duty", "tactical-voting", "turnout", "voting-age", "vote-difference"},
    "economy": {"economy-direction", "economy-outlook", "economy-blame", "cost-of-living", "personal-outlook"},
    "inequality": {"redistribution", "inequality", "fair-share-wealth", "one-law", "big-business", "management"},
    "public-spending": {"tax-and-spend", "deficit", "spending-cuts", "local-cuts"},
    "health": {"nhs-direction", "nhs-cuts", "private-health", "private-healthcare"},
    "immigration": {"immigration", "immigration-direction"},
    "europe": {"europe", "brexit-effects", "remain-effects"},
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


NEUTRAL = re.compile(r"more or less its fair share|about right|in equal measure|not sure I'd bother"
                     r"|as much good as harm|mixed effects|much impact|hasn't made much difference|hasn't made any difference"
                     r"|made little difference|made no difference|about the same|neither better nor worse|don't take either side"
                     r"|stay about where they are|a mix of public and private|neither well nor badly|neither good nor bad|cut both ways")
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
