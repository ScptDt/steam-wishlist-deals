from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HistoryDrilldownAssetsTests(unittest.TestCase):
    def test_history_drilldown_uses_compact_candidate_groups(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("HISTORY_DRILLDOWN_VISIBLE_CANDIDATES = 6", app_js)
        self.assertIn("splitHistoryDrilldownCandidates", app_js)
        self.assertIn("renderHistoryDrilldownButtons", app_js)
        self.assertIn("Ver ${escapeHtml(hiddenCount)} juegos más", app_js)
        self.assertIn("Mostramos primero los juegos más relevantes", app_js)
        self.assertIn(".history-drilldown-more", app_css)
        self.assertIn(".history-drilldown-more-grid", app_css)


if __name__ == "__main__":
    unittest.main()
