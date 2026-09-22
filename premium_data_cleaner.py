#!/usr/bin/env python3
"""
clean_data.py - Clean a messy CSV or Excel file.
Features:
    • Detect input format (CSV or Excel) and load with pandas.
    • Remove duplicate rows (all columns by default).
    • Detect columns that contain dates (>= 50% parsable) and standardize them to ISO format.
    • Save the cleaned data back to CSV (default) or Excel (if original was Excel).

Usage:
    python clean_data.py --input raw_data.csv --output cleaned_data.csv
    python clean_data.py -i raw_data.xlsx -o cleaned_data.xlsx
"""

import argparse
import os
import sys
import pandas as pd
from pandas.api.types import is_string_dtype, is_numeric_dtype

DATE_PARSE_THRESHOLD = 0.5  # Minimum fraction of non‑NA values that must be parseable as dates


def infer_date_columns(df: pd.DataFrame) -> list:
    """
    Return a list of column names that look like dates.
    Heuristic: column is string/object dtype and at least DATE_PARSE_THRESHOLD of
    its non‑NA values can be parsed by pd.to_datetime.
    """
    date_cols = []
    for col in df.columns:
        if is_string_dtype(df[col]) and not is_numeric_dtype(df[col]):
            sample = df[col].dropna().astype(str)
            if sample.empty:
                continue
            # Try to parse; coerce errors to NaT
            parsed = pd.to_datetime(sample, errors='coerce', infer_datetime_format=True)
            success_ratio = parsed.notna().mean()
            if success_ratio >= DATE_PARSE_THRESHOLD:
                date_cols.append(col)
    return date_cols


def clean_file(input_path: str, output_path: str) -> None:
    # Detect file type
    _, ext = os.path.splitext(input_path.lower())
    if ext in {".xlsx", ".xls"}:
        df = pd.read_excel(input_path, engine="openpyxl")
        original_is_excel = True
    elif ext == ".csv":
        df = pd.read_csv(input_path, dtype=str, keep_default_na=False, na_values=[""])
        original_is_excel = False
    else:
        sys.exit(f"Unsupported file extension '{ext}'. Use .csv, .xlsx or .xls")

    # Remove exact duplicate rows
    df_before = len(df)
    df = df.drop_duplicates(ignore_index=True)
    df_after = len(df)

    # Identify and fix date columns
    date_columns = infer_date_columns(df)
    for col in date_columns:
        df[col] = pd.to_datetime(df[col], errors='coerce', infer_datetime_format=True).dt.strftime('%Y-%m-%d')

    # Save cleaned data
    if original_is_excel or output_path.lower().endswith(('.xlsx', '.xls')):
        df.to_excel(output_path, index=False, engine="openpyxl")
    else:
        df.to_csv(output_path, index=False)

    print(f"Cleaned file saved to: {output_path}")
    print(f"Rows before duplicate removal: {df_before}, after: {df_after}")
    if date_columns:
        print(f"Standardized date columns: {', '.join(date_columns)}")
    else:
        print("No date columns detected.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean CSV/Excel files: deduplicate rows and normalize dates.")
    parser.add_argument("-i", "--input", required=True, help="Path to the messy CSV or Excel file.")
    parser.add_argument("-o", "--output", required=False, help="Path for the cleaned output file. "
                        "If omitted, '<input>_cleaned.<ext>' will be used.")
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = args.input
    if not os.path.isfile(input_path):
        sys.exit(f"Input file not found: {input_path}")

    if args.output:
        output_path = args.output
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_cleaned{ext}"

    clean_file(input_path, output_path)


if __name__ == "__main__":
    main()