"""Command-line interface for acquisition, analysis, and publishing."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from campaign_uplift.acquire import download_dataset, validate_archive
from campaign_uplift.config import DEFAULT_DATA_PATH, PipelineConfig
from campaign_uplift.data import sample_gzip_csv
from campaign_uplift.pipeline import run_analysis, write_results
from campaign_uplift.publish import build_site, validate_site
from campaign_uplift.synthetic import make_synthetic_uplift_data


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="campaign-uplift",
        description="Reproducible causal campaign targeting analysis.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    acquire = subparsers.add_parser("acquire", help="Download and validate Criteo v2.1.")
    acquire.add_argument("--destination", type=Path, default=DEFAULT_DATA_PATH)
    acquire.add_argument("--force", action="store_true")

    run = subparsers.add_parser("run", help="Run model selection and evaluation.")
    run.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    run.add_argument("--sample-fraction", type=float, default=0.10)
    run.add_argument("--artifact-dir", type=Path, default=Path("artifacts"))
    run.add_argument("--seed", type=int, default=20261120)
    run.add_argument("--smoke", action="store_true", help="Run a fast real-data pipeline check.")
    run.add_argument(
        "--synthetic",
        action="store_true",
        help="Use clearly labeled synthetic development data instead of Criteo.",
    )
    run.add_argument("--synthetic-rows", type=int, default=30_000)
    run.add_argument("--build-site", action="store_true")

    publish = subparsers.add_parser("build-site", help="Update the static site data artifact.")
    publish.add_argument("--result-path", type=Path, default=Path("artifacts/results.json"))
    publish.add_argument("--site-dir", type=Path, default=Path("site"))

    validate = subparsers.add_parser("validate-site", help="Validate the Pages payload.")
    validate.add_argument("--site-dir", type=Path, default=Path("site"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "acquire":
        metadata = download_dataset(args.destination, force=args.force)
        print(json.dumps(metadata, indent=2))
        return 0

    if args.command == "run":
        config = PipelineConfig(seed=args.seed, sample_fraction=args.sample_fraction)
        artifact_dir = args.artifact_dir
        if args.smoke:
            config = replace(
                config,
                sample_fraction=min(args.sample_fraction, 0.005),
                max_boost_iterations=35,
                min_samples_leaf=40,
            )
            if artifact_dir == Path("artifacts"):
                artifact_dir = Path("artifacts/smoke")
        if args.synthetic:
            frame = make_synthetic_uplift_data(args.synthetic_rows, args.seed)
            source_metadata: dict[str, object] = {
                "source_type": "synthetic_development",
                "rows_scanned": len(frame),
                "rows_sampled": len(frame),
                "requested_sample_fraction": 1.0,
                "realized_sample_fraction": 1.0,
            }
        else:
            if not args.data_path.exists():
                raise FileNotFoundError(
                    f"{args.data_path} does not exist. Run `campaign-uplift acquire` first."
                )
            archive = validate_archive(args.data_path)
            frame, sample_metadata = sample_gzip_csv(
                args.data_path,
                fraction=config.sample_fraction,
                seed=config.seed,
                chunk_size=config.chunk_size,
            )
            source_metadata = {
                "source_type": "real_criteo",
                **archive,
                **sample_metadata,
            }
        results = run_analysis(frame, source_metadata=source_metadata, config=config)
        result_path, memo_path = write_results(results, artifact_dir)
        if args.build_site:
            build_site(result_path)
        print(f"Wrote {result_path} and {memo_path}")
        return 0

    if args.command == "build-site":
        print(build_site(args.result_path, args.site_dir))
        return 0

    if args.command == "validate-site":
        validate_site(args.site_dir)
        print("Static site validation passed.")
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")
