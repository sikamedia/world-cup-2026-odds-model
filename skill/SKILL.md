---
name: football-odds-model
description: >-
  Bookmaker-style match analysis for football/soccer. Use when the user asks to
  estimate the probability of a match result, correct-score odds, who will win,
  over/under, draw chances, value vs the market, or to model a World Cup /
  tournament (champion, advancement). Converts Elo + market odds into true
  probabilities via Poisson + Dixon-Coles, de-margins bookmaker odds
  (proportional/power/Shin), and runs Monte Carlo for outright/tournament
  questions. Also use when the user wants to build or update the market-context
  CSV/JSON pipeline, including Odds API ingestion, recorded fixture JSON, import,
  validation, or end-to-end automation. Handles home advantage, altitude,
  weather, injuries, motivation and fatigue. Educational/analytical only —
  never gives betting advice.
---

# Football Odds Model — v3.9 bundle (KO n=29; n=28 review complete; λ-floor 0.30, ensemble w=0.6, and graded-k frozen)

中文：这是一个从博彩公司定价视角出发的足球比赛分析 skill。它用于估算胜平负、
正确比分、大小球、BTTS、让球、锦标赛晋级/冠军概率，以及对比模型概率和市场
盘口。只做数学和模型解释，不给投注建议。

> v3.6 engine defaults (NOW IN CODE): gd_per_100 **0.65**, avg_goals **2.90**,
> draw_boost **0.06**, opp-style `auto` (fatten favourite tail when |λ_h−λ_a|≥1.65),
> Tipset draw gate 0.42. Validated on **54** played 2026 games (48 in-sample + 6
> Jun-24 OUT-OF-SAMPLE): W/D/L **63%** (34/54), RPS **0.1508**, scoreline logL
> −155.58, model draw% **25.7** vs actual 25.9, blowout 15 actual vs **13.2**
> expected, O/U2.5 Brier **0.2522**. Beats v3.5 on every metric INCLUDING
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

