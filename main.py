import argparse
import logging
import sys

import config
from pipeline import run

def _setup_logging(level_name: str) -> None:
    """Configure root logger: coloured console output with timestamps."""
    numeric_level = getattr(logging, level_name.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Silence noisy third-party loggers
    for noisy_lib in ("urllib3", "requests", "charset_normalizer"):
        logging.getLogger(noisy_lib).setLevel(logging.WARNING)

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="coventry-scraper",
        description="Scrape structured course data from Coventry University.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --output results/my_courses.json
  python main.py --debug
        """,
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=config.OUTPUT_FILE,
        help=f"Path to write the JSON output (default: {config.OUTPUT_FILE})",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG-level logging (very verbose)",
    )
    return parser.parse_args()

def main() -> int:
    """
    Returns 0 on success, 1 on failure.
    """
    args = _parse_args()

    log_level = "DEBUG" if args.debug else config.LOG_LEVEL
    _setup_logging(log_level)

    logger = logging.getLogger(__name__)

    # Allow --output to override config at runtime
    if args.output != config.OUTPUT_FILE:
        config.OUTPUT_FILE = args.output
        logger.info("Output path overridden → %s", config.OUTPUT_FILE)

    try:
        records = run()
        logger.info(
            "Success — %d course records written to '%s'.",
            len(records),
            config.OUTPUT_FILE,
        )
        return 0

    except KeyboardInterrupt:
        logger.warning("Interrupted by user (Ctrl-C).")
        return 1

    except RuntimeError as exc:
        logger.error("Pipeline error: %s", exc)
        return 1

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
