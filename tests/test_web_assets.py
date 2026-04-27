from __future__ import annotations

import unittest
from pathlib import Path


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

        self.assertIn('class="brand-lockup"', index_html)
        self.assertIn('class="pd2-logo-mark"', index_html)
        self.assertIn("Heist board", index_html)
        self.assertIn("--heist-blue", app_css)
        self.assertIn(".pd2-mask-img", app_css)
        self.assertIn(".brand-number", app_css)

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


if __name__ == "__main__":
    unittest.main()
