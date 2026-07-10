#!/usr/bin/env python3
"""Run the context import -> validation -> training -> prediction pipeline.

The default path is intentionally conservative:
  import CSV into JSON -> validate -> train the stable-profile report -> run
  the June 25 predictor with the training recommendation.

Market evaluation is optional and off by default so the core internal loop stays
decoupled from market-fit experiments.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from model_stability import resolve_profile


ROOT = Path(__file__).resolve().parent
TEMPLATE_SOURCES = ["jun25", "jun26", "qf_jul11", "stryktipset", "train", "validation", "locked_test", "all"]


def _script(name: str) -> Path:
    return ROOT / name


def _run_step(label: str, cmd: list[str]) -> subprocess.CompletedProcess[str]:
    print(f"\n==> {label}")
    print(f"    $ {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc


def _resolve_profile_name(raw: str) -> str:
    if raw == "auto":
        return "auto"
    return resolve_profile(raw).name


def _parse_training_recommendation(output: str) -> str:
    match = re.search(r"^Recommendation:\s+([^\s(]+)", output, flags=re.MULTILINE)
    if not match:
        return "stable_v35"
    return match.group(1)


def _temp_file_path(prefix: str, suffix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(prefix=prefix, suffix=suffix, delete=False)
    try:
        return Path(handle.name)
    finally:
        handle.close()


def _generate_fixture_csv(source: str) -> Path:
    output_csv = _temp_file_path(f"worldcup_{source}_", ".csv")
    cmd = [
        sys.executable,
        str(_script("create_context_template.py")),
        "--source",
        source,
        "--format",
        "csv",
        "--output",
        str(output_csv),
    ]
    _run_step("Generate fixture CSV", cmd)
    return output_csv


def _enrich_with_odds_api(
    fixture_csv: Path,
    *,
    fixture_json: str | None,
    api_key: str | None,
    sport_key: str | None,
    regions: str,
    markets: str,
    odds_format: str,
    date_format: str,
    bookmakers: str | None,
    api_base: str,
    timeout: int,
    cache_dir: str | None,
    cache_ttl_seconds: int,
    preferred_bookmakers: str | None,
) -> Path:
    output_csv = _temp_file_path(f"{fixture_csv.stem}.odds_", ".csv")
    cmd = [
        sys.executable,
        str(_script("fetch_the_odds_api.py")),
        "--fixture-csv",
        str(fixture_csv),
        "--output-csv",
        str(output_csv),
        "--regions",
        regions,
        "--markets",
        markets,
        "--odds-format",
        odds_format,
        "--date-format",
        date_format,
        "--api-base",
        api_base,
        "--timeout",
        str(timeout),
        "--cache-ttl-seconds",
        str(cache_ttl_seconds),
    ]
    if fixture_json:
        cmd.extend(["--fixture-json", fixture_json])
    else:
        if api_key:
            cmd.extend(["--api-key", api_key])
        if sport_key:
            cmd.extend(["--sport-key", sport_key])
    if bookmakers:
        cmd.extend(["--bookmakers", bookmakers])
    if cache_dir:
        cmd.extend(["--cache-dir", cache_dir])
    if preferred_bookmakers:
        cmd.extend(["--preferred-bookmakers", preferred_bookmakers])
    _run_step("Fetch Odds API data", cmd)
    return output_csv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-csv", help="CSV context file to import, or a template CSV for Odds API enrichment.")
    ap.add_argument(
        "--fixture-source",
        choices=TEMPLATE_SOURCES,
        help="Generate a template CSV with create_context_template.py before import.",
    )
    ap.add_argument("--base-json", help="Optional existing JSON context file to merge into.")
    ap.add_argument(
        "--output-json",
        help="Where to write the merged context JSON. Defaults to a temp file.",
    )
    ap.add_argument(
        "--source-label",
        help="Label stored in the merged JSON meta block; defaults to the input filename.",
    )
    ap.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Fail validation on warnings, not just errors.",
    )
    ap.add_argument(
        "--require-weather-evidence",
        action="store_true",
        help="Require complete matchday weather provenance on every row, including weather_scale=1.00.",
    )
    ap.add_argument(
        "--context-only",
        action="store_true",
        help="Stop after import and validation; do not train, evaluate, or run a predictor.",
    )
    ap.add_argument(
        "--bootstrap",
        type=int,
        default=200,
        help="Bootstrap iterations for the stable-profile report.",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for bootstrap selection rates.",
    )
    ap.add_argument(
        "--profile-set",
        choices=["core", "full"],
        default="core",
        help="Profile pool for the training report.",
    )
    ap.add_argument(
        "--prediction-profile",
        default="auto",
        help="Profile used for prediction. Use 'auto' to take the training recommendation.",
    )
    ap.add_argument(
        "--prediction-slate",
        choices=["auto", "jun25", "jun26"],
        default="auto",
        help="Prediction script to run after validation. qf_jul11 defaults to context-only validation.",
    )
    ap.add_argument(
        "--market-mode",
        choices=["none", "evaluate", "train"],
        default="none",
        help="Optional market branch: none, evaluate the supplied context, or train the blend weight.",
    )
    ap.add_argument(
        "--market-source",
        choices=["none", "odds-api"],
        default="none",
        help="Optional market ingestion step. odds-api enriches the CSV before import.",
    )
    ap.add_argument(
        "--odds-api-fixture-json",
        help="Recorded Odds API JSON payload for offline enrichment.",
    )
    ap.add_argument(
        "--odds-api-api-key",
        help="Odds API key for live enrichment. Defaults to ODDS_API_KEY / THE_ODDS_API_KEY / WORLD_CUP_2026_ODDS_API_KEY.",
    )
    ap.add_argument(
        "--odds-api-sport-key",
        help="Odds API sport key for live enrichment. Defaults to ODDS_API_SPORT_KEY / WORLD_CUP_2026_ODDS_API_SPORT_KEY.",
    )
    ap.add_argument("--odds-api-regions", default="us,uk,eu")
    ap.add_argument("--odds-api-markets", default="h2h")
    ap.add_argument("--odds-api-odds-format", default="decimal")
    ap.add_argument("--odds-api-date-format", default="iso")
    ap.add_argument("--odds-api-bookmakers", help="Comma-separated bookmaker filter for live Odds API calls.")
    ap.add_argument("--odds-api-api-base", default="https://api.the-odds-api.com/v4")
    ap.add_argument("--odds-api-timeout", type=int, default=30)
    ap.add_argument("--odds-api-cache-dir", help="Optional cache directory for live Odds API calls.")
    ap.add_argument(
        "--odds-api-cache-ttl-seconds",
        type=int,
        default=1800,
        help="Cache lifetime for live Odds API calls. Set to 0 to refresh every run.",
    )
    ap.add_argument(
        "--odds-api-preferred-bookmakers",
        default="pinnacle,bet365",
        help="Comma-separated bookmaker preference order for Odds API enrichment.",
    )
    ap.add_argument(
        "--market-split",
        choices=["train", "validation", "locked_test", "all"],
        default="validation",
        help="Split used by market evaluation when --market-mode=evaluate.",
    )
    args = ap.parse_args()

    if args.input_csv and args.fixture_source:
        ap.error("--input-csv and --fixture-source are mutually exclusive")
    if not args.input_csv and not args.fixture_source:
        ap.error("either --input-csv or --fixture-source is required")
    if args.fixture_source == "qf_jul11" and args.prediction_slate != "auto":
        ap.error("qf_jul11 cannot be handed to a June predictor; use --context-only")

    if args.fixture_source:
        source_csv = _generate_fixture_csv(args.fixture_source)
        source_label = args.source_label or (
            f"odds-api:{args.fixture_source}" if args.market_source == "odds-api" else f"template:{args.fixture_source}"
        )
        context_stem = args.fixture_source
    else:
        source_csv = Path(args.input_csv)
        source_label = args.source_label
        context_stem = source_csv.stem

    market_csv = source_csv
    if args.market_source == "odds-api":
        market_csv = _enrich_with_odds_api(
            source_csv,
            fixture_json=args.odds_api_fixture_json,
            api_key=args.odds_api_api_key,
            sport_key=args.odds_api_sport_key,
            regions=args.odds_api_regions,
            markets=args.odds_api_markets,
            odds_format=args.odds_api_odds_format,
            date_format=args.odds_api_date_format,
            bookmakers=args.odds_api_bookmakers,
            api_base=args.odds_api_api_base,
            timeout=args.odds_api_timeout,
            cache_dir=args.odds_api_cache_dir,
            cache_ttl_seconds=args.odds_api_cache_ttl_seconds,
            preferred_bookmakers=args.odds_api_preferred_bookmakers,
        )
        if source_label is None:
            source_label = f"odds-api:{context_stem}"

    output_json = Path(args.output_json) if args.output_json else Path(tempfile.gettempdir()) / f"{context_stem}.merged.json"

    import_cmd = [
        sys.executable,
        str(_script("import_context_csv.py")),
        "--input",
        str(market_csv),
        "--output",
        str(output_json),
    ]
    if args.base_json:
        import_cmd.extend(["--base-json", str(Path(args.base_json))])
    if args.source_label:
        import_cmd.extend(["--source-label", args.source_label])
    elif source_label:
        import_cmd.extend(["--source-label", source_label])
    _run_step("Import context CSV", import_cmd)

    validate_cmd = [
        sys.executable,
        str(_script("validate_context.py")),
        "--context-file",
        str(output_json),
    ]
    if args.fail_on_warning:
        validate_cmd.append("--fail-on-warning")
    if args.require_weather_evidence or args.fixture_source == "qf_jul11":
        validate_cmd.append("--require-weather-evidence")
    _run_step("Validate context JSON", validate_cmd)

    if args.context_only or args.fixture_source == "qf_jul11":
        print(f"\nContext validation complete: context_json={output_json}")
        print("Downstream training and prediction handoff skipped (context-only).")
        return

    prediction_slate = args.prediction_slate
    if prediction_slate == "auto":
        prediction_slate = "jun26" if args.fixture_source == "jun26" else "jun25"

    train_cmd = [
        sys.executable,
        str(_script("train_stable_profile.py")),
        "--context-file",
        str(output_json),
        "--bootstrap",
        str(args.bootstrap),
        "--seed",
        str(args.seed),
        "--profile-set",
        args.profile_set,
    ]
    train_proc = _run_step("Train stable profile", train_cmd)
    recommended_profile = _parse_training_recommendation(train_proc.stdout)
    if args.prediction_profile == "auto":
        try:
            prediction_profile = _resolve_profile_name(recommended_profile)
            profile_reason = "training recommendation"
        except Exception:
            prediction_profile = "stable_v35"
            profile_reason = f"training recommendation {recommended_profile!r} is not a registered runtime profile; fell back to stable_v35"
    else:
        try:
            prediction_profile = _resolve_profile_name(args.prediction_profile)
        except Exception as exc:
            ap.error(f"invalid --prediction-profile: {exc}")
        profile_reason = "explicit override"
    print(f"\nSelected prediction profile: {prediction_profile} ({profile_reason})")

    if args.market_mode != "none":
        market_cmd = [
            sys.executable,
            str(_script(
                "evaluate_market_context.py" if args.market_mode == "evaluate" else "train_market_blend.py"
            )),
            "--context-file",
            str(output_json),
            "--profile",
            prediction_profile,
        ]
        if args.market_mode == "evaluate":
            market_cmd.extend(["--split", args.market_split])
        _run_step(
            "Market evaluation" if args.market_mode == "evaluate" else "Market blend training",
            market_cmd,
        )

    predict_script = "predict_jun26.py" if prediction_slate == "jun26" else "predict_jun25.py"
    predict_label = "June 26" if prediction_slate == "jun26" else "June 25"
    predict_cmd = [
        sys.executable,
        str(_script(predict_script)),
        "--context-file",
        str(output_json),
        "--profile",
        prediction_profile,
    ]
    _run_step(f"Predict {predict_label} slate", predict_cmd)

    print(f"\nPipeline complete: context_json={output_json}")


if __name__ == "__main__":
    main()
