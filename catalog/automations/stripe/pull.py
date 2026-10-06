#!/usr/bin/env python3
"""Pull MRR, active subscriptions and 30-day revenue from Stripe (read-only). Prints {"points": [...]}."""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

API = "https://api.stripe.com/v1/"
MONTHLY = {"month": 1.0, "year": 1 / 12, "week": 52 / 12, "day": 365 / 12}


def fetch(path: str, params: dict) -> dict:
    req = urllib.request.Request(API + path + "?" + urllib.parse.urlencode(params, doseq=True))
    token = base64.b64encode((os.environ["STRIPE_API_KEY"] + ":").encode()).decode()
    req.add_header("Authorization", "Basic " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"Stripe API error {exc.code}: {exc.read().decode()[:200]}")


def pages(path: str, params: dict, get=fetch):
    params = {**params, "limit": 100}
    while True:
        page = get(path, params)
        yield from page["data"]
        if not page.get("has_more") or not page["data"]:
            return
        params["starting_after"] = page["data"][-1]["id"]


def monthly_amount(subscription: dict) -> float:
    total = 0.0
    for item in subscription.get("items", {}).get("data", []):
        price = item.get("price") or {}
        recurring = price.get("recurring") or {}
        per = MONTHLY.get(recurring.get("interval"), 1.0) / max(int(recurring.get("interval_count") or 1), 1)
        total += (price.get("unit_amount") or 0) * (item.get("quantity") or 1) * per
    return total / 100


def compute(get=fetch, now: float | None = None) -> list:
    now = now or time.time()
    today = date.today().isoformat()
    subs = list(pages("subscriptions", {"status": "active"}, get))
    mrr = sum(monthly_amount(s) for s in subs)
    charges = pages("charges", {"created[gte]": int(now - 30 * 86400)}, get)
    revenue = sum((c["amount"] - (c.get("amount_refunded") or 0)) for c in charges if c.get("paid")) / 100
    return [{"metric": "stripe_mrr", "value": round(mrr, 2), "date": today},
            {"metric": "stripe_active_subscriptions", "value": len(subs), "date": today},
            {"metric": "stripe_revenue_30d", "value": round(revenue, 2), "date": today}]


if __name__ == "__main__":
    print(json.dumps({"points": compute()}))
