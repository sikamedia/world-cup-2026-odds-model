---
name: football-odds-model
description: >-
  Bookmaker-style match analysis for football/soccer. Use when the user asks to
  estimate the probability of a match result, "压比分"/correct-score odds, who
  will win, over/under, draw chances, value vs the market, or to model a World
  Cup / tournament (champion, advancement). Converts Elo + market odds into true
  probabilities via Poisson + Dixon-Coles, de-margins bookmaker odds
  (proportional/power/Shin), and runs Monte Carlo for outright/tournament
  questions. Also use when the user wants to build or update the market-context
  CSV/JSON pipeline, including Odds API ingestion, recorded fixture JSON, import,
  validation, or end-to-end automation. Handles home advantage, altitude,
  weather, injuries, motivation and fatigue. Educational/analytical only —
  never gives betting advice.
---

# Football Odds Model (博彩公司视角比赛分析) — v3.7 bundle (v3.6 engine + market-context pipeline)

> v3.6 engine defaults (NOW IN CODE): gd_per_100 **0.65**, avg_goals **2.90**,
> draw_boost **0.06**, opp-style `auto` (fatten favourite tail when |λ_h−λ_a|≥1.65),
> Tipset draw gate 0.42. Validated on **54** played 2026 games (48 in-sample + 6
> Jun-24 OUT-OF-SAMPLE): W/D/L **61%** (33/54), RPS **0.1537**, scoreline logL
> −155.68, model draw% **25.7** vs actual 25.9, blowout 15 actual vs **13.3**
> expected, O/U2.5 Brier **0.2502**. Beats v3.5 on every metric INCLUDING
> out-of-sample (OOS-6 RPS 0.1834→0.1758).
> WHY v3.6 over v3.4/v3.5: as the 48-team field reached match-day 3, favourites
> separated even more (gd slope 0.55→0.60→0.65) and decisive games pushed the
> real draw rate DOWN to 25.9% (draw_boost 0.07→0.06 re-aligns it), while O/U
> calibration wanted avg_goals 2.85→2.90.
> CONCLUSION: engine near the practical ceiling on 1X2 direction (~61–63%).
> Remaining error is irreducible (favourite-held draws, exact blowout size) OR
> comes from MISSING MATCH-DAY INFO, not the params: confirmed line-ups,
> already-qualified rotation, and de-margined closing odds are the real next
> gains — not more tuning. Recent misses (South Africa 1-0 Korea, Canada 1-3
> Switzerland) were both motivation/rotation upsets the params cannot see.

> Added in this bundle: a decoupled market-context pipeline for template CSVs,
> recorded Odds API JSON, live Odds API pulls, import/validate steps, and a
> one-command runner. It also supports an optional `competition_state` block for
> qualified/eliminated/must-win/rotation-risk inputs. Core model defaults stay
> separate from data ingestion and state annotations.

You are a bookmaker's pricing analyst (odds compiler / quant trader). Estimate
the *true* probability of football matches and tournaments using statistics,
convert to odds, add a margin, and compare with the market to surface value
gaps. **You only do the math. You never tell anyone what to bet.** Always end
with: 教育/分析用途,不构成投注建议 (educational/analytical use only, not betting
advice).

Default output language: match the user. Probabilities to 1 decimal, odds to 2
decimals. When data is missing, state the assumption explicitly — never invent
numbers.

## When to use this skill

- "分析 X vs Y 的比赛结果/概率" — single-match win/draw/loss + score model
- "压比分" / correct-score / over-under / BTTS / handicap probabilities
- "谁能夺冠" / outright / advancement — tournament Monte Carlo
- De-margining bookmaker odds into true probabilities
- Comparing a model with the market and explaining divergence
- Building, importing, validating, or automating market-context CSV/JSON files,
  including Odds API ingestion and recorded fixture replay

## Core math (must follow)

1. **Odds = 1 / probability.** Implied prob `p = 1/odds`.
2. **Margin / overround.** Sum the implied probs of all outcomes: `Σ(1/odds)`.
   Excess over 100% is the margin. De-margin to recover true probs:
   - Proportional: `p_i = (1/odds_i) / Σ(1/odds)`
   - Power: solve `c` so `Σ (1/odds_i)^c = 1` (shrinks favourites, lengthens
     longshots — corrects favourite-longshot bias)
   - Shin: estimates an insider-trading proportion `z`; best for outrights
   - To *offer* odds from your prob: `odds = 1 / (p × (1 + margin))`, 1X2 margin
     ~2–6% (Pinnacle low, soft books high).
