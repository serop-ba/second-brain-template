"""Run: python3 -m unittest discover -s tests -v   (stdlib only)"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import backup  # noqa: E402
import cli  # noqa: E402
import db  # noqa: E402
import metrics  # noqa: E402
import seed  # noqa: E402
import store  # noqa: E402
import views  # noqa: E402
from store import Error  # noqa: E402


def load_script(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BRAIN_DB"] = str(Path(self.tmp.name) / "brain.db")
        os.environ["BRAIN_ACTOR"] = "tester"
        db._ready.clear()

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("BRAIN_DB", None)
        os.environ.pop("BRAIN_ACTOR", None)

    def run_cli(self, *argv):
        buf = StringIO()
        with redirect_stdout(buf):
            cli.main(list(argv))
        return buf.getvalue()


class Audit(Base):
    def test_every_change_is_recorded_with_actor_and_reason(self):
        store.profile_set("name", "Acme", "first fact")
        store.profile_set("name", "Acme Ltd", "renamed")
        rows = store.changes(10, entity="profile")
        self.assertEqual([r["action"] for r in rows], ["update", "insert"])
        self.assertEqual(rows[0]["actor"], "tester")
        self.assertEqual(rows[0]["reason"], "renamed")
        self.assertEqual(rows[0]["before"]["value"], "Acme")
        self.assertEqual(rows[0]["after"]["value"], "Acme Ltd")

    def test_raw_sql_edits_are_audited_too(self):
        store.profile_set("name", "Acme")
        con = sqlite3.connect(os.environ["BRAIN_DB"])
        con.execute("UPDATE profile SET value = 'sneaky'")
        con.commit()
        con.close()
        self.assertEqual(store.changes(1)[0]["after"]["value"], "sneaky")

    def test_history_cannot_be_edited(self):
        store.profile_set("name", "Acme")
        with self.assertRaises(sqlite3.DatabaseError):
            with db.write() as con:
                con.execute("DELETE FROM changes")

    def test_revert_update_insert_and_delete(self):
        store.profile_set("name", "Acme")
        store.profile_set("name", "Wrong")
        store.revert(store.changes(1)[0]["id"])
        self.assertEqual(store.profile_get()["name"], "Acme")
        d = store.doc_add("Playbook", "v1", kind="playbook")
        store.doc_update(d["slug"], body="v2")
        store.doc_remove(d["slug"])
        self.assertTrue(store.revert(store.changes(1)[0]["id"]).startswith("brought back"))
        self.assertEqual(store.doc_get(d["slug"])["body"], "v2")
        update = next(c for c in store.changes(10, entity="documents") if c["action"] == "update")
        store.revert(update["id"])
        self.assertEqual(store.doc_get(d["slug"])["body"], "v1")
        self.assertGreaterEqual(len(store.changes(50)), 6)  # reverts are themselves recorded


class AppendOnly(Base):
    def test_decision_needs_a_prediction_and_a_future_review(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        with self.assertRaises(Error):
            store.decision_add("T", "do it", "", future)
        with self.assertRaises(Error):
            store.decision_add("T", "do it", "x", date.today().isoformat())
        self.assertEqual(store.decision_add("T", "do it", "x", future), 1)

    def test_past_decision_only_accepts_an_outcome(self):
        past = (date.today() - timedelta(days=10)).isoformat() + "T09:00:00"
        review = (date.today() + timedelta(days=5)).isoformat()
        i = store.decision_add("Old", "did", "expect", review, created_at=past)
        with self.assertRaises(sqlite3.DatabaseError):
            store.decision_update(i, expect="rewritten history")
        with self.assertRaises(sqlite3.DatabaseError):
            store.decision_remove(i)
        store.decision_outcome(i, "Right.")
        self.assertEqual(store.decision_list()[0]["outcome"], "Right.")

    def test_todays_decision_can_be_fixed_and_deleted(self):
        i = store.decision_add("T", "d", "e", (date.today() + timedelta(days=3)).isoformat())
        store.decision_update(i, title="Fixed")
        store.decision_remove(i)
        self.assertEqual(store.decision_list(), [])

    def test_log_entries_are_never_edited(self):
        i = store.log_add("capture", "Something happened")
        with self.assertRaises(sqlite3.DatabaseError):
            with db.write() as con:
                con.execute("UPDATE log_entries SET title = 'edited' WHERE id = ?", (i,))
        with self.assertRaises(Error):
            store.log_add("Not A Type", "x")


class Metrics(Base):
    def test_bands_are_validated_and_verdicts_never_guess(self):
        store.dept_add("Finance")
        with self.assertRaises(Error):
            metrics.metric_add("mrr", "MRR", healthy="pretty good")
        metrics.metric_add("mrr", "MRR", department="finance", healthy=">= 2000", watch="500-1999", bad="< 500")
        metrics.metric_add("subs", "Subs")
        self.assertEqual(metrics.metric_get("mrr")["verdict"], "no data")
        metrics.point_set("mrr", "1,200")
        metrics.point_set("subs", 40)
        self.assertEqual(metrics.metric_get("mrr")["verdict"], "watch")
        self.assertEqual(metrics.metric_get("subs")["verdict"], "not scored")
        with self.assertRaises(Error):
            metrics.point_set("nope", 1)

    def test_pulled_point_deleted_by_hand_stays_deleted(self):
        metrics.metric_add("views", "Views")
        today = db.today()
        metrics.record_points("youtube", [{"metric": "views", "value": 10, "date": today}])
        metrics.point_delete("views", today)
        res = metrics.record_points("youtube", [{"metric": "views", "value": 11, "date": today}, {"metric": "ghost", "value": 1}])
        self.assertEqual(res, {"recorded": 0, "unmapped": ["ghost"]})
        self.assertIsNone(metrics.metric_get("views")["now"])
        metrics.point_set("views", 12)  # a hand entry revives the day
        self.assertEqual(metrics.metric_get("views")["now"], 12)

    def test_delta_uses_the_previous_point(self):
        metrics.metric_add("mrr", "MRR")
        metrics.point_set("mrr", 100, "2026-01-01")
        metrics.point_set("mrr", 130, "2026-02-01")
        m = metrics.metric_get("mrr")
        self.assertEqual((m["now"], m["prev"], m["delta"]), (130, 100, 30))


class Tasks(Base):
    def test_items_need_a_real_bet_and_open_goals_carry_over(self):
        with self.assertRaises(Error):
            store.task_add("goal", "ship it", 3)
        store.bet_add("Ship")
        i = store.task_add("goal", "ship it #bet1")
        with db.write() as con:
            con.execute("UPDATE items SET week = ? WHERE id = ?", (store.iso_week(date.today() - timedelta(days=14)), i))
        goal = store.task_snapshot()["goals"][0]
        self.assertEqual((goal["bet"], goal["carried"]), (1, 2))
        store.task_done(i)
        self.assertTrue(store.task_snapshot()["goals"][0]["done"])


class Demo(Base):
    def test_demo_loads_clears_and_leaves_no_trace(self):
        seed.load()
        self.assertTrue(views.demo_active())
        self.assertGreater(len(metrics.metric_list()), 3)
        self.assertGreater(len(store.changes(500)), 20)
        with self.assertRaises(Error):
            seed.load()
        seed.clear()
        self.assertFalse(views.demo_active())
        with db.read() as con:
            for table in db.WIPE_ORDER + ["changes", "demo_rows"]:
                self.assertEqual(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)

    def test_clear_keeps_what_you_edited_and_added(self):
        seed.load()
        store.profile_set("name", "My Real Business", "mine now")
        store.dept_add("Support")
        seed.clear()
        self.assertEqual(store.profile_get(), {"name": "My Real Business"})
        self.assertEqual([d["slug"] for d in store.dept_list()], ["support"])

    def test_load_refuses_when_you_already_have_data(self):
        store.profile_set("name", "Real")
        with self.assertRaises(Error):
            seed.load()


class Backups(Base):
    def test_backup_and_restore_roundtrip(self):
        store.profile_set("name", "Before")
        snap = backup.backup()
        store.profile_set("name", "After")
        backup.restore(str(snap))
        db._ready.clear()
        self.assertEqual(store.profile_get()["name"], "Before")
        self.assertTrue(json.loads(backup.export().read_text())["tables"]["profile"])


class Cli(Base):
    def test_pre_commit_hook_runs_the_suite(self):
        hook = Path(__file__).resolve().parent.parent / ".githooks" / "pre-commit"
        self.assertTrue(os.access(hook, os.X_OK))
        self.assertIn("unittest discover -s tests", hook.read_text())
    def test_flags_work_after_the_verb_and_json_is_parseable(self):
        self.run_cli("dept", "add", "Marketing", "--reason", "setup")
        data = json.loads(self.run_cli("dept", "list", "--json"))
        self.assertEqual(data[0]["slug"], "marketing")
        self.assertEqual(store.changes(20, entity="documents")[0]["action"], "insert")  # default sections created

    def test_context_on_an_empty_brain_points_at_init(self):
        self.assertIn("/init", self.run_cli("context"))

    def test_errors_are_one_line_and_actionable(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("metric", "set", "ghost", "1")
        self.assertIn("no metric 'ghost'", str(ctx.exception))

    def test_sweep_imports_readable_files_and_leaves_the_rest(self):
        drop = Path(self.tmp.name) / "drop"
        drop.mkdir()
        (drop / "call-notes.md").write_text("We priced the audit at 900")
        (drop / "empty.txt").write_text("  ")
        (drop / "scan.docx").write_bytes(b"PK")
        (drop / ".gitkeep").write_text("")
        original, cli.DROP = cli.DROP, drop
        try:
            data = json.loads(self.run_cli("doc", "sweep", "--tags", "pricing", "--json"))
            again = json.loads(self.run_cli("doc", "sweep", "--json"))
        finally:
            cli.DROP = original
        self.assertEqual(data["imported"], ["call-notes"])
        self.assertEqual(sorted(data["left"]), ["empty.txt", "scan.docx"])
        doc = store.doc_get("call-notes")
        self.assertEqual((doc["kind"], doc["ingested"], doc["tags"]), ("source", 0, "pricing"))
        self.assertEqual([p.name[11:] for p in (drop / "done").iterdir()], ["call-notes.md"])
        self.assertFalse((drop / "call-notes.md").exists())
        self.assertEqual(again["imported"], [])  # nothing is imported twice
        self.assertTrue((drop / ".gitkeep").exists())


class Automations(Base):
    def setUp(self):
        super().setUp()
        import registry
        self.registry = registry
        self.auto = Path(self.tmp.name) / "automations"
        shutil.copytree(ROOT / "automations", self.auto)
        self.saved = (registry.AUTO, registry.ENV_FILE)
        registry.AUTO, registry.ENV_FILE = self.auto, self.auto / ".env"

    def tearDown(self):
        self.registry.AUTO, self.registry.ENV_FILE = self.saved
        super().tearDown()

    def test_csv_import_records_points_and_reports_unknown_metrics(self):
        import refresh
        metrics.metric_add("mrr", "MRR")
        (self.auto / "csv-import" / "inbox" / "a.csv").write_text("metric,date,value,note\nmrr,2026-01-05,1200,hand\nghost,2026-01-05,1,\n")
        lines = []
        status = refresh.refresh(say=lines.append)
        self.assertTrue(status["ok"], lines)
        self.assertEqual(metrics.metric_get("mrr")["now"], 1200)
        self.assertIn("ghost", "\n".join(lines))
        self.assertTrue((self.auto / "csv-import" / "done" / "a.csv").exists())
        again = []
        refresh.refresh(say=again.append)  # nothing left to read: skipped, not failed
        self.assertIn("skipped", "\n".join(again))

    def test_a_failing_pull_keeps_the_last_value_and_does_not_stop_the_others(self):
        import refresh
        metrics.metric_add("good", "Good")
        metrics.metric_add("bad", "Bad")
        metrics.point_set("bad", 7)
        for name, body in (("a_bad", "import sys; sys.exit('boom')"), ("b_good", "import json; print(json.dumps({'points': [{'metric': 'good', 'value': 3}]}))")):
            folder = self.auto / name
            folder.mkdir()
            (folder / "pull.py").write_text(body)
            (folder / "automation.json").write_text(json.dumps({"label": name, "order": 1, "pull": [{"run": "pull.py"}]}))
        status = refresh.refresh(say=lambda *_: None)
        self.assertFalse(status["ok"])
        self.assertEqual(metrics.metric_get("good")["now"], 3)
        self.assertEqual(metrics.metric_get("bad")["now"], 7)

    def test_pack_install_creates_metrics_and_lists_the_env_it_needs(self):
        import packs
        store.dept_add("Marketing")
        res = packs.install_automation("youtube")
        self.assertIn("youtube_subscribers", res["metrics_created"])
        self.assertEqual(metrics.metric_get("youtube_subscribers")["department"], "marketing")
        self.assertIn("YOUTUBE_API_KEY", res["next"])
        with self.assertRaises(Error):
            packs.install_automation("youtube")
        with self.assertRaises(Error):
            packs.install_automation("nope")
        missing = self.registry.missing_env(self.registry.get("youtube"))
        self.assertIn("YOUTUBE_API_KEY", missing)

    def test_profiles_only_add(self):
        import packs
        store.dept_add("Marketing")
        res = packs.apply_profile("service")
        self.assertNotIn("marketing", res["departments"])
        self.assertIn("delivery", res["departments"])
        self.assertEqual(packs.apply_profile("service")["departments"], [])

    def test_stripe_mrr_normalises_intervals(self):
        stripe_pull = load_script(ROOT / "catalog" / "automations" / "stripe" / "pull.py", "stripe_pull")
        sub = lambda amount, interval, qty=1: {"id": "s", "items": {"data": [{"quantity": qty, "price": {"unit_amount": amount, "recurring": {"interval": interval, "interval_count": 1}}}]}}  # noqa: E731
        fake = {"subscriptions": [sub(2900, "month"), sub(12000, "year"), sub(1000, "month", 3)],
                "charges": [{"id": "c1", "amount": 5000, "paid": True, "amount_refunded": 1000}, {"id": "c2", "amount": 900, "paid": False}]}

        def get(path, params):
            return {"data": fake[path], "has_more": False}
        pts = {p["metric"]: p["value"] for p in stripe_pull.compute(get)}
        self.assertEqual(pts["stripe_mrr"], 29 + 10 + 30)
        self.assertEqual(pts["stripe_active_subscriptions"], 3)
        self.assertEqual(pts["stripe_revenue_30d"], 40)

    def test_meta_ads_export_becomes_daily_points(self):
        meta_pull = load_script(ROOT / "catalog" / "automations" / "meta-ads" / "pull.py", "meta_pull")
        f = Path(self.tmp.name) / "export.csv"
        f.write_text("Day,Campaign name,Amount spent (EUR),Link clicks,Results\n2026-09-20,A,10.00,20,2\n2026-09-20,B,5.00,10,0\n2026-09-21,A,8,16,4\n")
        pts = {(p["metric"], p["date"]): p["value"] for p in meta_pull.points(meta_pull.read(f))}
        self.assertEqual(pts[("ad_spend", "2026-09-20")], 15.0)
        self.assertEqual(pts[("ad_cost_per_result", "2026-09-20")], 7.5)
        self.assertEqual(pts[("ad_cpc", "2026-09-21")], 0.5)


class Context(Base):
    def test_working_rules_and_attention_reach_claude(self):
        store.doc_add("Working rules", "Be blunt.", kind="playbook")
        store.inbox_add("remember the milk")
        text = views.status_text()
        self.assertIn("Be blunt.", text)
        self.assertIn("1 item(s) in the inbox", text)

    def test_claude_is_the_actor_inside_claude_code(self):
        os.environ.pop("BRAIN_ACTOR")
        os.environ["CLAUDECODE"] = "1"
        try:
            store.profile_set("name", "X")
            self.assertEqual(store.changes(1)[0]["actor"], "claude")
        finally:
            os.environ.pop("CLAUDECODE")
            os.environ["BRAIN_ACTOR"] = "tester"


class Console(Base):
    def test_api_needs_the_token_and_writes_are_attributed_to_the_console(self):
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer

        import server
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        def call(path, body=None, token=server.TOKEN):
            req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, headers={"X-Token": token, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.load(r)
            except urllib.error.HTTPError as e:
                return e.code, json.load(e)
        try:
            self.assertEqual(call("/api/state", token="wrong")[0], 403)
            self.assertEqual(call("/api/rpc", {"fn": "os_system", "args": {}})[0], 404)
            self.assertEqual(call("/api/rpc", {"fn": "profile_set", "args": {"key": "name", "value": "Via UI"}})[0], 200)
            code, state = call("/api/state")
            self.assertEqual((code, state["company"]), (200, "Via UI"))
            self.assertEqual(state["changes"][0]["actor"], "console")
            code, err = call("/api/rpc", {"fn": "decision_add", "args": {"title": "t", "decided": "d", "expect": "", "review_on": "2099-01-01"}})
            self.assertEqual(code, 400)
            self.assertIn("expect", err["error"])
            self.assertEqual(call("/api/graph")[0], 200)
        finally:
            httpd.shutdown()
            httpd.server_close()


@unittest.skipUnless(os.environ.get("BRAIN_MIGRATION_SOURCE"), "set BRAIN_MIGRATION_SOURCE=/path/to/markdown-brain to run this")
class Migration(Base):
    def test_a_markdown_brain_imports_completely_and_unchanged(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import migrate_markdown as mig
        sys.path.pop(0)
        src = Path(os.environ["BRAIN_MIGRATION_SOURCE"])
        before = (src / "company.md").read_text()
        data = mig.collect(src, False, {"finance"})
        counts = mig.apply(data, src)
        self.assertEqual(counts["departments"], len(data["areas"]))
        self.assertEqual(counts["log"], len(data["log"]))
        self.assertEqual(len(metrics.metric_list()), counts["metrics"])
        self.assertEqual(len(store.dept_list()), counts["departments"])
        self.assertEqual((src / "company.md").read_text(), before)
        self.assertTrue(store.search("a")[0])


if __name__ == "__main__":
    unittest.main()
