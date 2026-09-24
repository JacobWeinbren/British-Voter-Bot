# British Voter Bot

The cards are built from the British Election Study Internet Panel. Please cite the data as the BES asks:

Fieldhouse, E., J. Green, G. Evans, J. Mellon, C. Prosser, J. Bailey, J. Griffiths and S. Perrett (2026). *British Election Study Internet Panel, Waves 1-31 (2014-2026)*, version 31.05. University of Manchester, University of Oxford and Royal Holloway, University of London. Fieldwork by YouGov. https://www.britishelectionstudy.com

## Choosing which views reach a card

A card can only say what its respondent was asked, and the BES asks some questions of everyone
and others once, years ago, of a subsample. Left to a flat draw, the feed fills with whatever the
survey asked most people - and with whatever subject the library happens to split into the most
questions. So every draw on a card (the opinion bubbles, the money sentence, the life details) is
given a target instead, and its weights are *solved for* at build time, per nation, over the whole
eligible panel, so the feed meets those targets as far as the answers allow (`voterbot/balance.py`).

The targets, and the dials behind them (all in `voterbot/config.py`):

- **Opinions.** Each theme (immigration, the economy, the NHS...) gets a share of the general
  bubbles: `SALIENCE_SHARE` (half) follows what voters in that nation name as the most important
  issue facing the country, measured from the BES's own question at build time; the rest is spread
  evenly over every theme, so the subjects nobody names still get a hearing. Within a theme its
  topics share equally, and within a topic the items share by their editorial weight. How many
  questions the BES asked, or how many the library phrased, no longer decides anything.
- **Life details and the money sentence.** Every life detail gets an equal share, as far as the
  answers allow, so the ones a handful of people can state stand level with an income band. The
  money sentence gives every BES question behind it an equal share, split evenly between the facts
  that question gives (`persona.MONEY_QUESTION`): per fact, the eight ways of being short of money
  would have wanted more of the sentence than the cards that can say any of them could give. Even
  per question the rarer facts cannot all reach their share, because they cluster on the same
  cards - someone who has borrowed for essentials usually has no savings and worries about money
  too - so the build gets within a few points (it prints the largest miss), and a card that holds
  one of them says one of them.
- **A cap.** No view or fact appears on more than `MAX_APPEARANCE` (half) of the cards that could
  carry it. A rare answer is lifted up to that point and no further - otherwise everyone who gave it
  would say it every time they came round. What a capped answer cannot use goes to the rest.
- **Middling answers** - marked where each wording is written (`items.middling`) - are drawn at
  `NEUTRAL_WEIGHT` (a fifth), because surveys nudge people to the middle and a view says more. The
  solver counts them the same way.
- **The top issue** still gets a bubble whenever the respondent holds a view on it, and a card's
  last bubble is about nation and identity `NATION_BUBBLE_CHANCE` of the time: most cards in
  Scotland and Wales, where the constitution is the second axis of politics, fewer in England.

The build prints what the solved weights achieve, nation by nation, next to what a flat draw would
have given; `python -m voterbot stats` shows each theme's share of the built queue. The two can
differ. The solver models each group as one draw from everything on offer, which is exactly what
the money sentence does. The bubbles have more to them - the top issue's bubble comes first and no
two bubbles share a theme - so the economy and immigration come out a few points above the report
and the rarest themes below it. The two life details are drawn without replacement, which the
model does not follow either: the commonest facts land up to a third above their share, and a
fact can reach about 55% of the cards that could carry it rather than the cap's half.

Two smaller rules follow the same idea. A personality or risk trait is mentioned only for the outer
`TRAIT_TAIL` (tenth) of the panel either side, measured at build time, so "I'm an extrovert" means
more extrovert than most. And the life and news paragraphs keep to line budgets measured from the
card as drawn (`LIFE_MAX_LINES`, `MEDIA_MAX_LINES`), so an extra detail lands only if it still fits.

### Wordings

A sentence gets as many wordings as its reach needs. At four cards a day no exact sentence should
come round more than twice a week (`MAX_WORDING_SHARE`, 1 card in 14), so the class sentence, on
seven cards in ten, has eleven wordings, and a fact on a handful of cards needs only one.
`stats` lists the most repeated wordings against that ceiling, and a test holds a built queue to it.

## Drawing the card

The card is an HTML page (`voterbot/templates/card.html`) screenshotted in headless Chromium.
It is set in Archivo, whose five weights in `assets/fonts` are inlined into every page
(`render.font_css`). They used to be linked by `file://`, which Chromium silently refuses for a
page loaded this way, so until September 2026 every card - the posted ones included - came out
in the machine's fallback sans-serif. Two checks now stand in the way of that happening again:
the posting workflow runs `python -m voterbot fontcheck` before it posts, and the renderer
refuses to screenshot any page whose typeface failed to load.

The vote band reads as a step from 2024 to today (`render.vote_steps`), each side in its own
party's colour, so a switch - or staying put - shows at a glance. The card never shrinks its
text to make room: small type on a phone is the one thing it cannot afford. The build lays every
card out in Chromium at its design sizes (`voterbot/fit.py`) and, where one would run past the
canvas, leaves optional copy off until it fits - the line on where they shared political
content, then the extra life details, and last, for a long seat name beside Scotland's tall map,
a tenth of the map (`profile.TRIMS`; about one card in a hundred). Once the fonts are in, the
views grow into any spare height up to 27px; a card that still runs over closes up the space
between its blocks, and one that overflows even then is refused by the renderer and passed over
for the next card rather than posted clipped. Every Chromium starts with font hinting off
(`render.CHROMIUM_ARGS`): with it on, Linux wraps about one card in sixty differently from macOS,
so a card that fitted on the Mac that built the queue could run over on the posting runner.
Each nation is fitted to the islands it actually draws, so it fills its box, and a coastal seat's
dot can draw past the map's edge rather than be cut off.

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