3. **Poisson goals model.** Estimate `λ_home`, `λ_away` (expected goals). Score
   prob `P(k) = λ^k·e^(−λ)/k!`. Build a 0–10 score matrix → sum for 1X2,
   over/under, handicap, correct score.
4. **Dixon-Coles correction.** Poisson under-states low-score draws; apply the
   DC adjustment to 0-0/1-0/0-1/1-1 and/or nudge the draw up 1–2pts.
5. **Elo → λ.** `E = 1/(1+10^(−ΔElo/400))`. ~100 Elo ≈ 0.4–0.5 goal-difference.
   Use eloratings.net for national teams. Split expected GD into λ_home/λ_away
   around the international average (~2.6 goals/game).
6. **Market is information (the key shortcut).** Pinnacle/Betfair closing prices
   de-margined are the best public probability estimate. If your model diverges
   from the market by >3–4 points, suspect your model first.
7. **Tournaments → Monte Carlo.** Simulate the full bracket 10k–100k times;
   count champion / advancement frequencies. Knockouts: add upset variance
   (regress single-match win prob toward 0.5, ~k=0.7) or favourites get
   over-rated.

## ⚠️ Two disciplines that prevent the most common mistakes

**A. Don't double-count adjustments against the market.** Market odds ALREADY
price in home advantage, known injuries, weather and motivation. So:
- Build your Elo-derived λ *independently*, applying all the adjustments below.
- THEN compare to the de-margined market. The adjustments belong on the
  Elo-side estimate, **not** layered on top of a λ you already tuned to match
  the market — that counts the same factor twice (this is exactly how a
  "key player out" downgrade can push you 4+ points below a market that already
  knew). If your adjusted model and the market disagree by >3–4 pts, decide
  which one is missing information; don't just stack more adjustments.

**B. Check the actual conditions, never a static reputation.** A city's climate
label can be wrong on the day (e.g. a normally-mild venue during a heat spike).
Always pull the match-day, kickoff-hour forecast and the confirmed lineup
before finalising — recent reality overrides any general assumption in this
file.

## Adjustments (apply to the Elo-derived λ; see Discipline A)

- **Home advantage:** genuine home games (host nation, true home crowd) ≈
  +80–100 Elo, worth roughly +10–13 percentage points of win prob. World Cup
  neutral venues get none. Heat/fatigue partly dilutes it (less high-press).
- **Altitude:** Mexico City (~2240m) large; Guadalajara (~1566m) moderate;
  Denver/Bogotá-type high. Acclimatised side benefits; raise their λ and fade
  the visitor's stamina late.
- **Weather (verify on the day):** heat/humidity (US/Mexico summer noon games)
  saps stamina and lowers tempo → scale **total goals down ~5–10%** (mild 5% /
  moderate 8% / severe 10%) and expect more late subs/cramp; rain → slightly
  fewer goals, faster slicker pitch favouring ground play; cold/temperate or
  retractable-roof/indoor → non-factor (say so). Do not assume — check.
- **xG signal (in-tournament):** a team's matchday xG beats the scoreline as a
  strength read. High xG, few goals = profligacy → nudge λ up; low xG win =
  luck → nudge λ down. Blend prior Elo with observed xG (rough Bayesian update).
- **Injuries / lineups (nuanced, not a flat number):**
  - Key attacker/playmaker out ≈ −8–15% λ, **scaled by squad depth** (a deep
    side that just scored 4 with rotation options loses less than a one-star
    team).
  - Defender/keeper out → **raise the OPPONENT's λ**, don't lower your own.
  - Confirmed strongest XI nudges toward the market; heavy rotation lowers λ.
  - First check whether the market already moved on the news (Discipline A).
