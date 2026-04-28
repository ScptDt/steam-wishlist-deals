from __future__ import annotations

import copy
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

    def test_payday2_budget_uses_importance_value_copy_and_fields(self) -> None:
        index_html = (ROOT / "web" / "payday2" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "payday2" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "payday2" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("priorizando importancia jugable y valor", index_html)
        self.assertIn("b.valueScore", app_js)
        self.assertIn("b.importanceScore", app_js)
        self.assertIn("valueReasons", app_js)
        self.assertIn("bi-reason", app_js)
        self.assertIn(".budget-item .bi-reason", app_css)

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

    def test_desktop_packaging_wires_windows_icon(self) -> None:
        icon_src = ROOT / "assets" / "steam_tools_icon.svg"
        fake_icon = ROOT / ".tmp" / "test" / "steam_tools_icon.ico"
        cmd = ["pyinstaller"]

        build_desktop.append_icon_arg(cmd, os_name="nt", icon_path=fake_icon)
        ico_bytes = build_desktop.build_windows_icon_bytes()

        self.assertTrue(icon_src.exists())
        self.assertEqual(cmd[-2:], ["--icon", str(fake_icon)])
        self.assertEqual(ico_bytes[:4], b"\x00\x00\x01\x00")
        self.assertGreater(len(ico_bytes), 100)


class Payday2BudgetImportanceTests(unittest.TestCase):
    def test_budget_prioritizes_gameplay_heist_over_cheap_cosmetic(self) -> None:
        missing = [
            {
                "appid": "100",
                "steam_name": "PAYDAY 2: Very Cheap Tailor Pack",
                "price_raw": 3900,
                "price_fmt": "Mex$ 39.00",
                "orig_raw": 39000,
                "discount": 90,
            },
            {
                "appid": "200",
                "steam_name": "PAYDAY 2: Important Bank Heist",
                "price_raw": 6400,
                "price_fmt": "Mex$ 64.00",
                "orig_raw": 6400,
                "discount": 0,
            },
        ]

        rec = payday2_dlc_tracker.compute_recommendations(
            missing, budget=70, alert_price=None, min_deal=50
        )

        self.assertEqual(
            [d["steam_name"] for d in rec["budget_fit"]],
            ["PAYDAY 2: Important Bank Heist"],
        )
        self.assertLessEqual(
            sum(d["price_raw"] for d in rec["budget_fit"]) / 100,
            70,
        )
        self.assertEqual(rec["budget_fit"][0]["importance_tier"], "S")
        self.assertIn("Heist", rec["budget_fit"][0]["value_reasons"][0])

    def test_payday2_web_payload_exposes_budget_value_metadata(self) -> None:
        original_store = copy.deepcopy(payday2_web._store)
        all_dlcs = {
            "200": {
                "appid": "200",
                "steam_name": "PAYDAY 2: Important Bank Heist",
                "price_raw": 6400,
                "price_fmt": "Mex$ 64.00",
                "orig_raw": 6400,
                "orig_fmt": "",
                "discount": 0,
            }
        }
        recommendations = payday2_dlc_tracker.compute_recommendations(
            list(all_dlcs.values()), None, None
        )

        try:
            with payday2_web._store_lock:
                payday2_web._store.update(
                    {
                        "loaded": True,
                        "refreshing": False,
                        "last_refresh": None,
                        "vanity": "tester",
                        "steam_id": "steam-id",
                        "pd2_dlc_appids": ["200"],
                        "all_dlcs": all_dlcs,
                        "owned": set(),
                        "prices": all_dlcs,
                        "sale_name": "",
                        "recommendations": recommendations,
                        "bundles": [],
                        "history_data": {},
                        "comparison": {},
                        "itad_lows": {},
                    }
                )

            payload = payday2_web.get_data_json()
        finally:
            with payday2_web._store_lock:
                payday2_web._store.clear()
                payday2_web._store.update(original_store)

        self.assertEqual(payload["dlcs"][0]["importanceTier"], "S")
        self.assertGreater(payload["dlcs"][0]["valueScore"], 0)
        self.assertIn("Heist", payload["dlcs"][0]["valueReasons"][0])


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

    def test_get_owned_games_converts_auth_errors_to_actionable_error(self) -> None:
        original_get_json = payday2_dlc_tracker._get_json

        def fake_get_json(url, headers=None):
            raise urllib.error.HTTPError(url, 401, "Unauthorized", hdrs=None, fp=None)

        try:
            payday2_dlc_tracker._get_json = fake_get_json
            with self.assertRaisesRegex(ValueError, "juegos poseídos"):
                payday2_dlc_tracker.get_owned_games("bad-key", "steam-id")
        finally:
            payday2_dlc_tracker._get_json = original_get_json

    def test_resolve_owned_dlc_appids_preserves_manual_cache_when_api_key_is_rejected(self) -> None:
        emitted = []

        def fake_get_owned_games(_key, _steam_id):
            raise ValueError(
                "Steam rechazó la API key al verificar juegos poseídos (HTTP 401)."
            )

        owned = payday2_dlc_tracker.resolve_owned_dlc_appids(
            "bad-key",
            "steam-id",
            ["10", "20", "30"],
            get_owned_games_fn=fake_get_owned_games,
            load_owned_fn=lambda _steam_id: {"20"},
            emit=emitted.append,
        )

        self.assertEqual(owned, {"20"})
        self.assertTrue(any("juegos poseídos" in line for line in emitted))


if __name__ == "__main__":
    unittest.main()
