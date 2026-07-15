# Official Prediction Automation Runbook

This runbook defines the external scheduler contract for official match-day
predictions. The scheduler definition is not stored in this repository, so its
persistent prompt must be updated in the scheduling platform and verified from
a new isolated run.

## Persistent task body

Include this block verbatim in the scheduled task body:

```text
Elo source (fetch before every daily preview and official prediction):
https://www.eloratings.net/World.tsv

Fetch this source through capture_elo_evidence.py before every daily preview and
official prediction. The HTTP response body must be written directly and
unmodified to a new create-only timestamped TSV; record the response-completion
time, byte count, and SHA-256 in its create-only receipt. Do not copy or reuse a
prior TSV, reconstruct it from parsed data, transcode it, or normalize its
newlines. Parse only the TSV/receipt pair produced by that capture.

If capture, receipt, parse, freshness, source-integrity, or required-team
validation fails, stop the Elo path. A daily run must not produce an Elo-based
preview. An official run must not publish a single-point probability. Official
finalization requires the response-completion time to be no more than 30
minutes old. Do not substitute estimated Elo or relax this age limit.

Weather adjustments must use auditable kickoff-hour evidence. Heat evidence
must be checked within 6 hours of kickoff. Applied rain requires hourly or
radar evidence checked within 3 hours of kickoff. Evidence timestamps must not
be later than the current run, and finalization must finish before kickoff. If
weather validation fails, stop the official prediction path.

Do not infer indoor conditions from a retractable-roof venue. A
weather_decision=indoor_no_weather decision requires a retained, match-specific
weather_evidence_type=official_roof HTTP(S) source that explicitly confirms the
roof will be closed, including roof_status=closed, the selected fixture's exact
weather_evidence_fixture_id, snapshot, SHA-256, source URL, and a check within
6 hours of kickoff. Without that confirmation, use the outdoor kickoff-hour
weather path and fail closed if it cannot be validated.

Weather evidence source policy (adopted 2026-07-15, user-directed): the PRIMARY
outdoor-forecast source is the api.weather.gov JSON API, NOT the
forecast.weather.gov HTML pages. Procedure: fetch
https://api.weather.gov/points/{lat},{lon} for the venue, follow the exact
`properties.forecastHourly` URL from that live response (never guess gridpoint
numbers), select the kickoff-hour period, retain both the points and hourly
snapshots under evidence/, and record the hourly snapshot SHA-256 as
weather_evidence_sha256. Direct HTTP may retain response bytes; workspace
web_fetch retains the exact tool snapshot and must not be described as raw or
verbatim HTTP response bytes. Set `weather_forecast_issued_at_utc` only from
the hourly JSON's `properties.updateTime`. Record `properties.generatedAt`
separately as response generation metadata; it is not the forecast issue time
and must never make an old `updateTime` appear fresh. Rationale (2026-07-15 daily findings):
forecast.weather.gov HTML pages arrive as STALE CACHES through the sandbox proxy
(June issuances observed on match day) and must be rejected by the ≤24h
issue-time check; the JSON API exposes `updateTime` so staleness is auditable.
Transport: prefer in-process HTTP capture; if the
sandbox allowlist blocks api.weather.gov (403 blocked-by-allowlist, observed
2026-07-15 07:05Z), the workspace web_fetch tool is acceptable FOR THE WEATHER
PATH ONLY — the weather contract requires an auditable snapshot + SHA-256 +
fresh timestamps, not the Elo-grade direct-capture receipt; the URL must be
present in the scheduled task body for web_fetch provenance (same fix as the
World.tsv task-body URL). Elo remains direct-capture-only; web_fetch can never
satisfy the Elo contract.
```

The URL appearing in a report or an interactive conversation does not update
the scheduler's persistent provenance set.

## July 11 finalization incident (historical)

- The intended plan kept the `07:00 UTC` run preview-only.
- Norway vs England was due to finalize at `2026-07-11 18:05 UTC`, for the
  `21:00 UTC` kickoff.
- Argentina vs Switzerland was due to finalize at `2026-07-11 22:05 UTC`, for
  the `2026-07-12 01:00 UTC` kickoff.
- Each isolated run was required to fetch a fresh `World.tsv`.
- The intended artifact MC could run after the second artifact existed, even
  while the first QF was in progress, because it never reads or incorporates
  live match state and never recalculates either QF probability.

Neither isolated finalization actually ran and neither official QF artifact
exists. The settled ledger rows therefore retain their 07:00 preview values and
disclose that basis. This section is retained as an incident record, not as an
active schedule.

## Semifinal finalization schedule

Keep the daily `07:00 UTC` task preview-only. Create and verify these as two
separate one-time scheduler tasks:

