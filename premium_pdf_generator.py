#!/usr/bin/env python3
"""
Invoice Generator
-----------------
Read a transaction log (CSV) and produce a PDF invoice using ReportLab.

Usage:
    python3 invoice_generator.py \
        --log transactions.csv \
        --output invoice_001.pdf \
        --invoice-number 001 \
        --date 2023-09-30 \
        --company-name "Acme Corp" \
        --company-address "123 Business Rd\nSuite 456\nMetropolis, NY 10101" \
        --client-name "John Doe" \
        --client-address "789 Client St\nApt 12\nGotham, CA 90210"
"""

import argparse
import csv
import sys
import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether,
)


def money(value):
    """Format a Decimal as currency."""
    return f"${value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,}"


def read_transactions(csv_path):
    """Read CSV file and return list of item dicts."""
    items = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                qty = Decimal(row["quantity"])
                unit_price = Decimal(row["unit_price"])
                total = qty * unit_price
                items.append(
                    {
                        "description": row["description"],
                        "quantity": qty,
                        "unit_price": unit_price,
                        "total": total,
                    }
                )
            except Exception as e:
                print(f"Skipping malformed row {row}: {e}", file=sys.stderr)
    return items


def build_invoice(args):
    # Document setup
    doc = SimpleDocTemplate(
        args.output,
        pagesize=LETTER,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    bold = ParagraphStyle(name="Bold", parent=normal, fontName="Helvetica-Bold")
    right = ParagraphStyle(name="Right", parent=normal, alignment=2)

    flow = []

    # Header (Company & Client Info)
    header_data = [
        [
            Paragraph(f"<b>{args.company_name}</b>", bold),
            "",
        ],
        [
            Paragraph(args.company_address.replace("\n", "<br/>"), normal),
            Paragraph(f"<b>Invoice #: </b>{args.invoice_number}<br/><b>Date: </b>{args.date}", normal),
        ],
        [
            Spacer(1, 12),
            Spacer(1, 12),
        ],
        [
            Paragraph(f"<b>Bill To:</b><br/>{args.client_name}<br/>{args.client_address.replace('\n','<br/>')}", normal),
            "",
        ],
    ]
    table = Table(header_data, colWidths=[doc.width * 0.6, doc.width * 0.4])
    flow.append(table)
    flow.append(Spacer(1, 24))

    # Items Table
    items = read_transactions(args.log)
    if not items:
        print("No items found in the transaction log.", file=sys.stderr)
        sys.exit(1)

    data = [
        [
            Paragraph("<b>Description</b>", bold),
            Paragraph("<b>Qty</b>", bold),
            Paragraph("<b>Unit Price</b>", bold),
            Paragraph("<b>Total</b>", bold),
        ]
    ]
    subtotal = Decimal("0")
    for it in items:
        data.append(
            [
                Paragraph(it["description"], normal),
                Paragraph(str(it["quantity"]), right),
                Paragraph(money(it["unit_price"]), right),
                Paragraph(money(it["total"]), right),
            ]
        )
        subtotal += it["total"]

    tax_rate = Decimal(args.tax_rate) / Decimal("100")
    tax_amount = (subtotal * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = subtotal + tax_amount

    # Summary rows
    for label, amount in [
        ("Subtotal", subtotal),
        (f"Tax ({args.tax_rate}%)", tax_amount),
        ("Total", total),
    ]:
        data.append(
            [
                "",
                "",
                Paragraph(f"<b>{label}</b>", right),
                Paragraph(money(amount), right),
            ]
        )

    tbl = Table(data, colWidths=[doc.width * 0.45, doc.width * 0.15, doc.width * 0.2, doc.width * 0.2])
    tbl.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND", (0, -3), (-1, -1), colors.whitesmoke),
            ]
        )
    )
    flow.append(tbl)
    flow.append(Spacer(1, 36))

    # Footer / Notes
    if args.notes:
        flow.append(Paragraph("<b>Notes</b>", bold))
        flow.append(Spacer(1, 6))
        flow.append(Paragraph(args.notes.replace("\n", "<br/>"), normal))

    # Build PDF
    doc.build(flow)
    print(f"Invoice generated: {args.output}")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a PDF invoice from a CSV transaction log.")
    parser.add_argument("--log", required=True, help="Path to CSV transaction log.")
    parser.add_argument("--output", required=True, help="Destination PDF file.")
    parser.add_argument("--invoice-number", required=True, help="Invoice number.")
    parser.add_argument("--date", default=datetime.today().strftime("%Y-%m-%d"), help="Invoice date (YYYY-MM-DD).")
    parser.add_argument("--company-name", required=True, help="Your company name.")
    parser.add_argument("--company-address", required=True, help="Your company address (use \\n for line breaks).")
    parser.add_argument("--client-name", required=True, help="Client name.")
    parser.add_argument("--client-address", required=True, help="Client address (use \\n for line breaks).")
    parser.add_argument("--tax-rate", default="0", help="Tax rate as a percentage (e.g., 8.25).")
    parser.add_argument("--notes", default="", help="Optional notes to include at the bottom of the invoice.")
    return parser.parse_args()


def main():
    args = parse_args()
    if not os.path.isfile(args.log):
        print(f"Transaction log not found: {args.log}", file=sys.stderr)
        sys.exit(1)
    build_invoice(args)


if __name__ == "__main__":
    main()