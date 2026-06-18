from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.steam_deals_history import load_previous_run, load_price_history, load_run_history
from app.steam_deals_history_dashboard import compare_history_runs, list_history_runs


class _FakeHistoryHandler:
    def __init__(self, path: str) -> None:
        self.path = path
        self.sent = []

    def _send_json(self, payload, status=200):
        self.sent.append((status, payload))


class TrackHistoryFlowTests(unittest.TestCase):
    def test_run_history_missing_dir_stays_quiet_for_first_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            missing_dir = Path(temp_dir) / "missing-history"
            diagnostics = []

            previous = load_previous_run(
                "steam-id",
                history_dir=missing_dir,
                on_diagnostic=diagnostics.append,
            )
            runs = load_run_history(
                "steam-id",
                history_dir=missing_dir,
                on_diagnostic=diagnostics.append,
            )

        self.assertIsNone(previous)
        self.assertEqual(runs, [])
        self.assertEqual(diagnostics, [])

    def test_run_history_reports_bad_existing_files_without_local_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            history_dir = Path(temp_dir)
            (history_dir / "run_2026-04-22_bad.json").write_text(
                "{not-valid-json}", encoding="utf-8"
            )
            (history_dir / "run_2026-04-21_shape.json").write_text(
                json.dumps([{"steam_id": "steam-id"}]), encoding="utf-8"
            )
            (history_dir / "run_2026-04-20_valid.json").write_text(
                json.dumps(
                    {
                        "steam_id": "steam-id",
                        "date": "2026-04-20",
                        "deals": {"10": {"name": "Alpha"}},
                    }
                ),
                encoding="utf-8",
            )
            diagnostics = []

            previous = load_previous_run(
                "steam-id",
                history_dir=history_dir,
                on_diagnostic=diagnostics.append,
            )

            dumped = json.dumps(diagnostics, ensure_ascii=False)

        self.assertIsNotNone(previous)
        assert previous is not None
        self.assertEqual(previous["date"], "2026-04-20")
        self.assertEqual(
            [diagnostic["code"] for diagnostic in diagnostics],
            ["invalid_json", "unsupported_shape"],
        )
        self.assertIn("run_2026-04-22_bad.json", dumped)
        self.assertIn("run_2026-04-21_shape.json", dumped)
        self.assertNotIn(temp_dir, dumped)

    def test_price_history_missing_file_stays_quiet_for_first_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            price_history_file = Path(temp_dir) / "price_history.json"
            diagnostics = []

            history = load_price_history(
                "steam-id",
                price_history_file=price_history_file,
                on_diagnostic=diagnostics.append,
            )

        self.assertEqual(history, {"version": 1, "steam_id": "steam-id", "games": {}})
        self.assertEqual(diagnostics, [])

    def test_price_history_reports_bad_existing_file_without_local_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            price_history_file = Path(temp_dir) / "price_history.json"
            price_history_file.write_text("{not-valid-json}", encoding="utf-8")
            diagnostics = []

            history = load_price_history(
                "steam-id",
                price_history_file=price_history_file,
                on_diagnostic=diagnostics.append,
            )
            dumped = json.dumps(diagnostics, ensure_ascii=False)

        self.assertEqual(history, {"version": 1, "steam_id": "steam-id", "games": {}})
        self.assertEqual(diagnostics[0]["source"], "price_history")
        self.assertEqual(diagnostics[0]["code"], "invalid_json")
        self.assertIn("price_history.json", dumped)
        self.assertNotIn(temp_dir, dumped)

    def test_price_history_reports_wrong_shape_and_profile_mismatch(self) -> None:
        with TemporaryDirectory() as temp_dir:
            price_history_file = Path(temp_dir) / "price_history.json"
            diagnostics = []

            price_history_file.write_text(json.dumps([]), encoding="utf-8")
            wrong_shape = load_price_history(
                "steam-id",
                price_history_file=price_history_file,
                on_diagnostic=diagnostics.append,
            )
            price_history_file.write_text(
                json.dumps({"version": 1, "steam_id": "other", "games": {}}),
                encoding="utf-8",
            )
            mismatch = load_price_history(
                "steam-id",
                price_history_file=price_history_file,
                on_diagnostic=diagnostics.append,
            )

        self.assertEqual(wrong_shape["games"], {})
        self.assertEqual(mismatch["games"], {})
        self.assertEqual(
            [diagnostic["code"] for diagnostic in diagnostics],
            ["unsupported_shape", "steam_id_mismatch"],
        )

    def test_list_history_runs_returns_empty_when_history_dir_is_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            missing_dir = Path(temp_dir) / "missing-history"

            runs = list_history_runs(missing_dir, max_runs=10)

        self.assertEqual(runs, [])

    def test_list_history_runs_skips_malformed_json_and_non_deal_payloads(self) -> None:
        with TemporaryDirectory() as temp_dir:
            history_dir = Path(temp_dir)
            (history_dir / "run_2026-04-19_100000.json").write_text(
                "{not-valid-json}", encoding="utf-8"
            )
            (history_dir / "run_2026-04-20_100000.json").write_text(
                json.dumps({"deals": []}, ensure_ascii=False), encoding="utf-8"
            )
            (history_dir / "run_2026-04-21_100000.json").write_text(
                json.dumps(
                    {
                        "date": "2026-04-21",
                        "timestamp": "2026-04-21T10:00:00",
                        "deals": {"10": {"name": "Alpha", "price_raw": 1000}},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            runs = list_history_runs(history_dir, max_runs=10)

        self.assertEqual([run["id"] for run in runs], ["run_2026-04-21_100000.json"])

    def test_compare_history_runs_adds_same_count_and_richer_analytics(self) -> None:
        with TemporaryDirectory() as temp_dir:
            history_dir = Path(temp_dir)
            (history_dir / "run_2026-04-20_100000.json").write_text(
                json.dumps(
                    {
                        "steam_id": "steam-id",
                        "vanity": "gaben",
                        "date": "2026-04-20",
                        "timestamp": "2026-04-20T10:00:00",
                        "sale_name": "Sale A",
                        "min_discount": 50,
                        "deals": {
                            "10": {"name": "Alpha", "discount": 50, "price_final": "$10", "price_raw": 1000},
                            "20": {"name": "Bravo", "discount": 60, "price_final": "$12", "price_raw": 1200},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (history_dir / "run_2026-04-21_100000.json").write_text(
                json.dumps(
                    {
                        "steam_id": "steam-id",
                        "vanity": "gaben",
                        "date": "2026-04-21",
                        "timestamp": "2026-04-21T10:00:00",
                        "sale_name": "Sale B",
                        "min_discount": 50,
                        "deals": {
                            "10": {"name": "Alpha", "discount": 55, "price_final": "$9", "price_raw": 900},
                            "20": {"name": "Bravo", "discount": 60, "price_final": "$12", "price_raw": 1200},
                            "30": {"name": "Charlie", "discount": 70, "price_final": "$8", "price_raw": 800},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = compare_history_runs(
                history_dir=history_dir,
                left_run_id="run_2026-04-20_100000.json",
                right_run_id="run_2026-04-21_100000.json",
                include_same=True,
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["summary"]["changed"], 1)
        self.assertEqual(result["summary"]["new"], 1)
        self.assertEqual(result["summary"]["removed"], 0)
        self.assertEqual(result["summary"]["same"], 1)
        self.assertEqual(result["analytics"]["state_counts"]["same"], 1)
        self.assertEqual(result["analytics"]["top_price_drops"][0]["appid"], "10")
        self.assertEqual(result["analytics"]["game_history"]["10"][0]["price"], "$10")
        self.assertEqual(result["analytics"]["game_history"]["10"][1]["price"], "$9")
        self.assertEqual(len(result["analytics"]["history_runs"]), 2)

    def test_compare_history_runs_skips_malformed_history_files_from_analytics(self) -> None:
        with TemporaryDirectory() as temp_dir:
            history_dir = Path(temp_dir)
            (history_dir / "run_2026-04-20_100000.json").write_text(
                json.dumps(
                    {
                        "steam_id": "steam-id",
                        "vanity": "gaben",
                        "date": "2026-04-20",
                        "timestamp": "2026-04-20T10:00:00",
                        "sale_name": "Sale A",
                        "min_discount": 50,
                        "deals": {
                            "10": {"name": "Alpha", "discount": 50, "price_final": "$10", "price_raw": 1000}
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (history_dir / "run_2026-04-20_bad.json").write_text(
                "{not-valid-json}", encoding="utf-8"
            )
            (history_dir / "run_2026-04-21_100000.json").write_text(
                json.dumps(
                    {
                        "steam_id": "steam-id",
                        "vanity": "gaben",
                        "date": "2026-04-21",
                        "timestamp": "2026-04-21T10:00:00",
                        "sale_name": "Sale B",
                        "min_discount": 50,
                        "deals": {
                            "10": {"name": "Alpha", "discount": 55, "price_final": "$9", "price_raw": 900}
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = compare_history_runs(
                history_dir=history_dir,
                left_run_id="run_2026-04-20_100000.json",
                right_run_id="run_2026-04-21_100000.json",
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result["analytics"]["history_runs"]), 2)

    def test_list_history_runs_keeps_current_summary_shape(self) -> None:
        with TemporaryDirectory() as temp_dir:
            history_dir = Path(temp_dir)
            (history_dir / "run_2026-04-20_100000.json").write_text(
                json.dumps(
                    {
                        "steam_id": "steam-id",
                        "vanity": "gaben",
                        "date": "2026-04-20",
                        "timestamp": "2026-04-20T10:00:00",
                        "sale_name": "Sale A",
                        "min_discount": 50,
                        "deals": {
                            "10": {"name": "Alpha", "discount": 50, "price_final": "$10", "price_raw": 1000}
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            runs = list_history_runs(history_dir, max_runs=10)

        self.assertEqual(len(runs), 1)
        self.assertEqual(
            sorted(runs[0].keys()),
            [
                "date",
                "deal_count",
                "id",
                "min_discount",
                "sale_name",
                "steam_id",
                "timestamp",
                "vanity",
            ],
        )

    def test_list_history_runs_respects_max_runs_and_keeps_latest_first(self) -> None:
        with TemporaryDirectory() as temp_dir:
            history_dir = Path(temp_dir)
            for day in (20, 21, 22):
                (history_dir / f"run_2026-04-{day}_100000.json").write_text(
                    json.dumps(
                        {
                            "steam_id": "steam-id",
                            "vanity": "gaben",
                            "date": f"2026-04-{day}",
                            "timestamp": f"2026-04-{day}T10:00:00",
                            "sale_name": f"Sale {day}",
                            "min_discount": 50,
                            "deals": {
                                "10": {
                                    "name": "Alpha",
                                    "discount": 50,
                                    "price_final": "$10",
                                    "price_raw": 1000,
                                }
                            },
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            runs = list_history_runs(history_dir, max_runs=2)

        self.assertEqual([run["date"] for run in runs], ["2026-04-22", "2026-04-21"])

    def test_compare_history_runs_supports_status_filter_for_same_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            history_dir = Path(temp_dir)
            (history_dir / "run_2026-04-20_100000.json").write_text(
                json.dumps(
                    {
                        "steam_id": "steam-id",
                        "vanity": "gaben",
                        "date": "2026-04-20",
                        "timestamp": "2026-04-20T10:00:00",
                        "sale_name": "Sale A",
                        "min_discount": 50,
                        "deals": {
                            "10": {"name": "Alpha", "discount": 50, "price_final": "$10", "price_raw": 1000},
                            "20": {"name": "Bravo", "discount": 60, "price_final": "$12", "price_raw": 1200},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (history_dir / "run_2026-04-21_100000.json").write_text(
                json.dumps(
                    {
                        "steam_id": "steam-id",
                        "vanity": "gaben",
                        "date": "2026-04-21",
                        "timestamp": "2026-04-21T10:00:00",
                        "sale_name": "Sale B",
                        "min_discount": 50,
                        "deals": {
                            "10": {"name": "Alpha", "discount": 50, "price_final": "$10", "price_raw": 1000},
                            "20": {"name": "Bravo", "discount": 55, "price_final": "$11", "price_raw": 1100},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = compare_history_runs(
                history_dir=history_dir,
                left_run_id="run_2026-04-20_100000.json",
                right_run_id="run_2026-04-21_100000.json",
                include_same=True,
                status_filter="same",
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual([row["appid"] for row in result["rows"]], ["10"])
        self.assertEqual(result["analytics"]["state_counts"]["same"], 1)

    def test_compare_history_runs_supports_delta_sort_desc_for_changed_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            history_dir = Path(temp_dir)
            (history_dir / "run_2026-04-20_100000.json").write_text(
                json.dumps(
                    {
                        "steam_id": "steam-id",
                        "vanity": "gaben",
                        "date": "2026-04-20",
                        "timestamp": "2026-04-20T10:00:00",
                        "sale_name": "Sale A",
                        "min_discount": 50,
                        "deals": {
                            "10": {"name": "Alpha", "discount": 50, "price_final": "$10", "price_raw": 1000},
                            "20": {"name": "Bravo", "discount": 50, "price_final": "$10", "price_raw": 1000},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (history_dir / "run_2026-04-21_100000.json").write_text(
                json.dumps(
                    {
                        "steam_id": "steam-id",
                        "vanity": "gaben",
                        "date": "2026-04-21",
                        "timestamp": "2026-04-21T10:00:00",
                        "sale_name": "Sale B",
                        "min_discount": 50,
                        "deals": {
                            "10": {"name": "Alpha", "discount": 40, "price_final": "$14", "price_raw": 1400},
                            "20": {"name": "Bravo", "discount": 60, "price_final": "$8", "price_raw": 800},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = compare_history_runs(
                history_dir=history_dir,
                left_run_id="run_2026-04-20_100000.json",
                right_run_id="run_2026-04-21_100000.json",
                sort_delta="delta_desc",
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual([row["appid"] for row in result["rows"]], ["10", "20"])

    def test_compare_history_runs_returns_none_for_invalid_run_names(self) -> None:
        with TemporaryDirectory() as temp_dir:
            history_dir = Path(temp_dir)
            result = compare_history_runs(
                history_dir=history_dir,
                left_run_id="../bad.json",
                right_run_id="run_2026-04-21_100000.json",
            )

        self.assertIsNone(result)

    def test_serve_history_runs_clamps_limit_to_supported_max(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        handler = _FakeHistoryHandler("/api/history/runs?limit=999")
        original_list_history_runs = module.list_history_runs
        calls = []

        def fake_list_history_runs(history_dir, *, max_runs=50):
            calls.append((history_dir, max_runs))
            return [{"id": "run_2026-04-21_100000.json"}]

        module.list_history_runs = fake_list_history_runs
        try:
            Handler._serve_history_runs(handler)
        finally:
            module.list_history_runs = original_list_history_runs

        self.assertEqual(calls, [(module.HISTORY_DIR, 100)])
        self.assertEqual(
            handler.sent,
            [(200, {"runs": [{"id": "run_2026-04-21_100000.json"}]})],
        )

    def test_serve_history_runs_falls_back_to_default_limit_on_invalid_value(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        handler = _FakeHistoryHandler("/api/history/runs?limit=nope")
        original_list_history_runs = module.list_history_runs
        calls = []

        def fake_list_history_runs(history_dir, *, max_runs=50):
            calls.append((history_dir, max_runs))
            return []

        module.list_history_runs = fake_list_history_runs
        try:
            Handler._serve_history_runs(handler)
        finally:
            module.list_history_runs = original_list_history_runs

        self.assertEqual(calls, [(module.HISTORY_DIR, 50)])
        self.assertEqual(handler.sent, [(200, {"runs": []})])

    def test_serve_history_compare_normalizes_query_filters_before_comparing(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        handler = _FakeHistoryHandler(
            "/api/history/compare?left=run_left.json&right=run_right.json&include_same=YES&status=bogus&sort_delta=weird"
        )
        original_compare_history_runs = module.compare_history_runs
        calls = []
        payload = {"summary": {}, "rows": [], "analytics": {}, "left": {}, "right": {}}

        def fake_compare_history_runs(**kwargs):
            calls.append(kwargs)
            return payload

        module.compare_history_runs = fake_compare_history_runs
        try:
            Handler._serve_history_compare(handler)
        finally:
            module.compare_history_runs = original_compare_history_runs

        self.assertEqual(
            calls,
            [
                {
                    "history_dir": module.HISTORY_DIR,
                    "left_run_id": "run_left.json",
                    "right_run_id": "run_right.json",
                    "include_same": True,
                    "status_filter": "all",
                    "sort_delta": "default",
                }
            ],
        )
        self.assertEqual(handler.sent, [(200, payload)])

    def test_serve_history_compare_requires_left_and_right(self) -> None:
        from steam_deals_web import Handler

        handler = _FakeHistoryHandler("/api/history/compare?left=run_left.json")

        Handler._serve_history_compare(handler)

        self.assertEqual(
            handler.sent,
            [
                (
                    400,
                    {
                        "error": "invalid_params",
                        "message": "left y right son requeridos.",
                    },
                )
            ],
        )

    def test_serve_history_compare_returns_not_found_when_comparison_is_unavailable(self) -> None:
        from steam_deals_web import Handler
        import steam_deals_web as module

        handler = _FakeHistoryHandler(
            "/api/history/compare?left=run_left.json&right=run_right.json"
        )
        original_compare_history_runs = module.compare_history_runs
        module.compare_history_runs = lambda **_kwargs: None
        try:
            Handler._serve_history_compare(handler)
        finally:
            module.compare_history_runs = original_compare_history_runs

        self.assertEqual(
            handler.sent,
            [
                (
                    404,
                    {
                        "error": "comparison_not_available",
                        "message": "No se pudieron cargar los runs solicitados.",
                    },
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
