* Reads a simple JSON config (or environment variables) that defines:
  - Discord webhook URL
  - List of product URLs (or store+handle pairs)
* Persists last‑known prices in a local JSON state file between runs.
* Handles Shopify's public *.json endpoint (e.g. https://store.myshopify.com/products/awesome‑shirt.json).
* Supports multiple variants – tracks the **lowest** variant price.
* Adjustable polling interval.
* Robust error handling & logging.

Usage
~~~~~
    python3 shopify_price_tracker.py --config config.json --state state.json --interval 300

Config file example (config.json)::

    {
        "webhook_url": "https://discord.com/api/webhooks/....",
        "products": [
            {
                "name": "Awesome Shirt",
                "url": "https://example.myshopify.com/products/awesome-shirt"
            },
            {
                "name": "Cool Mug",
                "url": "https://anotherstore.myshopify.com/products/cool-mug"
            }
        ]
    }

The script creates/updates the state file (state.json) automatically.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import requests

# --------------------------------------------------------------------------- #
# Configuration & Constants
# --------------------------------------------------------------------------- #

DEFAULT_INTERVAL = 300               # seconds
USER_AGENT = "ShopifyPriceTracker/1.0 (+https://github.com/yourname/shopify-price-tracker)"
REQUEST_TIMEOUT = 15                # seconds
EMBED_COLOR = 0xFF5555               # Discord embed color (red-ish)

# --------------------------------------------------------------------------- #
# Helper Functions
# --------------------------------------------------------------------------- #

def load_json_file(path: str, default=None):
    if not os.path.isfile(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logging.error("Failed to load JSON from %s: %s", path, exc)
        return default if default is not None else {}

def save_json_file(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logging.error("Failed to write JSON to %s: %s", path, exc)

def fetch_shopify_product_json(product_url: str):
    """
    Returns the parsed JSON payload from the public Shopify endpoint.
    Shopify exposes product data at: <product_url>.json
    """
    json_url = product_url.rstrip("/") + ".json"
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(json_url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logging.error("Error fetching %s: %s", json_url, exc)
        return None

def extract_lowest_price(product_json: dict):
    """
    Shopify product JSON format:
    {
        "product": {
            "title": "...",
            "variants": [
                {"price": "12.99", ...},
                {"price": "10.00", ...}
            ],
            ...
        }
    }
    Returns Decimal of the lowest variant price or None.
    """
    try:
        variants = product_json["product"]["variants"]
        prices = []
        for v in variants:
            price_str = v.get("price")
            if price_str is None:
                continue
            try:
                prices.append(Decimal(price_str))
            except InvalidOperation:
                continue
        if not prices:
            return None
        return min(prices)
    except Exception as exc:
        logging.error("Failed to extract price: %s", exc)
        return None

def send_discord_webhook(webhook_url: str, product_name: str, product_url: str,
                         old_price: Decimal, new_price: Decimal):
    """
    Sends a Discord embed notifying about a price change.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    embed = {
        "title": "Shopify Price Change Detected",
        "url": product_url,
        "description": f"**{product_name}** price updated.",
        "color": EMBED_COLOR,
        "fields": [
            {"name": "Old Price", "value": f"${old_price:.2f}", "inline": True},
            {"name": "New Price", "value": f"${new_price:.2f}", "inline": True},
        ],
        "timestamp": now_iso,
        "footer": {"text": "Shopify Price Tracker"},
    }
    payload = {"embeds": [embed]}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=REQUEST_TIMEOUT)
        if resp.status_code in (200, 204):
            logging.info("Discord webhook sent for %s", product_name)
        else:
            logging.error("Discord webhook failed (%s): %s", resp.status_code, resp.text)
    except Exception as exc:
        logging.error("Exception while sending Discord webhook: %s", exc)

def normalize_price(value):
    """Ensures Decimal with two decimal