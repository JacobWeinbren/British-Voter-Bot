# Handoff: BES Voter Persona Social Post

## Overview
A 1080×1350 social-media graphic (Bluesky/Instagram portrait) presenting a "portrait of a voter" built from British Election Study (BES) survey data. First-person persona text, a Scotland map with the constituency marked, speech bubbles carrying BES-derived opinions, two horizontal political-position spectrums, and a party-coloured footer band showing voting-intention change. The layout is a template: the Glasgow North care worker is example content — every value (demographics, constituency, opinions, spectrum positions, parties) is swappable per persona.

## About the Design Files
The files in this bundle are **design references created in HTML** — prototypes showing intended look and behavior, not production code to copy directly. The task is to **recreate this design in the target codebase's existing environment** (React, Vue, a Python image pipeline, etc.) using its established patterns and libraries — or, if no environment exists yet, choose the most appropriate stack for generating these graphics (e.g. an HTML-to-PNG render step, or a canvas/SVG renderer) and implement there.

`BES Persona Post.dc.html` contains two live variants side by side; **option 2b** ("Mobile vertical · 1080×1350") is the approved final. Option 2a is the same content with the map on the left and split paragraphs; turn-1 sections (1a/1b) are earlier iterations kept for history — ignore them.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and copy structure are final. Recreate pixel-perfectly at 1080×1350. Output is a static image (no interactivity), so the only "behavior" to implement is data-driven rendering.

