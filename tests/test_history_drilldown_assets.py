from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HistoryDrilldownAssetsTests(unittest.TestCase):
    def test_history_dashboard_static_audit_guardrails_stay_under_details(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        run_button_index = index_html.index('id="btn-run"')
        history_card_index = index_html.index('id="history-card"')
        history_panel_start = index_html.index('<details class="history-panel">')
        history_panel_body_start = index_html.index(
            '<div class="history-panel-body">', history_panel_start
        )
        history_panel_end = index_html.index("</details>", history_panel_body_start)
        history_panel_markup = index_html[history_panel_start:history_panel_end]

        self.assertLess(run_button_index, history_card_index)
        self.assertLess(history_panel_start, history_panel_body_start)
        self.assertNotIn('<details class="history-panel" open', index_html)
        for marker in (
            '<summary class="history-card-summary">',
            "Comparar ejecuciones anteriores",
            "Mantiene filtros y gráficas bajo demanda",
            "Buscar en el histórico",
            "Filtra por fecha, evento o perfil",
            "Comparar 2 recientes",
            'id="history-status-chart"',
            'id="history-top-deltas"',
            'id="history-analytics-summary"',
            'id="history-game-drilldown"',
        ):
            self.assertIn(marker, history_panel_markup)

        for marker in (
            "Contexto ampliado del historial",
            "Resumen visual por estado",
            "La tendencia general resume el volumen de ofertas por ejecución",
            "Cambios destacados de precio (ejecuciones comparadas)",
            "Sin cambios en esta categoria.",
            "Historial por juego",
            "Ver ${escapeHtml(hiddenCount)} juegos más",
            "historyTableBody.querySelectorAll('[data-history-appid]')",
        ):
            self.assertIn(marker, app_js)

        for marker in (
            ".history-panel-body",
            ".history-status-chart",
            ".history-top-deltas",
            ".history-analytics-summary",
            ".history-game-drilldown",
            ".history-drilldown-more-grid",
        ):
            self.assertIn(marker, app_css)

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
