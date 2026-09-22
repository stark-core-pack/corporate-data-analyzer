```python
#!/usr/bin/env python3
"""
clean_csv.py

Read a CSV file, normalize date columns, remove duplicate rows,
and write the cleaned data to a new CSV file.

Usage:
    python clean_csv.py -i input.csv -o output.csv [options]

Options:
    -d, --date-cols COLS   Comma‑separated list of columns to treat as dates.
    -k, --keep KEEP        Which duplicate to keep: 'first' (default) or 'last'.
    -e, --encoding ENC     File encoding (default: 'utf-8').
    -v, --verbose          Enable verbose logging.
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean a messy CSV file.")
    parser.add_argument("-i", "--input", required=True, help="Path to input CSV file.")
    parser.add_argument("-o", "--output", required=True, help="Path to output CSV file.")
    parser.add_argument(
        "-d",
        "--date-cols",
        default="",
        help="Comma‑separated list of columns to parse as dates.",
    )
    parser.add_argument(
        "-k",
        "--keep",
        choices=["first", "last"],
        default="first",
        help="Which duplicate to keep (default: first).",
    )
    parser.add_argument(
        "-e",
        "--encoding",
        default="utf-8",
        help="File encoding (default: utf-8).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output.")
    return parser.parse_args()


def load_csv(path: Path, encoding: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, encoding=encoding, low_memory=False, dtype=str)
        logging.info("Loaded %d rows and %d columns from %s", len(df), len(df.columns), path)
        return df
    except Exception as exc:
        logging.error("Failed to read CSV file %s: %s", path, exc)
        sys.exit(1)


def infer_date_columns(df: pd.DataFrame, sample_size: int = 100) -> list:
    date_cols = []
    for col in df.select_dtypes(include=["object"]).columns:
        sample = df[col].dropna().sample(min(sample_size, df[col].dropna().shape[0]), random_state=0)
        try:
            parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True, dayfirst=False)
            success_rate = parsed.notna().mean()
            if success_rate > 0.7:
                date_cols.append(col)
                logging.debug("Column '%s' inferred as date (%.0f%% parsable).", col, success_rate * 100)
        except Exception:
            continue
    return date_cols


def parse_dates(df: pd.DataFrame, date_cols: list) -> pd.DataFrame:
    for col in date_cols:
        try:
            df[col] = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True, dayfirst=False)
            num_invalid = df[col].isna().sum()
            logging.info(
                "Parsed column '%s' as dates. %d invalid / %d total entries.",
                col,
                num_invalid,
                len(df),
            )
        except Exception as exc:
            logging.warning("Failed to parse dates in column '%s': %s", col, exc)
    return df


def remove_duplicates(df: pd.DataFrame, keep: str) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(keep=keep)
    after = len(df)
    logging.info("Removed %d duplicate rows (kept %s).", before - after, keep)
    return df


def write_csv(df: pd.DataFrame, path: Path, encoding: str) -> None:
    try:
        df.to_csv(path, index=False, encoding=encoding)
        logging.info("Wrote cleaned data to %s (%d rows).", path, len(df))
    except Exception as exc:
        logging.error("Failed to write CSV file %s: %s", path, exc)
        sys.exit(1)


def main() -> None:
    args = parse_arguments()
    configure_logging(args.verbose)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.is_file():
        logging.error("Input file does not exist: %s", input_path)
        sys.exit(1)

    df = load_csv(input_path, args.encoding)

    # Determine which columns to treat as dates
    if args.date_cols:
        date_columns = [c.strip() for c in args.date_cols.split(",") if c.strip()]
        missing = set(date_columns) - set(df.columns)
        if missing:
            logging.error("Specified date columns not found in CSV: %s", ", ".join(missing))
            sys.exit(1)
    else:
        date_columns = infer_date_columns(df)
        logging.info("Auto‑detected date columns: %s", ", ".join(date_columns) or "none")

    df = parse_dates(df, date_columns)
    df = remove_duplicates(df, args.keep)
    write_csv(df, output_path, args.encoding)


if __name__ == "__main__":
    main()
```