## Canvas
- 1080×1350 px, white (#ffffff) background, zero border radius everywhere (Modernist system: flat, architectural, no rounded corners except the circular map/spectrum markers).
- Structure: content column (flex, `justify-content: space-between`) with padding 46px top, 56px sides, 26px bottom; then a full-bleed footer band.
- Font: **Archivo** (Google Fonts) throughout, all text flush left.

## Layout (option 2b, top to bottom)
1. **Headline** — `font: 600 40px/1.28 Archivo`, color #201e1d, letter-spacing -0.01em.
   "I'm a **White Scottish** **atheist** **woman** from **Glasgow North**, aged **34**."
   Bold spans are weight 800; the constituency name is additionally colored #c2255c.
2. **Paragraph 1** — `font: 400 23px/1.45 Archivo`, color #3c3744.
   "I'm privately renting and finding it quite difficult on my current income. I'm currently working as a **care worker**, and I identify as **working class**." (bolds: weight 700, #201e1d)
3. **Paragraph 2 (news/websites)** — `font: 400 20px/1.45 Archivo`, color #6b6371.
   "I don't read the news much - my top source is the news on BBC One. My favourite websites are **the BBC**, **Facebook**, and **RightMove**." (bolds: weight 700, #201e1d)
   Note: plain short hyphens only, never em dashes, anywhere in copy.
4. **Top issue line** — `font: 600 28px/1.3 Archivo`, #201e1d.
   "My top issue is **the cost of living**." — the issue phrase is weight 800 with a 5px solid #c2255c bottom border (underline effect), padding-bottom 1px.
5. **Map + bubbles row** — flex, gap 32px, vertically stretched:
   - **Left: Scotland map**, 360×540 box, vertically centered. Real geography (see Assets): Scottish European-electoral-region boundaries merged, rendered via Mercator projection fit to the box with 8px inset. Fill #84a883 (sage green), stroke #41603f at 1.25px, stroke-linejoin round. Paths are lightly simplified (points closer than ~1.4px dropped; islets with bbox extent < 7px culled). **Constituency marker**: circle r=11 at the constituency's lon/lat (Glasgow North: -4.289, 55.889), fill #c2255c, 3px white stroke. No label, no ring.
   - **Right: 4 speech bubbles**, flex column, gap 20px, vertically centered, each:
     - Background #f4eef6 (soft lilac), border 2px solid #201e1d, padding 16px 20px, `font: 500 23px/1.35 Archivo`, #201e1d. No radius.
     - Tail: 14×14px square, same fill, positioned absolute left 26px / bottom -9px, rotated 45°, with right+bottom borders 2px #201e1d (renders as a down-pointing notch).
     - Copy (bolds weight 700):
       1. "My favourite leader is **John Swinney**. My least favourite is **Nigel Farage**."
       2. "Ordinary working people don't get their fair share of the nation's wealth."
       3. "NHS waiting times matter more to me than cutting taxes."
       4. "I'm more Scottish than British - Holyrood should decide more of what happens here."
6. **"Where I sit" spectrums** — column, gap 14px:
   - Header row (space-between, baseline): "Where I sit" `700 22px/1` #201e1d; right key `500 18px/1` #6b6371 with inline swatches: magenta dot "= me" · black tick "= scale midpoint" · #cfc5d6 bar "= middle half of voters".
   - Two slider groups (gap 8px between track block and label row; 48px-tall track block):
     - Track: 5px tall, #e9e3ec, full width, at y=30px of the block.
     - Middle-half band: darker segment #cfc5d6 over the track from 25% to 75% (the middle 50% of voters - IQR of the BES scale; track ends ≈ ±2sd).
     - Midpoint tick: 3×27px, #201e1d, fixed at 50% (5 on the BES 0-10 scale), y=18px.
     - Position marker: 22px circle, #c2255c fill, 3px white border, centered on its % position, y=22px. **No "ME" label.** Example positions: economic 26%, cultural 33%. Positions map the BES 0-10 scale directly to 0-100% (left = more left / more liberal); the tick is the scale midpoint, NOT the median voter.
   - Label row: `600 19px/1` #6b6371, ends space-between, middle label absolutely centered at 50%:
     - "← More left" / **Economic** (700, #3c3744) / "More right →"
     - "← More liberal" / **Cultural** (700, #3c3744) / "More authoritarian →"
7. **Footer band** — full-bleed, background = current-voting-intention party colour (SNP #fdf38e with ink #201e1d in the example), padding 22px 56px, column gap 8px:
   - "In 2024 I voted Labour. Today I'd vote SNP*" — `800 32px/1.2`, letter-spacing -0.01em. (Asterisk directly after the party, no full stop after it.)
   - "* Voting intention, British Election Study, May-June 2026" — `500 16px/1`, opacity 0.8.

## Data model (per persona)
```
{ ethnicity, religionOrNone, gender, constituency, age,
  housing, precarity, workStatus, occupation, classId,
  newsHabit, topNewsSource, favouriteWebsites[3],
  topIssue, bubbles[4],            // leader best/worst, 2 issue views, identity/devolution
  econPct, culturalPct,            // 0-100, 50 = median voter
  vote2024, intentionParty,        // party names
  constituencyLonLat }
```
Party colour map (band bg / text): SNP #fdf38e/#201e1d, Labour #e4003b/#ffffff, Conservative #0087dc/#ffffff, Reform UK #12b6cf/#201e1d, Lib Dem #faa61a/#201e1d, Green #02a95b/#ffffff, Plaid Cymru #005b54/#ffffff. Fallback #201e1d/#ffffff.

## Design Tokens
- Ink: #201e1d · Body: #3c3744 · Secondary: #6b6371
- Accent (persona/"me" everywhere): #c2255c
- Bubble fill: #f4eef6 · Spectrum track: #e9e3ec · Middle-half band: #cfc5d6
- Map fill: #84a883 · Map stroke: #41603f
- Ground: #ffffff · Band: party colour (above)
- Radius: 0 (markers are circles) · Rules/borders: 2px solid ink
- Type scale (px): 40 headline / 32 band / 28 issue / 23 bubbles+body / 20 secondary / 22-18 spectrum header / 19 spectrum labels / 16 footnote. Weights 400/500/600/700/800.

## Interactions & Behavior
None in the output (static image). Rendering behavior: for other UK nations swap the boundary file (England regions / Wales) and refit the projection; positions on spectrums map 0-100% → left-right; band colours from the party map. Map data loads async — the reference component re-renders on attribute change and shows a bordered "MAP UNAVAILABLE" fallback on fetch failure.

## Assets
- **Scotland boundaries**: `topo_eer.json` (Scottish European electoral regions TopoJSON) from `https://cdn.jsdelivr.net/gh/martinjc/UK-GeoJSON@master/json/electoral/sco/topo_eer.json` (martinjc/UK-GeoJSON, open licence). Same repo carries England/Wales equivalents.
- **Archivo** font: Google Fonts.
- Rendering libs in the reference: d3 v7 + topojson-client v3 (any equivalent geo pipeline is fine).

## Files
- `BES Persona Post.dc.html` — the design document (option **2b** = final; 2a = alt layout; turn 3 = Bluesky banner + avatar; 1a/1b = history). Inline styles carry all values.
- `persona-map.js` — the map web component: fetch + topojson merge, Mercator fit, path simplification, marker drawing, error fallback. Port its logic, not its API.
- `screenshots/` — PNGs: `final-post-2b.png` (1080×1350 final), `alt-post-2a.png`, `intro-poster-1080x1350.png` (pinned intro), `bluesky-banner-1500x500.png`, `bluesky-avatar-1000x1000.png`.

## Intro poster (pinned post)
1080×1350, same tokens. Structure: masthead ("British Voter Bot" + magenta dot, 2px rule) → headline "Real British voters, one at a time." → lead ("Every card is one real, anonymous BES respondent…") → "How to read a card" ruled key (map dot / bubbles / scales / vote band / sample row - each row: 180px flush-left mini-graphic + 21.5px explainer) → magenta close band ("No one is the average voter." / "Three voters a day") → small-print credit line (Jacob Weinbren · Lawrence McKay · Chris Terry-Enescu). Sample row copy: voters drawn from the wave's 31,392 respondents in proportion to BES survey weights (count comes from config PROFILE_COUNT - don't hard-code 2,000 in copy). Scales row names the BES 0-10 value scales, midpoint tick (5 of 10), IQR band (25th-75th pct). Credits grid at very bottom: three columns, name + magenta bsky handle (@jacobweinbren / @lawrencemckay / @cjterry .bsky.social); close band carries the "Taken one at a time…" subtitle.

## Bluesky profile assets
Union Jack drawn as flat SVG geometry (official construction, #012169 / #C8102E / white), cropped full-bleed.
- **Banner 1500×500**: plain Union Jack, full-bleed.
- **Avatar 1000×1000**: flag centered; magenta persona dot (230px circle, 22px white ring) at center. Composed for circular crop.
