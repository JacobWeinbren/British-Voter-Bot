"""Which BES questions from wave 20 onwards the cards use, and why the rest are left out.

`python -m voterbot audit` rewrites docs/unused-questions.md. A variable counts
as used when its name (or its question stem) appears in the bot's source. The
reasons are pattern rules, reviewed by hand; anything unmatched is listed as
"not yet used" so it stays visible.

The codebook PDF is scanned as well (pdftotext if installed, else pypdf), and
question headers with no variable in the SPSS file get their own section: the
open-text questions (internetRead, selfOrgLast...) whose free-text answers
are not in the public release, and grid headers whose items carry other names.
"""

from __future__ import annotations

import collections
import re
import shutil
import subprocess
from pathlib import Path

import pyreadstat

from . import config

SOURCES = ["items.py", "persona.py", "profile.py", "codes.py", "sample.py", "brand.py", "geo.py"]
WAVE_RE = re.compile(r"^(.*?)(W\d+(?:_?W\d+)*)$")
SKIP = re.compile(r"^(wt_|starttime|endtime|timing|Timing|timestamp|wave\d|country|gor|pcon|oslaua|pano|Age|gender|id$|p_|ns_sec|profile_|panelsource|ukip|Randomiz|random|_)")

RULES: list[tuple[str, str]] = [
    (r"covid|coronavirus|vaccine|hesitant|PPE|Testing|Trace|highRisk|stoppedWork|furlough|strainHandle|lockdown|^cv|CVsuspect|trustGov|incomeGuarantee|Reduce coronavirus|dependentsCoronavirus",
     "Covid-era question (2020-22), tied to the pandemic"),
    (r"Mayor|FirstChoice|SecondChoice|FPTP|londonAssembly|londonTurnout|pcc|localElectionScot|welshElectionVote|eastMid|northEast|northYork|southYorks|tees|westEng|westMid|westYork|gm(FPTP|First|Second)|liverpool|northOfTyne|salford|bristol|cambridge|doncaster|bedford|leicester|mansfield|middlesbrough|croydon|hackney|lewisham|newham|towerHamlets|watford|_MayorVI|goodConductLocals",
     "A specific local or mayoral contest in one area and one year; the card already carries local vote intention"),
    (r"^like(Con|Lab|LD|SNP|PC|Grn|Green|Brexit|Reform|UKIP|Alba)|LookAfter|Unity|unity|bestOnMII|^pid|regretsIHaveAFew$|voteAgainst|tacticalVote|reasonForVote|^partyId|^partyMember|registeredSupporter",
     "Opinions about parties and the 2024 vote (likes, unity, who they look after, best on the issue, party identity, regrets, tactics): left out deliberately - the vote band carries the preference and the leader line the personalities"),
    (r"^(con|lab|ld|grn|snp|pc|brexit|brx|ukip)(Handle|Priorities|Patriotic|Competent|Trust|_Ideas)|^(lr|immig|redist|taxSpend|EUIntegration|enviroGrowth)(Con|Lab|LD|SNP|PC|Green|greens|Brexit|Starmer|Sunak)|^change\w+Lab$|^ptv|^winConstituency|^majorityParty|^prefer|^Achieve|^would|^noChance|Coalition|hungParliament|^likelyWin|Likelihood Win|Based Constituency|constituency2Win|^winLocal|^winUK|^expect(Con|Lab)|Achieve |Would Successfully|No Chance",
     "Where the respondent places a party or leader, or predicts a result - not their own view or circumstances"),
    (r"like\w+Former|likeJohnson|likeSunak|likeTruss|likeSturgeon|likeYousaf|likeTice|likeBartley|likeBerry|likeDenyer|likeRamsay|likeHarvie|likeSlater|likePrice|likeGething|likeSalmond|likeCorbyn|competent|integrity|polKnow|bestPM|partygate|handleGaza|handleUkraine|rwanda|csplUncover|knowf2f|ukraine",
     "About leaders who have since gone, or a specific episode of the time"),
    (r"partyContact|^contact(Con|Lab|LD|Grn)|Convince|CampaignDay|respdate|electionInterest|discussPolDays|sharedContent|postal|participation_4|participation_5|participation_6|regretsIHaveAFewNotVote|regretsIHaveAFewEUNotVote|recallVote19|generalElection(Certainty|VotePost|VoteSqueeze|VoteUnsqueeze|VoteNonVoter)|generalElecCertainty|changeView|voteMakesDifference|attemptTurnout|eligible|voteMethoda|debate|decidedVote|reasonForTurnaway|normPartyVote",
     "About the mechanics of the 2024 campaign or eligibility, rather than the person"),
    (r"^(al_scale|lr_scale|mii_cat|small_mii|LRAL|new_pcon|new_pano|ageGroup|neverPrivSchl|privPrimSchl|disabilityCensus|fatherVote|motherVote|genElecTurnoutRetro|euRefpastVote|euRefTurnoutRetro|incomeHousehold|incomeFilter|profiles_newspaper2|paperLast|ethnicity2|noDependents|preschoolKids|schoolKids|careAdult|careDuty|prevJob|selfOcc|selfNum|partnerOcc|partnerNum|occCheck|jobzone|sectorParent|sectorPartner|edlevelPartner|partnerEducation|hasValidVoteID|askedForID|efficacyNotUnderstand|efficacyEnjoyVote|efficacyVoteEffort|blackEquality|femaleEquality|gayEquality|belongGroup|ccinoIT|statusActivities|statusCulture|socMedia_111|selfPriorities|euRefPartner|vote2019Partner|scotWording|sSqueeze|scotRefID|euID|nfc|empathy|resourceAccess|statusEarnings|statusEducation|statusJobRespect|statusRespect|nonelecParticipation|globalEconomyEconImpact|changeEducation|satDem|voterIDConfident|voterIDVote|voterID|hostileSexism|benevolentSexism|smallEmergency|trustWestminster)",
     "Older wave, a sub-item or a variant of a question the card already uses"),
    (r"dealPriority|euPriorityBalance|effectsRemain|effectsEU|responsibleEcon|^global(Banks|Brands|Films|Migration|Orgs|Planes|Talk|Tourism|Trade)|selfEUCertain",
     "A 2020-23 Brexit or globalisation sub-question; the card uses the overall versions and the wave-31 economic-impact items"),
    (r"^leftRight$", "Left-right self-placement: the card's scales already show it"),
    (r"^warm|disabilityChild|highRiskLetter", "Left off deliberately: warmth ratings of religious groups and a child's disability are too raw to put on a public card"),
    (r"defenceSpend|environ(Carbon|Countryside|Flood|Forest|Solar|Species|WindFarms)",
     "A per-line 'spend much less ... much more of its budget' grid from 2023; tried as bubbles and dropped, since it is about specific lines rather than the budget"),
    (r"lifeSat|lifeHappy|lifeAnxiety|lifeWorthwhile|payRise|shortages|marriageLength|goodTimePurchase|(self|wc|mc|local|region|london|em|wb)Econ$|localUnemployment|nationalUnemployment|referendumLikely|scotgovt|welshgovt|govtHandle|labHandle",
     "A snapshot of 2020-25 circumstances or a past government's handling that will have moved on; the card uses the wave-31 equivalents"),
]
UNEXPLAINED = "Not yet used - no reason beyond time; could be added"

