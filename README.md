# British Voter Bot

The cards are built from the British Election Study Internet Panel. Please cite the data as the BES asks:

Fieldhouse, E., J. Green, G. Evans, J. Mellon, C. Prosser, J. Bailey, J. Griffiths and S. Perrett (2026). *British Election Study Internet Panel, Waves 1-31 (2014-2026)*, version 31.05. University of Manchester, University of Oxford and Royal Holloway, University of London. Fieldwork by YouGov. https://www.britishelectionstudy.com

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

A queue built before this changed can be brought into line with `python -m voterbot anonymise`,
which rewrites the headlines in place and leaves the posting order untouched.