> STAGE PROFILES (group vs knockout). The group "model" and the knockout "model"
> are the SAME engine with different parameter values, picked by `--stage`:
> - `--stage group` (default) = frozen v3.7A above (gd 0.65 / db 0.06 / ag 2.90).
>   Regression-locked; do not change.
> - `--stage knockout` = lower goals (`avg_goals` 2.70 — knockouts grind), plus an
>   **advancement resolver**. A knockout has no draw: a level game after 90' goes
>   to ET then penalties, so the draw mass is split by a near-coin-flip shootout
>   (`pen_tilt` 0.20 Elo tilt), and the 90' win split is regressed toward 0.5 by
>   a **GRADED, ΔElo-dependent ko_regress (LOCKED 2026-07-04, pre-registered
>   2026-07-03)**: `k_eff = 0.70 + 0.30 × min(1, |ΔElo|/350)`. Coin-flips keep
>   the full variance buffer (k 0.70); crushing favourites barely regress
>   (k→1.00). Initial lock evidence (R32 complete, n=16): advancement Brier
>   **0.1733** vs flat-0.70's 0.1808, called 13/16; ZERO 90-minute upsets all
>   round — all 3 favourite exits were pens-after-draw (Ger +230, Ned +110,
>   Aus +92), while every ΔElo≥232 favourite advanced in 90'. Live monitoring
>   through 2026-07-12 (KO n=28): called 22/28, advancement Brier **0.1606**,
>   90' RPS **0.1472**, actual upsets 6 vs model-expected 8.59. Flat 1.00 is
>   retrospectively best on n=28 (Brier 0.1570), but remains MONITOR-ONLY, not
>   a refit.
>   It spends the whole buffer (Argentina +495 was still dragged to 1-1 at
>   90'). Auto-graded when `--elo` is given (prints k_eff); explicit
>   `--ko-regress` overrides; falls back to flat 0.70 without Elo input. Output
>   is an **advancement probability** (`adv_home + adv_away = 1`), NOT a
>   regressed 90' W/D/L. Drop motivation/rotation — everyone is full strength.
> RULE: tune the knockout profile ONLY on its own batch (`backtest_ko.py` over
> `worldcup_2026_data_ko.py`); never mix knockout games into the group-stage
> parameter search. Discipline: any change must be pre-registered before
> testing; the n=24 (R16 complete) pre-registered review was executed
> 2026-07-08 with these outcomes:
>
> **v3.9 changes (n=24 pre-registered review, 2026-07-08):**
> - **λ floor 0.15 → 0.30 (knockout profile only) — ADOPTED.** Natural
>   experiment: Argentina 3-2 Egypt (R16). Egypt's λ was pinned at the 0.15
>   floor, making "Egypt scores 2" a ~1% event — Egypt scored 2 and led to
>   79'. Goals-channel scoring favours 0.30 across the board (P(Egy≥2) 1.1%
>   vs 3.8%, BTTS-yes logL −2.03 vs −1.42, P(3-2) 0.16% vs 0.54%); the
>   adv/RPS channels' small preference for 0.15 was survivor bias (Argentina
>   advanced anyway; cost on adv Brier ~0.005). Group profile keeps 0.15
>   (frozen). floor-0.15 remains a prospective SHADOW after the n=24 baseline;
>   only later floor-active fixtures identify a difference. At n=28 there are
>   four prospective rows but zero floor-active rows: **NO_DECISION**.
> - **Ensemble weight w = 0.6 model / 0.4 market — ADOPTED** (was 50:50).
>   Unified ledger n=8: model Brier 0.1769 < market 0.1910; recomputed
>   current-Elo 50:50 ensemble 0.1834. The CSV `p_ensemble` column contains one
>   `mixed_legacy` row from the stale-Elo/current-Elo transition. A refit must
>   use only unique, settled `live_current_elo` rows and waits for eligible
>   n>=12; then report the 0.0..1.0 model-weight grid in 0.1 steps. At current
>   n=29 the ledger has 11 eligible rows out of 13 total: **HOLD_W_0_6**. The two July 11
>   QF preview rows remain eligible because `basis` records pre-match Elo input
>   quality, not the existence of an official finalization artifact.
>   The 11 live fixtures through France-Spain are explicitly grandfathered;
>   every later or otherwise new `live_current_elo` fixture requires a
>   repository-relative `pre_match_evidence` file under `evidence/`. This may be a valid official
>   artifact or a sealed `ensemble_pre_match_freeze`; it must bind pre-kickoff
>   direct-Elo bytes/receipt, model and market probabilities, selected market
>   odds and de-margin method, and weather/lineup basis. Post-match capture or
>   reconstructed probabilities fail closed and cannot trigger the n=12 grid.
>   Freeze admission defaults to denial. Its caller must provide an external
>   trusted-anchor resolver whose source/anchor ID/payload digest match and whose
>   observation satisfies `frozen_at <= observed_at < kickoff`; a self-reported
>   timestamp is not proof of creation. The validator replays
>   `predict_jul11._predict/v1` with the exact frozen knockout parameters,
>   weather decision/scale, and lineup scales before accepting `reference_side`,
>   market (including any 90-minute draw split), or ensemble probabilities.
>   Official artifacts do not use this freeze-only resolver.
>   Grid-fit optimum was w=1.0, but
>   3 of 8 games are market-wrong-side low-frequency events — half-step to 0.6.
> - **graded-k HELD.** At n=28, graded-minus-flat-1.00 Brier is +0.0036 with
>   95% CI [-0.0044, +0.0116]: **NO_DECISION**. The interval crosses zero and
>   the rule stays frozen through the tournament.
> - **draw_boost 0.06 HELD** (neutral KO backtest口径: model 90' draws 6.8
>   expected vs 6 actual on n=24). The n=28 pre-registered
>   `floor {0.15,0.30} x draw_boost {0.06,0.07}` interaction is +0.00003 RPS:
>   `REVIEW_INTERACTION`, but negligible and with no production change.
> - **Lineup rule codified: only adjust on OFFICIAL rulings** (confirmed
>   absences/suspensions), never on rumours or "expected out" reports;
>   re-verify suspensions match-day (Balogun overturn + Quansah lessons).
> - **Style observations remain descriptive unless pre-registered.** The formal
>   low-block/counterattack cohort has zero eligible fixtures at n=28; reported
>   "low-block side 4/4" sequences cannot justify a model adjustment.
> `tournament_mc.py` reuses the SAME group profile via `elo_to_lambdas` (no
> private slope) and its knockout damping is now graded to match
> (`graded_damp` 0.72→1.00 over |ΔElo|/350; `--damp` forces the legacy flat).

> Added in this bundle: a decoupled market-context pipeline for template CSVs,
> recorded Odds API JSON, live Odds API pulls, import/validate steps, and a
> one-command runner. It also supports an optional `competition_state` block for
> qualified/eliminated/must-win/rotation-risk inputs. Core model defaults stay
> separate from data ingestion and state annotations.

