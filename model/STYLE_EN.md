# English race comment style (learned from 17 KRBC preview documents, Aug–Oct 2026)

147 race paragraphs, average 164 words, 6 sentences, about 6 runners mentioned.

## Shape
- One paragraph per race, then a box:
  `Selections (5) White Thunder (7) Queens Impact (2) Raon Polis (1) Loom Chukje` / `Next Best 9, 4` / `Fast Start 1, 4, 6, 7, 9`
- Runners written as `(5) WHITE THUNDER` in the paragraph, title case in the box.
- Order: top pick → the other key runner → third and fourth joined with "whilst" → remaining two as "best of the rest" / "rate next" / "others in the hunt".

## What the sentences rest on (facts, not adjectives)
- Last two runs with finishing position, distance and date: "ran 2nd over 1400M last start", "was third three back", "won two back".
- Streaks and course form: "comes off back-to-back wins", "course and distance winner", "a two-time winner at this distance".
- Moves: "is up in class", "drops back in class", "comes up 4kg in weight", "is down 3kg".
- Fitness: "returns from six months out", "can strip fitter for that run", "first try at this distance".
- Running style and draw: "draws to hold a forward role", "led throughout", "coming from midfield", "doing his best work late".
- Connections: "with Seo Seung-un aboard", "under the in-form Kim Hyo-jung", apprentice claims.
- Maidens and exposure: "is still a maiden", "naught from twenty-two", "lightly raced".

## Verdict phrases
"is the one to beat" · "can go close" · "looks the other key runner" · "can be competitive" · "rates as an each-way chance" · "can be around the mark" · "is not to be dismissed" · "best of the rest" · "others in the hunt".

## Conventions
- Distances as `1400M` (no comma), weights as `4kg`, dates as `September 5th`.
- Negatives are conceded then turned: "He is up 3kg in weight, but ... he can measure up."
- British spelling and "whilst".

Implemented in `site/index.html` → `enClauses()` / `enComment()`; facts come from `model/predict.py`.