KIND_RE = re.compile(r"grid-open|OPEN TEXTBOX|\bOPEN\b|SINGLE CHOICE|MULTIPLE CHOICE|DYNAMIC GRID|\bGRID\b|\bGrid\b|Coded variable|NUMERIC|SCALE|Scale|TEXT", re.I)
OPEN_RE = re.compile(r"grid-open|OPEN TEXTBOX|\bOPEN\b", re.I)


def codebook_text(pdf_path: Path = config.CODEBOOK_PATH) -> str | None:
    """The codebook as text, or None if the PDF or a PDF reader is missing."""
    if not pdf_path.exists():
        return None
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True, check=True).stdout
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    return "\n".join(page.extract_text(extraction_mode="layout") or "" for page in PdfReader(str(pdf_path)).pages)


def codebook_questions(text: str) -> dict[str, tuple[str, list[int], str]]:
    """Question headers in the codebook: name -> (type, waves, question text).

    A header is a variable-style name alone on a line (internetRead, values1,
    PTVGrid1) with a question type or wave tag in the lines under it; the wave
    tag often wraps, so the header lines are joined before the waves are read.
    """
    lines = text.splitlines()
    found: dict[str, tuple[str, list[int], str]] = {}
    for i, line in enumerate(lines):
        match = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*", line)
        if not match:
            continue
        name = match.group(1)
        if len(name) < 3 or re.search(r"W\d", name) or not re.search(r"[a-z][A-Z0-9_]", name):
            continue  # wave tags, leader names and section titles are not variable names
        head = []  # the type and wave tag: up to four lines, ending at the type keyword, a blank line or running text
        for nxt in lines[i + 1:i + 5]:
            if not nxt.strip() or (len(nxt.split()) > 4 and not KIND_RE.search(nxt)):
                break
            head.append(nxt)
            if KIND_RE.search(nxt):
                break
        joined = " ".join(head)
        if not (KIND_RE.search(joined) or re.search(r"\bW\d+", joined)):
            continue
        kind = KIND_RE.search(joined)
        tag = re.sub(r"\s+", "", KIND_RE.sub("", joined.replace(name, "")).replace("topup", ""))
        waves = sorted({int(w) for w in re.findall(r"W(\d+)", tag) if int(w) <= config.WAVE})
        body = next((l.strip() for l in lines[i + 1 + len(head):i + 12] if len(l.split()) >= 4 and not l.strip().startswith("cols")), "")
        found.setdefault(name, (kind.group(0) if kind else "", waves, body[:160]))
    return found


def unreleased_questions(questions: dict, released: set[str]) -> dict[str, tuple[str, list[int], str]]:
    """Codebook headers with no variable (or variable prefix) in the data, ignoring names the PDF cut short."""
    lower = {r.lower() for r in released}
    out = {}
    for name, info in questions.items():
        key = name.lower()
        if key in lower or any(r.startswith(key) for r in lower):
            continue
        if any(o != name and o.lower().startswith(key) for o in questions):
            continue  # a longer header shares the prefix: this one was truncated at the column edge
        out[name] = info
    return out