You are a bookmaker's pricing analyst (odds compiler / quant trader). Estimate
the *true* probability of football matches and tournaments using statistics,
convert to odds, add a margin, and compare with the market to surface value
gaps. **You only do the math. You never tell anyone what to bet.** Always end
with: Educational/analytical use only; not betting advice. / 教育/分析用途,
不构成投注建议。

Default output language: match the user. Probabilities to 1 decimal, odds to 2
decimals. When data is missing, state the assumption explicitly — never invent
numbers.

中文：默认输出语言跟随用户。概率保留 1 位小数，赔率保留 2 位小数。缺数据时
必须明确写出假设，不能编造数据。

## When to use this skill / 适用场景

- Single-match win/draw/loss and score model. / 单场胜平负和比分模型。
- Correct-score, over-under, BTTS, and handicap probabilities. / 正确比分、
  大小球、双方进球和让球概率。
- Outright, champion, and advancement simulation. / 冠军盘、晋级概率和锦标赛模拟。
- De-margining bookmaker odds into true probabilities
- 将博彩公司赔率去水，还原真实概率。
- Comparing a model with the market and explaining divergence
- 对比模型和市场，解释概率分歧。
- Building, importing, validating, or automating market-context CSV/JSON files,
  including Odds API ingestion and recorded fixture replay
- 构建、导入、验证或自动化 market-context CSV/JSON，包括 Odds API 数据接入和
  录制 fixture JSON 回放。

## Core math (must follow) / 核心数学原则

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

中文摘要：赔率是概率倒数；盘口有 overround，需要先去水；比分用 Poisson/Dixon-
Coles 矩阵；Elo 转为预期净胜球再拆成双方 λ；市场收盘价是重要信息源；锦标赛
问题用 Monte Carlo 模拟。

## Two disciplines that prevent the most common mistakes / 两条关键纪律

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

中文：第一，不要把市场已经计入的信息再叠加一次；模型侧独立建模，然后和去水
盘口比较。第二，不要用城市或球队的静态印象替代比赛日现实；最终判断前要看当日
天气、开球时间、确认首发和伤停。

## Adjustments (apply to the Elo-derived λ; see Discipline A) / 调整项

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
  confirmed closed-roof/indoor → non-factor (say so). A retractable-roof venue
  alone is not proof of indoor conditions. `indoor_no_weather` requires retained,
  match-specific `official_roof` HTTP(S) evidence that explicitly confirms the
  roof will be closed, plus `roof_status=closed`, the selected fixture's exact
  `weather_evidence_fixture_id`, and a check within 6 hours of kickoff;
  otherwise use the outdoor evidence path. Weather
  adjustments need auditable context: kickoff/check/forecast issue and valid
  times, HTTP(S) source, evidence type, evidence snapshot plus SHA-256,
  `weather_decision`, and `weather_scale`. Heat evidence must be checked within
  6 hours and cover the kickoff hour; forecast issue time must be within 24
  hours of the check; applied rain requires hourly/radar evidence within 3
  hours. Invalid evidence blocks current predictions.
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

中文摘要：主场、海拔、天气、xG、伤停、首发、轮换、出线动机、疲劳和对手战术
都会影响 Elo 派生的 λ。所有调整都应保守，并先判断市场是否已经反映该信息。

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

## How to get the prediction as close as possible (accuracy ceiling) / 准确率上限

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

中文：单场足球有不可约随机性。最好的做法是锚定去水收盘盘口，叠加确认首发、
比赛日天气、xG、动机和轮换信息；模型和市场差距超过 3-4 个百分点时，优先查
信息缺口，而不是盲目信模型。

## Workflow (every analysis) / 每次分析流程

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

中文：每次先收集 Elo、xG、首发伤停、场地天气、出线形势和当前赔率；然后盘口
去水、独立建模、比较差异、报价并输出不确定性说明。

## Reusable scripts / 可复用脚本

Run from the skill directory (numpy needed only for the Monte Carlo;
`match_model.py` is pure-stdlib):

