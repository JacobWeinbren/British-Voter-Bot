# British Voter Bot

The cards are built from the British Election Study Internet Panel. Please cite the data as the BES asks:

Fieldhouse, E., J. Green, G. Evans, J. Mellon, C. Prosser, J. Bailey, J. Griffiths and S. Perrett (2026). *British Election Study Internet Panel, Waves 1-31 (2014-2026)*, version 31.05. University of Manchester, University of Oxford and Royal Holloway, University of London. Fieldwork by YouGov. https://www.britishelectionstudy.com

## Choosing which views reach a card

A card can only draw from the questions its respondent was actually asked, and the BES asks
some questions of everyone and others once, years ago, of a subsample. Left flat, the draw
fills the feed with whatever is most commonly answered. Three corrections shape it instead
(`ProfileBuilder.pick_opinions`):

- a fence-sitting answer is drawn at `items.NEUTRAL_WEIGHT`, because surveys nudge people
  towards the middle and a view either way says more about them
- a topic's items share one topic's worth of weight, so a subject the library happens to
  phrase nine ways does not get nine times the chances of one phrased once
- an item is lifted by how rarely it can be said at all, `(1 / availability) ** QUESTION_RARITY`,
  where availability is measured over a sample of the panel at build time (`item_availability`)

The lift can never push an item past the share of cards it could appear on, so a question few
people were asked stays uncommon on the feed - it just stops being invisible. `QUESTION_RARITY`
is the dial: 0 restores the old flat draw, 1 equalises every item's airtime, and the default of
0.5 keeps the balance honest, since the questions the BES puts to everyone are the ones British
politics actually turns on. None of this touches the top-issue bubble, which is still drawn
first whenever the respondent holds a view on the issue they named.

## Keeping respondents anonymous

Every card is one real BES respondent, so what it says about them is deliberately blunt at
the edges. Religion is published as a group large enough to hide in rather than the
denomination (`voterbot/codes.py`): the two largest churches keep their name, *Anglican* and
*Catholic*, and every smaller denomination reads as *Christian*, because "Free Presbyterian"
is five people in the whole panel and "Brethren" twelve. Age is
published as the decade someone is in and never the exact year (`persona.age_band`), with the
eighties left open at the top and the late teens - the two years a card can start at - a band
of their own; the exact age is still read to decide who is eligible for a card, it is just
never printed. The constituency,
ethnicity and gender stay as the survey records them - together with the coarser two, that
leaves 21% of the queue unique on those five attributes, against 32% before.

A faith is also left off entirely where the census finds almost nobody of it in the
respondent's constituency (`persona.faith_is_rare`, threshold in `config.RARE_FAITH_THRESHOLD`):
naming a faith that a few people in the seat hold, next to an ethnicity and a gender, comes
close to naming the respondent. Where the faith goes, so does any mention of the mosque or the
gurdwara in the life paragraph, which would otherwise say the same thing a sentence later. The
rule reads `data/reference/religion_pcon24.csv` and applies to the census's own minority groups
only - Christian and non-religious are too large anywhere to narrow anyone down.

A queue built before any of this can be brought into line with `python -m voterbot anonymise`,
which rewrites the headlines in place and leaves the posting order untouched.

### Reference data

`data/reference/religion_pcon24.csv` holds the five minority faith counts and the usual
resident population for all 632 British constituencies, from each nation's own census.

England and Wales are Census 2021 table TS030 (religion, ten categories) as published for
post-2019 Westminster constituencies - Office for National Statistics. Scotland is Scotland's
Census 2022 table UV205, published by output area and summed to constituencies through the
OA22-to-UKPC24 lookup - National Records of Scotland. NRS perturbs small-area counts to protect
confidentiality, so the Scottish figures are within a few tens of the published national totals
rather than exact; that is well inside what a threshold in single figures needs. Both releases
are under the Open Government Licence v3.0. Northern Ireland has no seats here: the BES panel
covers Great Britain.