| Task ID | Fixture and kickoff | Run time | One-time `fireAt` |
|---|---|---|---|
| `sf101_france_spain_final` | France vs Spain, `2026-07-14 19:00 UTC` | `2026-07-14 16:05 UTC` | `2026-07-14T18:05:00+02:00` |
| `sf102_england_argentina_final` | England vs Argentina, `2026-07-15 19:00 UTC` | `2026-07-15 16:05 UTC` | `2026-07-15T18:05:00+02:00` |

Use the scheduler's native one-time `fireAt`, not a recurring cron expression;
the task must auto-disable after firing. Its UI/metadata must show the exact task
ID, timestamp with the `+02:00` Europe/Stockholm offset, enabled state, selected
repository folder, completion notification, and web-fetch permission. Keep the
desktop scheduler open, online, and the host awake through both windows. A
missed task may run when the app next starts, so the pre-kickoff guard remains
mandatory and a post-kickoff retry must fail closed.

Each task body must include the persistent block above verbatim, so the literal
`https://www.eloratings.net/World.tsv` enters that task's provenance set. It
must also state its fixed fixture, kickoff, scheduled run time, evidence paths,
context/validation/finalize commands, and every fail-closed condition. A runbook
entry alone does not create a scheduler task. New tasks do not inherit the daily
task's permissions: pre-authorize network execution of
`python3 capture_elo_evidence.py` to `https://www.eloratings.net` for each task.
Generic browser/web-fetch permission does not prove that the scheduled Python
process has egress. Verify the exact capture command from a new isolated task
before match day so an unattended approval prompt or proxy allowlist cannot
block the run. Create tasks through the official scheduler UI/API; never edit
its internal JSON storage by hand.

Elo and weather egress are independent permissions. Pre-authorizing
`python3 capture_elo_evidence.py` for `www.eloratings.net` does not authorize
`api.weather.gov`, and a successful request to either host does not prove access
to the other. Verify each required host from the scheduled-task environment and
retain the scheduler execution log; an interactive-session request is not a
substitute.

## Repository handoff

For each finalization run:

1. Run `capture_elo_evidence.py` to write the direct, unmodified HTTP response
   bytes to a new timestamped TSV and its matching create-only receipt. The
   capture is the only supported current-data acquisition path; never copy,
   reuse, reconstruct, transcode, or normalize an evidence file.
2. Parse that exact TSV/receipt pair with `fetch_elo_current.py --receipt`. The
   receipt's response-completion time is authoritative; parser execution time
   and caller-supplied timestamps are not substitutes.
3. Generate the fixture's one-match context template (`sf_jul14_15` for the
   semifinals), populate market and weather evidence, and retain every
   referenced evidence snapshot. Prefer a direct two-way advancement market;
   if it is unavailable, retain the 90-minute 1X2 market used by the documented
   draw-resolution fallback.
4. Run `validate_context.py`; any error blocks prediction.
5. Run both `./run_tests.sh` and `python3 -m pytest -q`. Any failure blocks the
   official prediction path.
6. Run `predict_jul11.py finalize`. It validates only the selected fixture and
   creates a read-only artifact at a new path. Existing artifacts are never
   overwritten.

France vs Spain example (use new output paths for every attempt and populate the
context before validation):

```bash
python3 capture_elo_evidence.py \
  --tsv-out evidence/World_20260714T1605Z.tsv \
  --receipt-out evidence/World_20260714T1605Z.receipt.json \
  --timeout-seconds 30

python3 fetch_elo_current.py \
  --tsv evidence/World_20260714T1605Z.tsv \
  --receipt evidence/World_20260714T1605Z.receipt.json \
  --out elo_sf101.py \
  --required-team France \
  --required-team Spain

python3 create_context_template.py \
  --source sf_jul14_15 \
  --fixture france-spain \
  --format csv \
  --output /tmp/sf101.csv

# Populate market evidence and either outdoor weather evidence or the exact
# roof_status=closed / weather_evidence_fixture_id=2026-SF101-France-Spain
# official-roof evidence in /tmp/sf101.csv first.
python3 run_context_pipeline.py \
  --input-csv /tmp/sf101.csv \
  --output-json /tmp/sf101.json \
  --require-weather-evidence \
  --context-only

python3 validate_context.py \
  --context-file /tmp/sf101.json \
  --require-weather-evidence

./run_tests.sh
python3 -m pytest -q

python3 predict_jul11.py finalize \
  --fixture france-spain \
  --elo-module elo_sf101.py \
  --elo-source-tsv evidence/World_20260714T1605Z.tsv \
  --elo-receipt evidence/World_20260714T1605Z.receipt.json \
  --context-file /tmp/sf101.json \
  --artifact-out evidence/sf101_20260714T1605Z.final.json
```