- `python capture_elo_evidence.py --tsv-out <World.tsv> --receipt-out
  <receipt.json> [--timeout-seconds 30]` is the only supported acquisition path
  for current Elo. It writes the direct, unmodified HTTP response body and a
  matching receipt to new create-only paths. Never copy or reuse an older TSV,
  reconstruct it from parsed data, transcode it, or normalize newlines. The
  receipt's response-completion timestamp is authoritative. If capture fails,
  a daily run produces no Elo preview and an official run produces no
  single-point probability. The local unsigned receipt is an audit binding,
  not a cryptographic attestation: stronger protection against a deliberately
  forged same-named TSV/receipt pair requires signed or external append-only
  scheduler logs.
- `python fetch_elo_current.py --tsv <World.tsv> --receipt <receipt.json> --out
  elo_current_latest.py --required-team <TEAM> ...` creates a SHA-256-labelled
  current Elo module from that exact pair. Official paths reparse the raw bytes
  and fail closed on stale, missing, mismatched, or estimated participant
  ratings; official finalization never accepts Elo more than 30 minutes after
  response completion.
- `python predict_jul11.py finalize --fixture
  {norway-england,argentina-switzerland,france-spain,england-argentina}
  --elo-module <elo.py> --elo-source-tsv <World.tsv> --elo-receipt
  <receipt.json> --context-file <context.json> --artifact-out <final.json>`
  finalizes exactly one pre-kickoff knockout match into a create-only hashed
  `pre_registered_match_prediction` artifact with its direct-HTTP receipt and
  stage recorded, using frozen w=0.6 model / 0.4 market. QF/SF remains schema 3;
  schema 4 activates only for third-place/final after SF102 settles and the real
  fixtures are registered. A direct
  two-way advancement market is preferred; otherwise the artifact explicitly
  marks the 90-minute-market fallback. The reader remains compatible with
  schemas 1-4 at their permitted stages.
- `python predict_jul11.py mc --artifacts <qf99.json> <qf100.json> --elo-module
  <elo.py> --elo-source-tsv <World.tsv> --elo-receipt <receipt.json>
  --qf98-winner {Spain,Belgium}` consumes the stored QF probabilities without
  recalculation; fresh, receipt-verified Elo is used only for future SF/final
  simulations and live match state is not incorporated. For the semifinals,
  generate a one-match context with `--source sf_jul14_15` and follow
  `AUTOMATION_RUNBOOK.md` for the two isolated finalization windows.
