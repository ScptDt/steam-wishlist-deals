from __future__ import annotations

import urllib.error
import unittest
from pathlib import Path

import build_desktop
import desktop_doctor
import payday2_dlc_tracker
import payday2_web
import steam_deals_web
from shared_web_infra import build_missing_assets_html


ROOT = Path(__file__).resolve().parents[1]


class WebAssetsTests(unittest.TestCase):
    def test_history_dashboard_search_quick_compare_copy_and_layout_hooks(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('class="row row-spaced history-search-row"', index_html)
        self.assertIn("Buscar en el histórico", index_html)
        self.assertIn("Comparar 2 recientes", index_html)
        self.assertIn("Filtra por fecha, evento o perfil", index_html)
        self.assertIn("Página ${historyPage} de ${totalPages}", app_js)
        self.assertIn("Filtros del histórico restablecidos.", app_js)
        self.assertIn("Salió", app_js)
        self.assertIn("Cambió", app_js)
        self.assertIn("precios sin cambio", app_js)
        self.assertIn("volumen de ofertas por ejecución", app_js)
        self.assertNotIn("Pagina ${historyPage} de ${totalPages}", app_js)
        self.assertNotIn("include_same activo", app_js)
        self.assertIn(".history-search-row", app_css)
        self.assertIn(".history-quick-card", app_css)
        self.assertIn("@media (max-width: 640px)", app_css)

    def test_generated_file_actions_explain_open_vs_download_behavior(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("Ver último HTML", index_html)
        self.assertIn("findLatestPrimaryHtmlReport", app_js)
        self.assertIn("Abrir reporte interactivo", app_js)
        self.assertIn("Descargar Markdown", app_js)
        self.assertIn("Descargar JSON", app_js)
        self.assertIn("Descargar CSV", app_js)
        self.assertIn("a.setAttribute('download', action.name)", app_js)
        self.assertIn("Los artefactos se muestran por tipo", app_js)

    def test_share_copy_uses_user_friendly_spanish_terms(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("Compartir oferta", index_html)
        self.assertIn("Compartir juegos destacados", app_js)
        self.assertIn("información del reporte más reciente", app_js)
        self.assertIn("¡Copiado!", app_js)
        self.assertNotIn("Compartir Deal", index_html)
        self.assertNotIn("Compartir Top Picks", app_js)
        self.assertNotIn("payload más reciente", app_js)

    def test_output_folder_actions_explain_default_folder_and_open_button(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn('placeholder="output/"', index_html)
        self.assertIn("Si lo dejas vacío, los reportes se guardan", index_html)
        self.assertIn("Ver carpeta", index_html)
        self.assertIn("Generar reportes", index_html)
        self.assertIn("/api/open-output-folder", app_js)
        self.assertIn("openOutputFolderUI", app_js)
        self.assertIn("GENERATED_FILE_ACTION_GROUPS", app_js)
        self.assertIn("HTML interactivo", app_js)
        self.assertIn("Share HTML", app_js)
        self.assertIn("Carpeta local", app_js)
        self.assertIn(".file-link-group", app_css)
        self.assertIn(".file-link-button", app_css)

    def test_payday2_dashboard_has_themed_branding_hooks(self) -> None:
        index_html = (ROOT / "web" / "payday2" / "index.html").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "payday2" / "app.css").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "payday2" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('class="brand-lockup"', index_html)
        self.assertIn('class="pd2-logo-mark"', index_html)
        self.assertIn('id="action-status"', index_html)
        self.assertIn('id="btn-setup"', index_html)
        self.assertIn('id="btn-save-config"', index_html)
        self.assertIn("Heist board", index_html)
        self.assertIn("--heist-blue", app_css)
        self.assertIn(".pd2-mask-img", app_css)
        self.assertIn(".action-status", app_css)
        self.assertIn(".action-status-loading", app_css)
        self.assertIn(".brand-number", app_css)
        self.assertIn("showActionStatus", app_js)
        self.assertIn("Actualizando datos de PAYDAY 2", app_js)
        self.assertIn("Guardando cambio del DLC", app_js)

    def test_payday2_favicon_and_random_masks_stay_scoped(self) -> None:
        index_html = (ROOT / "web" / "payday2" / "index.html").read_text(
            encoding="utf-8"
        )
        steam_index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "payday2" / "app.js").read_text(
            encoding="utf-8"
        )
        payday2_web = (ROOT / "payday2_web.py").read_text(encoding="utf-8")
        steam_deals_web = (ROOT / "steam_deals_web.py").read_text(encoding="utf-8")

        mask_files = [
            "heist_mask_blue.svg",
            "heist_mask_gold.svg",
            "heist_mask_red.svg",
            "heist_mask_shadow.svg",
        ]

        self.assertIn('rel="icon" type="image/svg+xml" href="/favicon.svg"', index_html)
        self.assertNotIn('href="/favicon.svg"', steam_index_html)
        self.assertIn("const PD2_MASKS = Object.freeze", app_js)
        self.assertIn("renderRandomMask", app_js)
        self.assertIn("PAYDAY2_FAVICON_FILE", payday2_web)
        self.assertIn("PAYDAY2_MASK_ROUTES", payday2_web)
        self.assertNotIn("PAYDAY2_MASK_ROUTES", steam_deals_web)
        self.assertTrue((ROOT / "web" / "payday2" / "favicon.svg").exists())
        for mask_file in mask_files:
            self.assertTrue((ROOT / "web" / "payday2" / "masks" / mask_file).exists())
            self.assertIn(f"/masks/{mask_file}", app_js)

    def test_missing_assets_fallback_is_minimal_and_user_facing(self) -> None:
        fallback = build_missing_assets_html("Steam Tools", "web/steam_deals")

        self.assertIn("assets web necesarios", fallback)
        self.assertIn("web/steam_deals", fallback)
        self.assertNotIn("Budget Planner", fallback)
        self.assertNotIn("mismo directorio del script", fallback)

    def test_web_entrypoints_use_minimal_missing_assets_fallbacks(self) -> None:
        self.assertIn("assets web necesarios", steam_deals_web.STEAM_DEALS_MISSING_ASSETS_HTML)
        self.assertIn("assets web necesarios", payday2_web.PAYDAY2_MISSING_ASSETS_HTML)
        self.assertNotIn("Budget Planner", payday2_web.PAYDAY2_MISSING_ASSETS_HTML)
        self.assertNotIn("mismo directorio del script", steam_deals_web.STEAM_DEALS_MISSING_ASSETS_HTML)

    def test_web_entrypoints_do_not_embed_full_fallback_html(self) -> None:
        steam_web = (ROOT / "steam_deals_web.py").read_text(encoding="utf-8")
        payday_web = (ROOT / "payday2_web.py").read_text(encoding="utf-8")

        self.assertNotIn("PAGE_HTML = r", steam_web)
        self.assertNotIn("PAGE_HTML = r", payday_web)
        self.assertIn("STEAM_DEALS_MISSING_ASSETS_HTML", steam_web)
        self.assertIn("PAYDAY2_MISSING_ASSETS_HTML", payday_web)

    def test_desktop_packaging_includes_payday2_svg_assets(self) -> None:
        data_sources = {src for src, _dest in build_desktop.DATA_FILES}

        for asset in desktop_doctor.REQUIRED_DATA_FILES:
            self.assertIn(asset, data_sources)


class Payday2SteamResolutionTests(unittest.TestCase):
    def test_resolve_steam_id_falls_back_to_public_xml_when_api_key_is_forbidden(self) -> None:
        original_get_json = payday2_dlc_tracker._get_json
        original_urlopen = payday2_dlc_tracker.urllib.request.urlopen
        calls = []

        def fake_get_json(url, headers=None):
            calls.append(url)
            raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"<steamID64>76561198000000000</steamID64>"

        try:
            payday2_dlc_tracker._get_json = fake_get_json
            payday2_dlc_tracker.urllib.request.urlopen = lambda _req, timeout=0: _FakeResponse()

            steam_id = payday2_dlc_tracker.resolve_steam_id("bad-key", "gaben")
        finally:
            payday2_dlc_tracker._get_json = original_get_json
            payday2_dlc_tracker.urllib.request.urlopen = original_urlopen

        self.assertEqual(steam_id, "76561198000000000")
        self.assertEqual(len(calls), 1)

    def test_resolve_steam_id_converts_public_profile_403_to_actionable_error(self) -> None:
        original_urlopen = payday2_dlc_tracker.urllib.request.urlopen

        def fake_urlopen(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", hdrs=None, fp=None)

        try:
            payday2_dlc_tracker.urllib.request.urlopen = fake_urlopen
            with self.assertRaisesRegex(ValueError, "Steam rechazó el perfil público"):
                payday2_dlc_tracker.resolve_steam_id(None, "private-profile")
        finally:
            payday2_dlc_tracker.urllib.request.urlopen = original_urlopen


if __name__ == "__main__":
    unittest.main()