England vs Argentina uses the same isolated flow on July 15:

```bash
python3 capture_elo_evidence.py \
  --tsv-out evidence/World_20260715T1605Z.tsv \
  --receipt-out evidence/World_20260715T1605Z.receipt.json \
  --timeout-seconds 30

python3 fetch_elo_current.py \
  --tsv evidence/World_20260715T1605Z.tsv \
  --receipt evidence/World_20260715T1605Z.receipt.json \
  --out elo_sf102.py \
  --required-team England \
  --required-team Argentina

python3 create_context_template.py \
  --source sf_jul14_15 \
  --fixture england-argentina \
  --format csv \
  --output /tmp/sf102.csv

# Populate market evidence and either outdoor weather evidence or the exact
# roof_status=closed / weather_evidence_fixture_id=2026-SF102-England-Argentina
# official-roof evidence in /tmp/sf102.csv first.
python3 run_context_pipeline.py \
  --input-csv /tmp/sf102.csv \
  --output-json /tmp/sf102.json \
  --require-weather-evidence \
  --context-only

python3 validate_context.py \
  --context-file /tmp/sf102.json \
  --require-weather-evidence

./run_tests.sh
python3 -m pytest -q

python3 predict_jul11.py finalize \
  --fixture england-argentina \
  --elo-module elo_sf102.py \
  --elo-source-tsv evidence/World_20260715T1605Z.tsv \
  --elo-receipt evidence/World_20260715T1605Z.receipt.json \
  --context-file /tmp/sf102.json \
  --artifact-out evidence/sf102_20260715T1605Z.final.json
```

The July 11 QF commands below are retained for audit and replay only.

Norway vs England example (counterfactual direct-capture flow; a post-kickoff
execution remains replay-only and cannot create an official artifact):

```bash
python3 capture_elo_evidence.py \
  --tsv-out evidence/World_20260711T1805Z.tsv \
  --receipt-out evidence/World_20260711T1805Z.receipt.json \
  --timeout-seconds 30

python3 fetch_elo_current.py \
  --tsv evidence/World_20260711T1805Z.tsv \
  --receipt evidence/World_20260711T1805Z.receipt.json \
  --out elo_qf99.py \
  --required-team Norway \
  --required-team England

python3 create_context_template.py \
  --source qf_jul11 \
  --fixture norway-england \
  --format csv \
  --output /tmp/qf99.csv

# Populate market and weather evidence in /tmp/qf99.csv first.
python3 run_context_pipeline.py \
  --input-csv /tmp/qf99.csv \
  --output-json /tmp/qf99.json \
  --require-weather-evidence \
  --context-only

python3 predict_jul11.py finalize \
  --fixture norway-england \
  --elo-module elo_qf99.py \
  --elo-source-tsv evidence/World_20260711T1805Z.tsv \
  --elo-receipt evidence/World_20260711T1805Z.receipt.json \
  --context-file /tmp/qf99.json \
  --artifact-out evidence/qf99_20260711T1805Z.final.json
```

Argentina vs Switzerland uses the same flow in its own isolated run:

```bash
python3 capture_elo_evidence.py \
  --tsv-out evidence/World_20260711T2205Z.tsv \
  --receipt-out evidence/World_20260711T2205Z.receipt.json \
  --timeout-seconds 30

python3 fetch_elo_current.py \
  --tsv evidence/World_20260711T2205Z.tsv \
  --receipt evidence/World_20260711T2205Z.receipt.json \
  --out elo_qf100.py \
  --required-team Argentina \
  --required-team Switzerland

python3 create_context_template.py \
  --source qf_jul11 \
  --fixture argentina-switzerland \
  --format csv \
  --output /tmp/qf100.csv

# Populate market and weather evidence in /tmp/qf100.csv first.
python3 run_context_pipeline.py \
  --input-csv /tmp/qf100.csv \
  --output-json /tmp/qf100.json \
  --require-weather-evidence \
  --context-only

python3 predict_jul11.py finalize \
  --fixture argentina-switzerland \
  --elo-module elo_qf100.py \
  --elo-source-tsv evidence/World_20260711T2205Z.tsv \
  --elo-receipt evidence/World_20260711T2205Z.receipt.json \
  --context-file /tmp/qf100.json \
  --artifact-out evidence/qf100_20260711T2205Z.final.json
```

The MC takes both artifacts and a separately refreshed Elo snapshot for future
SF/final pairings only:

```bash
python3 capture_elo_evidence.py \
  --tsv-out evidence/World_20260711T2210Z.tsv \
  --receipt-out evidence/World_20260711T2210Z.receipt.json \
  --timeout-seconds 30

python3 fetch_elo_current.py \
  --tsv evidence/World_20260711T2210Z.tsv \
  --receipt evidence/World_20260711T2210Z.receipt.json \
  --out elo_mc.py \
  --required-team France \
  --required-team Spain \
  --required-team Norway \
  --required-team England \
  --required-team Argentina \
  --required-team Switzerland

python3 predict_jul11.py mc \
  --artifacts evidence/qf99_20260711T1805Z.final.json \
              evidence/qf100_20260711T2205Z.final.json \
  --elo-module elo_mc.py \
  --elo-source-tsv evidence/World_20260711T2210Z.tsv \
  --elo-receipt evidence/World_20260711T2210Z.receipt.json \
  --qf98-winner Spain
```

Replace `Spain` with `Belgium` in both MC required-team validation and
`--qf98-winner` when Belgium wins QF98.

## Artifact trust boundary

The Elo receipt is a local, unsigned audit binding. It closes the accidental
copy/re-stamp path by binding the response time, evidence basename, byte count,
and body digest, but it cannot prove authenticity against an operator who can
forge or copy the same-named TSV and receipt together. Stronger adversarial
assurance requires a signed scheduler attestation or an externally retained
append-only/WORM capture log.

The artifact payload SHA-256 detects accidental edits, and the runner creates
the local path once with read-only permissions. It is not a digital signature:
a user who can rewrite files and commands can also create a newly sealed
payload. For audit-grade authenticity, retain each finalize run's printed
`payload_sha256` in the scheduler's append-only execution log or external WORM
storage, then compare that trusted value before MC. Do not derive the trusted
digest from the artifact being checked.

## Acceptance criteria

An official run is valid only when all of the following are true:

- `SOURCE` is exactly `https://www.eloratings.net/World.tsv`.
- The Elo evidence is a new create-only file containing the direct, unmodified
  HTTP response body; its receipt records
  `capture_method=direct_http_response_body`, the response-completion time,
  byte count, and matching SHA-256. The operator must not supply a copied,
  reconstructed, transcoded, newline-normalized, or reused TSV; the unsigned
  receipt's non-adversarial enforcement boundary is documented above.
- The receipt is no more than 30 minutes old at official finalization. The Elo
  module matches the receipt and retained response, and required-team ratings
  match a fresh parse of those bytes.
- Every participating team is present and none is listed in `ESTIMATES`.
- `indoor_no_weather` is used only with retained match-specific
  `official_roof` HTTP(S) evidence checked within six hours that explicitly
  confirms roof closure, records `roof_status=closed`, and matches the selected
  `weather_evidence_fixture_id`. A retractable-roof venue without that
  confirmation follows the outdoor path.
- Outdoor matches have retained kickoff-hour weather evidence with a matching
  SHA-256 and forecast-valid time.
- Finalization happens before kickoff, evidence timestamps are not later than
  the run time, and the official output uses frozen `w=0.6` model / `0.4`
  market probabilities.
- A direct two-way advancement market is preferred and recorded as
  `direct_two_way`. When it is absent, the runner may derive the market
  advancement probability from a valid 90-minute 1X2 market and must record
  `derived_from_90`; missing usable market inputs block finalization.
- The artifact records signed model-minus-market gaps for 90-minute outcomes
  and advancement. Any absolute gap at or above 4 points sets
  `review_required=true` and must be surfaced in the run report; it is an
  investigation flag, not permission to change frozen parameters.
- Each new official artifact uses schema 3 / `pre_registered_match_prediction`,
  records `provenance_contract=direct_http_v1`, the receipt identity, its stage,
  and a verified canonical payload SHA-256, and was generated before its exact
  fixture kickoff. Artifact paths are create-only; the reader remains compatible
  with historical schema 1 and schema 2 artifacts.
- MC consumes the two stored official QF advancement probabilities without
  recalculating or republishing them. Fresh Elo is used only for future rounds,
  and the output states that live match state is not incorporated.
- Before finalization, `./run_tests.sh` and `python3 -m pytest -q` both pass.
- A failed capture, missing/invalid receipt, a receipt bound to another evidence
  file, evidence/receipt/module mismatch, Elo older than 30 minutes, estimated
  Elo, missing required teams or market inputs, missing/invalid roof evidence,
  stale weather, future evidence
  timestamps, an at-or-after-kickoff run time, or an existing artifact path
  exits non-zero and produces no official probability output.

Run acceptance from a newly started scheduled task. Testing in the interactive
session that supplied the URL is not valid evidence that persistent provenance
was fixed.