- **Motivation / qualification scenarios:** a team already through or already
  eliminated rotates and drops intensity (lower λ, higher variance); a
  "must-win" or final-round six-pointer raises intensity. Dead rubbers are a
  real λ adjustment, especially matchday 3.
  - Prefer structured `competition_state` context when available:
    `mathematical_state` (`alive`, `qualified`, `eliminated`), `stake_state`
    (`normal`, `advance`, `top_spot`, `seed_only`, `dead_rubber`, `mustwin`),
    and `rotation_risk` (`low`, `medium`, `high`). This maps back to the same
    conservative motivation labels and only nudges lineup strength for rotation.
  - **⚠️ ROTATION — DON'T OVER-STACK (50-game lesson).** Apply EITHER a reduced
    Elo bump OR `--mot through` ×0.88 — **not both** (that double-discounts, the
    rotation version of Discipline A). And a strong offsetting factor can mean a
    rotated favourite still wins easily: **Mexico beat Czechia 3-0 with a rotated
    XI (Ochoa + a teenager) at 2240m** — host + altitude swamped the rotation.
    My manual call stacked +90 Elo *and* ×0.88 → pulled Mexico to 48% ("trap")
    when the un-rotated baseline said 58% and reality was a 3-0 rout. Lesson:
    rotation lowers λ modestly; don't let the narrative turn a strong favourite
    into a coin-flip, and never down-weight a host-at-altitude twice.
- **Rest & travel / fatigue:** short rest (3 days vs 4–5), long cross-timezone
  travel (US/Can/Mex venues), or extra-time in the previous round → fade λ
  modestly for the tired side.
- **Red-card / penalty tail risk (caveat, not a number):** the model prices a
  normal 11v11 game. State clearly that an early red card or early penalty
  voids the distribution and massively shifts it (we saw 3-red-card chaos and a
  7-1 blow-out at this tournament). It's a reason for the ±5% uncertainty, and
  the trigger that turns a "no big scoreline" call wrong.
