# Stripe revenue

Read-only: MRR, active subscriptions and revenue over the last 30 days.

1. Stripe Dashboard, Developers, API keys, **Create restricted key**. Grant **Read** on *Subscriptions* and *Charges* only. Nothing else.
2. Put it in `automations/.env`: `STRIPE_API_KEY=rk_live_...`
3. `python3 brain.py refresh stripe`

Notes: amounts are in your Stripe currency (the script doesn't convert). MRR normalises yearly and weekly plans to a month and ignores one-time charges. If you sell in several currencies, ask Claude to adapt `pull.py` to filter by currency.
