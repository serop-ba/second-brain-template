"""Demo data: a fictional solo AI-consultancy so the console isn't an empty sky on first run.

  python3 brain.py demo load      # only onto an empty brain (or --force)
  python3 brain.py demo clear     # removes exactly what the demo created

Every row the demo creates is remembered in `demo_rows`, so `demo clear` removes
those and nothing you added. A demo row you edited is yours and is kept.
Run `/init` in Claude Code and it clears the demo before filing your real business. Stdlib only.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import db
import metrics
import store
from store import Error, _insert

TRACKED = db.WIPE_ORDER


def _ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def is_demo() -> bool:
    return db.meta_get("demo") == "1"


def has_user_data() -> bool:
    """Anything in the content tables that the demo didn't put there."""
    with db.read() as con:
        for table in TRACKED:
            total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            demo = con.execute("SELECT COUNT(*) FROM demo_rows WHERE tbl = ?", (table,)).fetchone()[0]
            if total > demo:
                return True
    return False


def load(force: bool = False) -> dict:
    if not force and has_user_data():
        raise Error("this brain already has your data. Clear it first, or add --force to load the demo alongside it")
    if is_demo():
        raise Error("the demo is already loaded (python3 brain.py demo clear removes it)")
    with db.read() as con:
        before = {t: con.execute(f"SELECT COALESCE(MAX(id), 0) FROM {t}").fetchone()[0] for t in TRACKED}
    token = db.ACTOR.set("demo")
    try:
        _seed()
    finally:
        db.ACTOR.reset(token)
    with db.write("demo", who="demo") as con:
        for t in TRACKED:
            con.execute(f"INSERT OR IGNORE INTO demo_rows (tbl, row_id) SELECT '{t}', id FROM {t} WHERE id > ?", (before[t],))
        total = con.execute("SELECT COUNT(*) FROM demo_rows").fetchone()[0]
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('demo', '1')")
    db.meta_set("initialized", "1")
    return {"rows": total}


def clear() -> dict:
    """Remove the demo rows (and their history). Rows you edited since are kept as yours."""
    removed = kept = 0
    with db.write("demo clear", who="demo", purge=True) as con:
        for table in TRACKED:  # children first, as WIPE_ORDER lists them
            ids = [r["row_id"] for r in con.execute("SELECT row_id FROM demo_rows WHERE tbl = ?", (table,))]
            if not ids:
                continue
            mine = {r["entity_id"] for r in con.execute(
                "SELECT DISTINCT entity_id FROM changes WHERE entity = ? AND actor NOT IN ('demo') AND actor NOT LIKE 'automation:%'", (table,))}
            drop = [i for i in ids if i not in mine]
            kept += len(ids) - len(drop)
            for i in range(0, len(drop), 400):
                chunk = drop[i:i + 400]
                marks = ",".join("?" * len(chunk))
                con.execute(f"DELETE FROM {table} WHERE id IN ({marks})", chunk)
                con.execute(f"DELETE FROM changes WHERE entity = ? AND entity_id IN ({marks})", [table, *chunk])
            removed += len(drop)
        con.execute("DELETE FROM changes WHERE actor = 'demo'")
        con.execute("DELETE FROM demo_rows")
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('demo', '0')")
    db.meta_set("initialized", "1")
    return {"removed": removed, "kept": kept}