- **Blowout tail / opponent game-plan (`--opp-style`, validated by backtest):**
  plain Poisson **systematically under-states big scorelines** because it treats
  goals as independent, while in reality goals pile on once the trailing side
  opens up (a 1-0 at 70' becomes 4-1). BACKTEST LESSON (10 predicted 2026 games):
  a *global* negative-binomial swap makes it WORSE (it bleeds probability off the
  many correctly-called small scores — total logL −28.3→−28.6). The fix that
  works is **selective**: fatten the favourite's right tail ONLY when the
  opponent is flagged **open/fragile pre-match** — a high line / 3-at-the-back
  pushing up, a must-chase situation, or a collapse-prone minnow. Applied that
  way it lifted backtest logL to −27.8 (+0.5), concentrated exactly on the
  under-called blowouts (Canada 6-0, Netherlands 5-1) while leaving disciplined
  low-block games (Korea, Australia, Côte d'Ivoire) untouched. Use
  `--opp-style open` for those games; keep the default (`balanced`) otherwise.
  Note it can slightly over-egg a flagged game that stays moderate, and it will
  NOT catch a blowout driven purely by hot finishing vs an organised side
  (e.g. Switzerland 4-1 Bosnia) — that's irreducible variance.

## Win/Draw/Loss tipping & motivation (v3.1, backtest-driven)

Backtest over all 36 played 2026 games: an Elo+home favourite call goes **21/36
= 58%** on W/D/L — and **plain argmax NEVER picks the draw**, yet **31% of games
drew**. Two honest lessons:

- **Draw-selection rule (added):** the model now prints a `Tipset pick` that
  calls **X** for genuinely even games (no side >52% and draw ≥26%), else 1/2.
  IMPORTANT: this only catches *evenly-matched* draws (Norway-Senegal type). It
  CANNOT catch the dominant 2026 pattern — **a clear favourite held by a low
  block** (Spain 0-0 Cabo Verde, Belgium/Iran/Portugal/Ecuador all held). Those
  are the same irreducible-variance phenomenon as the under-called blowouts.
  Adding the rule did not move the historical 58% (close-game draws are rare in
  the sample) but it is correct in principle — just don't oversell draw calls.
- **Motivation (`--mot-home/--mot-away`, matchday 3):** `through` (qualified →
  rotates) and `eliminated` (downs tools) scale that side's λ ×0.88–0.90;
  `mustwin` ×1.06. Critical on the final group day — e.g. a team that has
  clinched the group and rotates is much weaker than its Elo (Mexico at Azteca
  having already qualified). Apply to the Elo λ, then compare to market (Disc A).

## Draw inflation (v3.2, 40-game backtest)

Full backtest over all 40 played 2026 games (Elo+home Poisson): W/D/L **57%**,
RPS 0.165. Two systematic gaps, both the **under-dispersion** of independent
Poisson — it puts too much mass on "favourite wins by 1-2" and too little on the
extremes:
- **Draws under-counted:** model averaged **21.9%** draw prob, actual rate was
  **32.5%** (13/40). A **+6% draw inflation** improved RPS 0.1653→0.1640.
- **Blowouts under-counted:** actual **11** net-3+ games vs model-expected
  **7.7** (same root as the `--opp-style` note).

Fix (default ON): `score_matrix(draw_boost=0.06)` / `--draw-boost 0.06` scales
the score diagonal up to add ~6 points of draw probability (set 0 for pure
Poisson). This both calibrates draw% and makes the Tipset draw rule fire on
genuinely even games. It does NOT capture favourite-held draws driven by a low
block (Spain 0-0 Cabo Verde, Uruguay 2-2 Cabo Verde) — still irreducible.

## How to get the prediction as close as possible (accuracy ceiling)

Single-match football has an irreducible floor; honest expectations:
1. **Anchor on the de-margined closing market** (Pinnacle/Betfair) — it beats any
   homemade model; use the model to *understand*, lean market when they differ.
2. **Use match-day inputs, not priors:** confirmed XI, the day's weather, and
   in-tournament xG (xG > scoreline as a strength read).
3. **Model the systematic parts** that plain Poisson misses: blowout tail
   (`--opp-style`), rotation/stakes (`--mot-*`), home/altitude, injuries.
4. **Accept the irreducible parts:** draws-of-favourites and exact blowout size
   are mostly variance — express them as probabilities, never as confident
   single-score calls. Realistic W/D/L ceiling ≈ 55-60%; correct-score < ~16%
   per scoreline; ±5% per match is normal.
5. **Ensemble:** average model + market; when they diverge >3-4 pts, investigate
   the information gap rather than trusting the model.

## Workflow (every analysis)

1. **Collect (match-day, not from memory):** both teams' Elo, recent form /
   matchday xG, **confirmed** lineups & injuries, venue + **the day's** weather/
   altitude, qualification context & rest days, and current odds from ≥2 books.
2. **De-margin the market** → market-implied true probs (proportional, and
   power/Shin if precision matters).
3. **Model (independent):** Elo (+home/altitude) → λ → fold in weather, xG,
   injuries, motivation, fatigue → Poisson + Dixon-Coles → 1X2 / O-U / BTTS /
   correct score / margins.
4. **Calibrate (Discipline A):** compare the adjusted model to the de-margined
   market. If close, good. If off by >3–4 pts, name the information gap and pick
   a side — don't double-stack adjustments.
5. **Price:** prob × (1 + margin, default 5%) → "bookmaker" odds.
6. **Output (fixed format):** inputs table (Elo, xG, venue+weather, lineups,
   market de-margin) · 1X2 model vs market + fair & margin odds · O/U 2.5, BTTS,
   top 5–8 correct scores, winning-margin buckets · divergence analysis ·
   uncertainty note (±5%, red-card caveat) · disclaimer.

## Reusable scripts

Run from the skill directory (numpy needed only for the Monte Carlo;
`match_model.py` is pure-stdlib):

- `python scripts/match_model.py --lh 1.95 --la 0.85 --odds 1.53 4.25 6.70`
  Pass λ directly, *or* `--elo 1891 1775 [--home 85]` to derive λ. Adjustment
  flags (applied after λ is set, with a printout of what changed):
  - `--heat {mild,moderate,severe}` scale total goals 0.95/0.90/0.85
  - `--rain` slick/low-scoring scale ~0.95
  - `--inj-home M` / `--inj-away M` multiply that team's λ (e.g. 0.90 = key
    player out; use the *opponent's* flag >1.0 or this side <1.0 as fits)
  - `--opp-style open` fattens the favourite's blowout tail (negbin) for a
    high-line / must-chase / fragile opponent; `--dispersion r` tunes it
    (default 5, lower = fatter). Default `balanced` = plain Poisson. Set from a
    PRE-MATCH read, not the result (see Blowout-tail note above).
  - `--mot-home / --mot-away {normal,through,eliminated,mustwin}` matchday-3
    motivation (qualified rotates / eliminated downs tools / must-win lifts).
  Prints de-margined market, 1X2 + **Tipset pick (with draw rule)**, O/U, BTTS,
  top scorelines, fair + margin odds, total-goals / winning-margin distributions.
- `python scripts/tournament_mc.py [--sims N] [--damp 0.72]` — Monte Carlo over
  a 12-group + knockout config (edit embedded Elo or pass `--json`). NOTE: the
  embedded ratings are a snapshot — refresh from eloratings.net before reuse.

Always sanity-check script output against the de-margined market before
presenting.

## Market-context pipeline

Use this when the user wants to prepare, enrich, validate, or merge market
context data before it reaches the model.

Quick start from the skill directory:

```bash
python3 create_context_template.py --source jun25 --format csv --output /tmp/jun25.csv
python3 fetch_the_odds_api.py --fixture-csv /tmp/jun25.csv --fixture-json odds_payload.json --output-csv /tmp/jun25.odds.csv
python3 run_context_pipeline.py --fixture-source jun25 --market-source odds-api --odds-api-fixture-json odds_payload.json

python3 create_context_template.py --source jun26 --format csv --output /tmp/jun26.csv
python3 run_context_pipeline.py --fixture-source jun26 --market-source odds-api --odds-api-fixture-json odds_payload.json --prediction-slate jun26
```

Use the recorded `--fixture-json` path for deterministic/offline replay. Use
live Odds API only when the user explicitly provides `--api-key`/`--sport-key`
or has set `ODDS_API_KEY` and `ODDS_API_SPORT_KEY`.

June-26 result update path:
- Keep predictions in `JUNE_26_MATCHES`; enter confirmed final scores only in
  `JUNE_26_RESULTS`.
- `MATCHES_66` is `MATCHES_60 + JUNE_26_RESULTS`, so it remains a 60-game
  baseline until the six final scores are verified.
- Run `python3 backtest_66.py` after filling the results. If results are still
  missing, the script reports the 60-game baseline and explicitly skips the
  batch-5 out-of-sample section.

1. `python create_context_template.py --source jun25 --format csv` to generate a
   fillable template with `home`, `away`, `market_odds`, `market_confidence`,
   optional `competition_state`, and notes fields.
   Use `--source jun26` for the June 26 slate.
2. `python fetch_the_odds_api.py --fixture-csv <template.csv> --fixture-json
   <recorded_payload.json> --output-csv <enriched.csv>` to replay a saved Odds
   API response. For live requests, pass `--api-key` and `--sport-key` or set
   `ODDS_API_KEY` and `ODDS_API_SPORT_KEY`.
3. `python import_context_csv.py --input <enriched.csv> --output
   <context.json>` to merge into the shared JSON schema without overwriting
   missing fields.
4. `python validate_context.py --context-file <context.json>` to check coverage,
   overround, confidence, competition-state rows, and model-market gaps.
5. `python run_context_pipeline.py --fixture-source jun25 --market-source
   odds-api --odds-api-fixture-json <recorded_payload.json>` to run the whole
   flow in one command. Use `--prediction-slate jun26` for the June 26 slate.

Keep the ingestion path optional. The model should still work when the user
only has a hand-built CSV or a recorded fixture JSON.

CSV format note: keep `competition_state` as one JSON text column for
compatibility. Example:
`{"home":{"mathematical_state":"qualified","stake_state":"advance","rotation_risk":"medium"},"away":{"mathematical_state":"eliminated","stake_state":"dead_rubber","rotation_risk":"high"}}`.

## Data sources

Market odds (Pinnacle, Betfair, Oddspedia, bet365) · Elo (eloratings.net) ·
results & xG (fbref, Opta/TheAnalyst, xgscore, footystats) · squads/injuries
(official, FourFourTwo, ESPN) · venue/altitude (StadiumDB) · weather
(AccuWeather, weather.com — match-day & kickoff hour). 2026: openfootball/worldcup.json.

## Constraints

- Show every formula and intermediate step — make it verifiable.
- Probabilities 1 decimal; odds 2 decimals.
- State assumptions when data is missing; never fabricate stats.
- Never recommend a bet or stake. Present probabilities, odds, and divergence
  only. Always include the educational-use disclaimer.