- `python scripts/match_model.py --lh 1.95 --la 0.85 --odds 1.53 4.25 6.70`
  Pass λ directly, *or* `--elo 1891 1775 [--home 85]` to derive λ. Adjustment
  flags (applied after λ is set, with a printout of what changed):
  - `--heat {mild,moderate,severe}` scale total goals 0.95/0.92/0.90
  - `--rain` slick/low-scoring scale ~0.95
  - `--inj-home M` / `--inj-away M` multiply that team's λ (e.g. 0.90 = key
    player out; use the *opponent's* flag >1.0 or this side <1.0 as fits)
  - `--opp-style open` fattens the favourite's blowout tail (negbin) for a
    high-line / must-chase / fragile opponent; `--dispersion r` tunes it
    (default 5, lower = fatter). Default `balanced` = plain Poisson. Set from a
    PRE-MATCH read, not the result (see Blowout-tail note above).
  - `--mot-home / --mot-away {normal,through,eliminated,mustwin}` matchday-3
    motivation (qualified rotates / eliminated downs tools / must-win lifts).
  - `--stage {group,knockout}` selects the parameter profile (default `group`).
    `--stage knockout` lowers `avg_goals` to 2.70 and prints an **advancement**
    block (90'→ET→penalties); tune via `--ko-regress` / `--pen-tilt`. Explicit
    `--avg-goals` / `--gd-per-100` / `--draw-boost` still override the profile.
  Prints de-margined market, 1X2 + **Tipset pick (with draw rule)**, O/U, BTTS,
  top scorelines, fair + margin odds, total-goals / winning-margin distributions.
- `python scripts/tournament_mc.py [--sims N] [--damp 0.72]` — Monte Carlo over
  a 12-group + knockout config (edit embedded Elo or pass `--json`). Reuses the
  group stage profile via `elo_to_lambdas` (one source of truth). NOTE: the
  embedded ratings are a snapshot — refresh from eloratings.net before reuse, and
  the bracket is a random PRE-DRAW estimate — supply the fixed R32 bracket once
  the group stage is complete for an accurate from-here forecast.
- `python backtest_ko.py` (repo root) — knockout-only backtest over
  `worldcup_2026_data_ko.py`, kept SEPARATE from the 72 group-stage games.
- `python predict_r32.py` (repo root) — advancement-to-R16 table for the 16
  fixed Round-of-32 ties. Exact (needs only the matchups, no bracket tree).
- `python predict_bracket.py [--sims N]` (repo root) — Monte Carlo over the
  fixed R32 bracket for R16/QF/SF/Final/Champion odds. `R32_FIXTURES` is in the
  official FIFA bracket-tree order (Match 73-104), so the pairings are exact.

Always sanity-check script output against the de-margined market before
presenting.

中文：脚本输出必须和去水市场赔率做 sanity check；当模型和市场明显分歧时，先查
缺失信息。

## Market-context pipeline / 市场上下文管线

Use this when the user wants to prepare, enrich, validate, or merge market
context data before it reaches the model.

中文：当用户需要准备、补全、验证或合并市场上下文数据时使用该管线。它只处理
数据输入，不改变核心模型默认值。

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

中文：6 月 26 日预测赛程保留在 `JUNE_26_MATCHES`；确认后的最终比分只填入
`JUNE_26_RESULTS`。在 6 场结果全部确认前，`MATCHES_66` 仍等同 60 场基线。

1. `python create_context_template.py --source jun25 --format csv` to generate a
   fillable template with `home`, `away`, `market_odds`, `market_confidence`,
   optional `competition_state`, and notes fields.
   Use `--source jun26` for the June 26 slate or `--source sf_jul14_15` for the
   semifinals. Semifinal templates also accept optional direct two-way
   `market_advance_odds`; their de-margin method is the row's `market_method`.
   Third-place/final schema-4 artifacts retain structured weather provenance in
   addition to direct-HTTP receipt provenance and signed model-minus-market gaps,
   and set a
   review flag at 4 points; the flag prompts investigation and never changes
   frozen parameters automatically.
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
Weather provenance is mandatory for current predictions, including no-adjustment
outdoor decisions. Historical replay may load legacy rows, but any asserted
weather override must still pass `validate_weather_context`.
Outdoor `api.weather.gov` evidence must retain both the points response and the
hourly response at its exact `properties.forecastHourly` URL, with matching
source fields, snapshots, and SHA-256 values. The points response `id` (or
`properties.@id`) must equal the declared points URL. Record
`weather_capture_method` as `direct_http_response_body` or
`workspace_web_fetch` exactly; case, whitespace, and hyphen aliases fail closed.
The latter is an auditable tool-text snapshot, not raw or byte-identical HTTP
response bytes.
Use hourly `properties.updateTime` as the sole issuance timestamp, record
`generatedAt` separately as `weather_forecast_generated_at_utc`, and require a
real period satisfying `startTime <= kickoff < endTime`. Caller-supplied
issue/valid timestamps must match the retained JSON; any mismatch fails closed.
For third-place/final artifacts, schema 4 verifies provenance and period
coverage; it does not infer a `heat_*` or `rain_*` decision from the forecast
values or change the frozen weather adjustment mapping. QF/SF artifacts remain
schema 3, including any compliant SF102 retry before kickoff.
Current Elo provenance is likewise mandatory for daily and official runs: use
the create-only direct-response capture and its receipt, never a copied or
reconstructed TSV. Unverified legacy input is replay-only and cannot enter an
official artifact or a current-data paper signal.
Before an official finalization, both `./run_tests.sh` and
`python3 -m pytest -q` must pass. The repository suite currently covers 12/12
standalone scripts through the pytest adapter; the packaged skill covers 10/10
because paper-ledger and release-tooling code/tests are intentionally
repository-only.

## Data sources

Market odds (Pinnacle, Betfair, Oddspedia, bet365) · Elo (eloratings.net) ·
results & xG (fbref, Opta/TheAnalyst, xgscore, footystats) · squads/injuries
(official, FourFourTwo, ESPN) · venue/altitude (StadiumDB) · weather
(AccuWeather, weather.com — match-day & kickoff hour). 2026: openfootball/worldcup.json.

## Constraints / 约束

- Show every formula and intermediate step — make it verifiable.
- Probabilities 1 decimal; odds 2 decimals.
- State assumptions when data is missing; never fabricate stats.
- Never recommend a bet or stake. Present probabilities, odds, and divergence
  only. Always include the educational-use disclaimer.

中文：列出公式和中间步骤；概率保留 1 位、赔率保留 2 位；缺数据必须写假设；
永远不推荐投注或下注金额，只展示概率、赔率和分歧。
