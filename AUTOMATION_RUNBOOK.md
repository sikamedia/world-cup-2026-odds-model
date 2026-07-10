# Official Prediction Automation Runbook

This runbook defines the external scheduler contract for official match-day
predictions. The scheduler definition is not stored in this repository, so its
persistent prompt must be updated in the scheduling platform and verified from
a new isolated run.

## Persistent task body

Include this block verbatim in the scheduled task body:

```text
Elo source (fetch before every official prediction):
https://www.eloratings.net/World.tsv

Fetch and parse this source before producing official predictions. If fetch,
parse, freshness, source-integrity, or required-team validation fails, stop the
official prediction path. Do not substitute estimated Elo and do not publish a
single-point official probability.

Weather adjustments must use auditable kickoff-hour evidence. Heat evidence
must be checked within 6 hours of kickoff. Applied rain requires hourly or
radar evidence checked within 3 hours of kickoff. Evidence timestamps must not
be later than the current run, and finalization must finish before kickoff. If
weather validation fails, stop the official prediction path.
```

The URL appearing in a report or an interactive conversation does not update
the scheduler's persistent provenance set.

## July 11 finalization schedule

- Keep the `07:00 UTC` run as preview-only. It must not finalize weather.
- Run Norway vs England finalization at `2026-07-11 18:05 UTC`, for the
  `21:00 UTC` kickoff.
- Run Argentina vs Switzerland finalization at `2026-07-11 22:05 UTC`, for the
  `2026-07-12 01:00 UTC` kickoff.
- Fetch a fresh `World.tsv` in each isolated finalization run.
- After the second artifact exists, run the artifact MC. It may run while the
  first QF is in progress because it never reads or incorporates live match
  state and never recalculates either QF probability.

## Repository handoff

For each finalization run:

1. Save the raw Elo response as a timestamped TSV evidence file.
2. Record the actual response-download time. Parse it with
   `fetch_elo_current.py --fetched-at-utc`; parser execution time is not a
   substitute for download time.
3. Generate a one-fixture `qf_jul11` context template, populate market and
   weather evidence, and retain the referenced evidence snapshots.
4. Run `validate_context.py`; any error blocks prediction.
5. Run `predict_jul11.py finalize`. It validates only the selected fixture and
   creates a read-only artifact at a new path. Existing artifacts are never
   overwritten.

Norway vs England example (replace the illustrative fetch timestamp with the
actual response-download time):

```bash
python3 fetch_elo_current.py \
  --tsv evidence/World_20260711T1805Z.tsv \
  --fetched-at-utc 2026-07-11T18:04:30Z \
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
  --context-file /tmp/qf99.json \
  --artifact-out evidence/qf99_20260711T1805Z.final.json
```

Argentina vs Switzerland uses the same flow in its own isolated run:

```bash
python3 fetch_elo_current.py \
  --tsv evidence/World_20260711T2205Z.tsv \
  --fetched-at-utc 2026-07-11T22:04:30Z \
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
  --context-file /tmp/qf100.json \
  --artifact-out evidence/qf100_20260711T2205Z.final.json
```

The MC takes both artifacts and a separately refreshed Elo snapshot for future
SF/final pairings only:

```bash
python3 fetch_elo_current.py \
  --tsv evidence/World_20260711T2210Z.tsv \
  --fetched-at-utc 2026-07-11T22:09:30Z \
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
  --qf98-winner Spain
```

Replace `Spain` with `Belgium` in both MC required-team validation and
`--qf98-winner` when Belgium wins QF98.

## Artifact trust boundary

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
- The Elo snapshot has a timezone-aware fetch time and a matching SHA-256 of
  the retained raw response; required-team ratings also match a fresh parse of
  that response.
- Every participating team is present and none is listed in `ESTIMATES`.
- Outdoor matches have retained kickoff-hour weather evidence with a matching
  SHA-256 and forecast-valid time.
- Finalization happens before kickoff, evidence timestamps are not later than
  the run time, and the official output uses frozen `w=0.6` model / `0.4`
  market probabilities.
- Each QF artifact has a verified canonical payload SHA-256 and was generated
  before its exact fixture kickoff. Artifact paths are create-only.
- MC consumes the two stored official QF advancement probabilities without
  recalculating or republishing them. Fresh Elo is used only for future rounds,
  and the output states that live match state is not incorporated.
- Injecting a stale Elo snapshot or stale weather evidence exits non-zero and
  produces no official probability output.

Run acceptance from a newly started scheduled task. Testing in the interactive
session that supplied the URL is not valid evidence that persistent provenance
was fixed.