def _seed() -> None:
    P = store.profile_set
    P("name", "Demo Consulting Co.")
    P("tagline", "A solo AI-automation consultancy for small agencies (this is demo data)")
    P("stage", "first revenue")
    P("hours_per_week", "15 alongside a day job")
    P("runway", "about 9 months of savings")
    P("kill_condition", "Under 3 retainer clients by the end of next quarter")
    P("offers", "AI workflow audit (fixed fee 900 EUR), then a monthly retainer (1,200 EUR)")
    P("planning_year", str(date.today().year))

    depts = {}
    for name, owner, hours, owns in [
        ("Marketing", "You", "5", "LinkedIn, the newsletter and the case studies that bring in leads"),
        ("Sales", "You", "4", "Discovery calls, audits and turning an audit into a retainer"),
        ("Delivery", "You", "5", "Building and running the automations clients pay for"),
        ("Finance", "You", "1", "Invoicing, expenses and the monthly close"),
    ]:
        depts[name.lower()] = store.dept_add(name, owner=owner, hours=hours, owns=owns,
                                             intro=f"{name} for Demo Consulting Co. Replace this with what {name} is trying to do.")

    def section(dept: str, title: str, body: str) -> None:
        store.doc_update(f"{dept}/{store.slugify(title)}", body=body)

    section("marketing", "Strategy", "One channel done well: LinkedIn posts that show a real workflow with a number in it, each ending in the newsletter signup.")
    section("marketing", "What's running", "- 3 LinkedIn posts a week\n- A fortnightly newsletter\n- Two case studies in progress")
    section("marketing", "What we've learned", "- Posts with a before/after number get about 4x the replies of tips posts.\n- Generic AI news posts get likes and zero leads.")
    section("sales", "Strategy", "The audit is the product that gets us in the door; the retainer is where the money is. Sell the audit cheaply and convert on results.")
    section("sales", "What's running", "- Every discovery call ends with an audit offer\n- A follow-up email the day after the audit readout")
    store.dept_brief("marketing", "**Headline:** Leads are up but the newsletter is the only thing converting.\n\n**Doing:** 3 posts a week, 2 case studies drafted.\n**Stuck:** nothing measurable on post-to-call conversion.\n**Next:** add a call-booking link to the newsletter footer.\n**Ask of the founder:** pick one case study to publish first.")
    store.dept_brief("sales", "**Headline:** 5 calls this month, 2 audits sold, 0 retainers yet.\n\n**Doing:** follow-ups after audit readouts.\n**Stuck:** audit-to-retainer conversion is unproven (n=2).\n**Next:** offer a 30-day pilot retainer.\n**Ask of the founder:** decide the pilot price.")

    store.north_star_set("Replace my salary with 6 retainer clients by next December", "Quit the day job once recurring revenue covers 12 months of expenses.")
    for g in ("Reach 3,000 EUR/month recurring revenue by June", "Publish 4 case studies that each cite a client number", "Build the audit into a repeatable 5-day process"):
        store.year_add(g)

    b1 = store.bet_add("Turn audits into retainers", department="sales", why="The audit is selling, the retainer is not. That gap is the business.",
                       success="3 of the next 5 audits convert to a retainer", status="on track", next_steps="Write the 30-day pilot offer\nSend it to the two audit clients")
    b2 = store.bet_add("Case studies as the lead engine", department="marketing", why="Posts with a number convert; we need more numbers.",
                       success="4 case studies live and 10 qualified leads a month", status="at risk", status_note="Only 1 published, client approval is slow.", next_steps="Chase approval from client B\nDraft case study 3")
    store.bet_add("Productise delivery", department="delivery", why="Hours per client must fall before more clients is possible.",
                  success="Onboarding takes under 3 hours", status="not started", next_steps="List the repeated onboarding steps")
    store.call_add("Should the audit be free to get more calls?", "Free would fill the calendar but may attract tyre-kickers.")
    store.call_add("Do I need a second channel, or is LinkedIn enough?", "I only have 5 marketing hours a week.")

    for key, name, dept, unit, definition, healthy, watch, bad in [
        ("mrr", "MRR", "finance", "EUR", "Recurring retainer revenue this month, net of VAT.", ">= 3000", "1500-2999", "< 1500"),
        ("active_retainers", "Active retainers", "delivery", "clients", "Clients currently paying a monthly retainer.", ">= 6", "3-5", "< 3"),
        ("qualified_leads", "Qualified leads", "marketing", "leads", "Inbound people who fit the ideal client and asked for a call, per week.", ">= 8", "4-7", "< 4"),
        ("newsletter_subs", "Newsletter subscribers", "marketing", "subs", "Total subscribers. Cumulative: read the change, not the total.", "", "", ""),
        ("close_rate", "Audit to retainer rate", "sales", "%", "Share of finished audits that became a retainer. n is small, treat it as a hint.", ">= 40", "20-39", "< 20"),
        ("monthly_expenses", "Monthly expenses", "finance", "EUR", "Tools, contractors and ads paid out this month.", "", "", ""),
    ]:
        metrics.metric_add(key, name, department=dept, unit=unit, definition=definition, healthy=healthy, watch=watch, bad=bad, source="manual")

    rng = random.Random(7)
    with db.write("demo", who="demo") as con:
        ids = {r["key"]: r["id"] for r in con.execute("SELECT id, key FROM metrics")}
        for key, start, end, step, noise in [
            ("newsletter_subs", 410, 563, 1, 3), ("qualified_leads", 3, 7, 7, 1), ("close_rate", 18, 33, 14, 3),
            ("active_retainers", 1, 3, 20, 0), ("monthly_expenses", 310, 355, 10, 12), ("mrr", 1200, 2400, 15, 0),
        ]:
            days = 80
            for d in range(days, -1, -step):
                value = start + (end - start) * (days - d) / days + rng.uniform(-noise, noise)
                if key == "active_retainers":
                    value = round(value)
                if key == "mrr":
                    value = 1200 if d > 24 else 2400
                _insert(con, "metric_points", {"metric_id": ids[key], "as_of": _ago(d), "value": round(value, 1), "origin": "demo", "recorded_at": db.now()})
            last = con.execute("SELECT MAX(as_of) FROM metric_points WHERE metric_id = ?", (ids[key],)).fetchone()[0]
            if last != _ago(0):
                _insert(con, "metric_points", {"metric_id": ids[key], "as_of": _ago(0), "value": round(end, 1), "origin": "demo", "recorded_at": db.now()})

    week = store.iso_week()
    last_week = store.iso_week(date.today() - timedelta(days=7))
    with db.write("demo", who="demo") as con:
        for kind, text, bet, wk, day, done in [
            ("goal", "Send the pilot retainer offer to both audit clients", b1["n"], week, None, False),
            ("goal", "Publish case study 2", b2["n"], week, None, True),
            ("goal", "Write the onboarding checklist", 3, last_week, None, False),
            ("priority", "Draft the 30-day pilot offer", b1["n"], week, _ago(0), False),
            ("priority", "Reply to the approval email from client B", b2["n"], week, _ago(0), False),
            ("priority", "Record the audit readout template", None, week, _ago(1), True),
        ]:
            created = db.now()
            _insert(con, "items", {"kind": kind, "text": text, "bet": bet, "week": wk, "day": day, "created_at": created, "done_at": created if done else None})

    d1 = store.decision_add("Sell the audit as a fixed 900 EUR fee", "Fixed price instead of hourly.", "At least 2 of the next 4 prospects accept without negotiating the price.",
                            _ago(30), why="Hourly invites haggling about hours.", department="sales", created_at=_ago(60) + "T10:00:00")
    store.decision_outcome(d1, "Right: 3 of 4 accepted. One asked for a discount, we held the price.")
    store.decision_add("Focus marketing on LinkedIn only", "Drop Twitter and the YouTube idea for the quarter.", "Qualified leads reach 8 a week by the review date.",
                       _ago(3), why="5 hours a week cannot feed three channels.", department="marketing", created_at=_ago(45) + "T09:30:00")
    store.decision_add("Offer a 30-day pilot retainer", "Pilot first, full retainer after.", "2 of the 2 audit clients take the pilot.",
                       (date.today() + timedelta(days=21)).isoformat(), why="Removes the risk that stops them committing.", department="sales")

    with db.write("demo", who="demo") as con:
        for days, kind, title, body in [
            (68, "init", "Brain set up (demo)", "Departments, metrics and the north star filed."),
            (40, "decision", "Sell the audit as a fixed 900 EUR fee", "Logged with a prediction and a review date."),
            (35, "weekly", "Week 38: first audit sold", "Moved: 1 audit sold. Didn't: no case study published. Next: chase client approval."),
            (24, "report", "Q3 numbers read", "MRR flat at 1,200 for 4 weeks; leads are the constraint, not close rate."),
            (17, "change", "Moved the newsletter signup above the fold", "So the next report can compare subscriber growth either side."),
            (12, "ingest", "Filed: competitor teardown", "Added a note on how competitor A prices audits."),
            (6, "weekly", "Week 40: second audit sold", "Moved: 2 audits sold in total, 2nd retainer started. Didn't: case study 2 slipped a week."),
            (2, "capture", "Idea: pilot retainer", "Possible fix for the audit-to-retainer gap."),
        ]:
            _insert(con, "log_entries", {"date": _ago(days), "type": kind, "title": title, "body": body, "created_at": _ago(days) + "T09:00:00"})

    store.doc_add("Working rules", "Be a mentor, not an assistant. Lead with an opinion, name the flaw plainly, question the premise.\nSay less: cut every sentence that doesn't change what I think or do.\nNever fabricate a number. Say what's missing.\nAlways report against the bets: a number without a verdict is noise.",
                  kind="playbook", tags="rules")
    store.doc_add("Discovery call script", "1. Their last 30 days: where did time go?\n2. The one task they hate most\n3. What it costs them per week\n4. Offer the audit, name the price, stop talking.",
                  kind="playbook", department="sales", tags="sales,calls")
    store.doc_add("Ideal client", "Founder-led agencies of 3 to 15 people. Revenue 300k to 2M. They already use a CRM and complain about reporting and onboarding.",
                  kind="note", department="marketing", tags="icp,marketing")
    store.doc_add("Competitor A pricing", "Charges 150 EUR/hour, no fixed scope. Their weakness: audits take 3 weeks.", kind="note", department="sales", tags="competitor")
    store.doc_add("Podcast transcript: pricing services", "[Pasted source material goes here. Ask Claude to ingest it into notes and metrics.]",
                  kind="source", department="marketing", tags="pricing", source_ref="https://example.com/episode")
    for text in ("Ask client B about the case study quote", "Idea: webinar on automating client reporting", "Buy the domain for the newsletter archive"):
        store.inbox_add(text)