def _stem(column: str) -> tuple[str, str]:
    match = WAVE_RE.match(column)
    return (match.group(1), match.group(2)) if match else (column, "")


def _waves(suffix: str) -> list[int]:
    return [int(w) for w in re.findall(r"W(\d+)", suffix)]


def _reason(stem: str, label: str) -> str:
    for pattern, why in RULES:
        if re.search(pattern, stem) or re.search(pattern, label, re.I):
            return why
    return UNEXPLAINED


def write_audit(out_path: Path = config.ROOT / "docs" / "unused-questions.md") -> Path:
    _, meta = pyreadstat.read_sav(config.SAV_PATH, metadataonly=True)
    labels = {k: (v or "") for k, v in meta.column_names_to_labels.items()}
    values = meta.variable_value_labels
    source = "\n".join((config.ROOT / "voterbot" / f).read_text() for f in SOURCES)
    literal = set(re.findall(r"[\"']([A-Za-z][A-Za-z0-9_]*)[\"']", source))
    fstem = {s for s in re.findall(r"f[\"']([A-Za-z][A-Za-z0-9_]*)\{", source) if len(s) > 2}
    by_stem: dict[str, list[str]] = collections.defaultdict(list)
    used: set[str] = set()
    for column in meta.column_names:
        stem, _ = _stem(column)
        by_stem[stem].append(column)
        if column in literal or stem in literal or any(column.startswith(s) for s in fstem) or re.fullmatch(r"(lr|al)\d", stem):
            used.add(stem)
    rows = []
    for stem, cols in by_stem.items():
        waves = sorted({w for c in cols for w in _waves(_stem(c)[1])})
        if not waves or max(waves) < 20 or SKIP.match(stem):
            continue
        label = labels.get(cols[-1], "")
        ends = [s for k, s in values.get(cols[-1], {}).items() if k < 900 and not re.fullmatch(r"\d+", str(s))]
        answers = " / ".join(ends[:2]) if len(ends) >= 2 and len(values.get(cols[-1], {})) > 6 else "; ".join(ends[:5])
        status = "Used" if stem in used else _reason(stem, label)
        rows.append((stem, ",".join(str(w) for w in waves if w >= 20), label, answers, status))
    rows.sort(key=lambda r: (r[4] != "Used", r[4], r[0].lower()))
    used_n = sum(r[4] == "Used" for r in rows)
    out = ["# BES questions from wave 20 onwards: what the bot uses and what it leaves out", "",
           f"{len(rows)} variable stems with at least one fielding from wave 20. {used_n} are used somewhere on the cards; the rest are grouped by the reason they are left out. "
           "Profile (p_*), weights, timing and admin variables are not listed. 'Answers' shows the scale ends or the first few response options so short labels make sense. "
           "Regenerate with `python -m voterbot audit`.", ""]
    for status in dict.fromkeys(r[4] for r in rows):
        group = [r for r in rows if r[4] == status]
        out += [f"## {status} ({len(group)})", "", "| Variable | Waves | Label | Answers |", "|---|---|---|---|"]
        out += [f"| {s} | {w} | {l.replace('|', '/')} | {a.replace('|', '/')} |" for s, w, l, a, _ in group]
        out.append("")
    out += codebook_section(set(by_stem) | set(meta.column_names))
    out_path.write_text("\n".join(out))
    return out_path


def codebook_section(released: set[str]) -> list[str]:
    """The questions the codebook PDF has that the SPSS file does not, from wave 20 on."""
    text = codebook_text()
    if text is None:
        return ["## In the codebook but not in the released data", "",
                f"Not checked: {config.CODEBOOK_PATH.name} was not found, or neither pdftotext nor pypdf is installed.", ""]
    missing = {n: q for n, q in unreleased_questions(codebook_questions(text), released).items()
               if not q[1] or max(q[1]) >= config.EARLIEST_WAVE}
    open_text = {n: q for n, q in missing.items() if OPEN_RE.search(q[0])}
    headers = sorted((n for n in missing if n not in open_text), key=str.lower)
    out = [f"## In the codebook but not in the released data ({len(missing)})", "",
           f"The questionnaire ({config.CODEBOOK_PATH.name}) was scanned as well. These question headers have no variable in the SPSS file, "
           "so nothing from them can go on a card. The open-text questions come first: the BES does not ship free-text answers in the public "
           "panel file (they are available from the BES on request), so for instance the three websites named in internetRead are not in the data. "
           "The rest are grid headers and section labels whose items are released under other names and appear in the tables above.", "",
           "| Question | Type | Waves | Asked |", "|---|---|---|---|"]
    for name, (kind, waves, asked) in sorted(open_text.items(), key=lambda kv: kv[0].lower()):
        out.append(f"| {name} | {kind} | {','.join(map(str, waves)) or '?'} | {asked.replace('|', '/')} |")
    out += ["", "Grid headers and section labels with no variable of that name: " + ", ".join(headers) + ".", ""]
    return out
