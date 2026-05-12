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

        self.assertIn('class="card history-card-compact" id="history-card"', index_html)
        self.assertIn('<details class="history-panel">', index_html)
        self.assertIn("Comparar ejecuciones anteriores", index_html)
        self.assertIn("Mantiene filtros y gráficas bajo demanda", index_html)
        self.assertIn('class="row row-spaced history-search-row"', index_html)
        self.assertIn("Buscar en el histórico", index_html)
        self.assertIn("Comparar 2 recientes", index_html)
        self.assertIn("Filtra por fecha, evento o perfil", index_html)
        self.assertIn("function resolveQuickCompareRuns", app_js)
        self.assertIn("function prepareQuickCompareSelectors", app_js)
        self.assertIn(
            "La búsqueda actual no tiene 2 ejecuciones; comparando las 2 más recientes globales.",
            app_js,
        )
        self.assertIn("Comparación rápida: últimas 2 ejecuciones globales.", app_js)
        self.assertIn("Página ${historyPage} de ${totalPages}", app_js)
        self.assertIn("Filtros del histórico restablecidos.", app_js)
        self.assertIn("Salió", app_js)
        self.assertIn("Cambió", app_js)
        self.assertIn("precios sin cambio", app_js)
        self.assertIn("volumen de ofertas por ejecución", app_js)
        self.assertNotIn("Pagina ${historyPage} de ${totalPages}", app_js)
        self.assertNotIn("include_same activo", app_js)
        self.assertIn(".history-card-compact", app_css)
        self.assertIn(".history-panel-body", app_css)
        self.assertIn(".history-search-row", app_css)
        self.assertIn(".history-quick-card", app_css)
        self.assertIn("@media (max-width: 640px)", app_css)

    def test_generated_file_actions_explain_open_vs_download_behavior(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("Abrir último reporte", index_html)
        self.assertIn("findLatestPrimaryHtmlReport", app_js)
        self.assertIn("renderLatestReportActions", app_js)
        self.assertIn("renderLatestReportDetails", app_js)
        self.assertIn('<details class="latest-report-details">', app_js)
        self.assertIn("Acciones y recomendaciones del último reporte", app_js)
        self.assertIn("HTML, Share, JSON, carpeta, wishlist, regalos y selección", app_js)
        self.assertIn("Acciones del último reporte", app_js)
        self.assertIn("Siguiente mejor paso", app_js)
        self.assertIn("Opciones técnicas del último reporte", app_js)
        self.assertIn("Abrir reporte interactivo", app_js)
        self.assertIn("Copiar URL JSON", app_js)
        self.assertIn('data-latest-action="open-folder"', app_js)
        self.assertIn("Descargar Markdown", app_js)
        self.assertIn("Descargar JSON", app_js)
        self.assertIn("Descargar CSV", app_js)
        self.assertIn("a.setAttribute('download', action.name)", app_js)
        self.assertIn("Los artefactos se muestran por tipo", app_js)
        self.assertIn('<details class="actions-help-panel"', index_html)
        self.assertIn("¿Qué hace cada botón utilitario?", index_html)
        self.assertIn("Ayuda opcional para no distraer", index_html)
        self.assertIn('<details class="metrics-guide"', index_html)
        self.assertIn("Guía rápida opcional", index_html)
        self.assertIn(".actions-help-panel", app_css)
        self.assertIn(".actions-help-summary-hint", app_css)
        self.assertIn(".latest-report-details", app_css)
        self.assertIn(".latest-report-details-body", app_css)
        self.assertIn(".latest-report-actions", app_css)
        self.assertIn(".latest-report-action-row-secondary", app_css)
        self.assertIn(".metrics-guide-summary-hint", app_css)
        self.assertNotIn("Ver último HTML", index_html)

    def test_advanced_filters_are_compact_and_help_is_on_demand(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        panel_start = index_html.index('<details class="advanced-filters-panel">')
        panel_end = index_html.index("</details>", index_html.index('class="advanced-filters-help"'))
        panel_markup = index_html[panel_start:panel_end]

        self.assertIn("Filtros avanzados", panel_markup)
        self.assertIn("Opcional: precio, reseñas, Deck, CSV/cache", panel_markup)
        self.assertIn("Déjalos vacíos para usar el flujo normal", panel_markup)
        self.assertIn('class="advanced-filters-help"', panel_markup)
        self.assertIn("Ayuda rápida de filtros avanzados", panel_markup)
        self.assertIn("Vacío = sin límite.", panel_markup)
        self.assertIn("Vacío = cualquier porcentaje.", panel_markup)
        self.assertIn("Wishlist pública del amigo.", panel_markup)
        self.assertNotIn("Deja fuera juegos que superen ese tope", panel_markup)
        self.assertNotIn("Muestra solo juegos con al menos ese porcentaje", panel_markup)
        self.assertIn(".advanced-filters-summary", app_css)
        self.assertIn(".advanced-filters-help-grid", app_css)
        self.assertIn(".advanced-filters-intro", app_css)

    def test_execution_log_copy_uses_native_bridge_then_browser_clipboard(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        copy_text_start = app_js.index("async function copyExecutionLogText(text)")
        copy_start = app_js.index("async function copyExecutionLog()")
        copy_text_block = app_js[copy_text_start:copy_start]
        copy_end = app_js.index("async function downloadExecutionLog()")
        copy_block = app_js[copy_start:copy_end]

        self.assertIn("async function exportExecutionLogText", app_js)
        self.assertIn("/api/log/export", app_js)
        self.assertNotIn("/api/log/copy", app_js)
        self.assertIn("async function copyExecutionLogText", app_js)
        self.assertIn("const IS_DESKTOP_NATIVE", app_js)
        self.assertIn("pywebviewready", app_js)
        self.assertIn("copy_text_to_clipboard", copy_text_block)
        self.assertIn("navigator.clipboard.writeText(text)", copy_text_block)
        self.assertIn("await copyExecutionLogText(text)", copy_block)
        self.assertIn("Usa Descargar log (.txt).", copy_text_block)
        self.assertIn('id="log-safety-hint"', index_html)
        self.assertIn("Log seguro", index_html)
        self.assertIn("[Redactado]", index_html)
        self.assertIn("[Ruta]", index_html)
        self.assertNotIn("copyTextWithFallback", copy_block)
        self.assertNotIn("execCommand", copy_block)
        self.assertNotIn("window.prompt('Copia este log:'", app_js)

    def test_steam_deals_mutable_requests_send_local_csrf_header(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("const LOCAL_CSRF_HEADER = 'X-Steam-Tools-Local-Token'", app_js)
        self.assertIn('meta[name="steam-tools-local-token"]', app_js)
        self.assertIn("function localMutableFetch", app_js)
        for endpoint in (
            "/api/config",
            "/api/preflight",
            "/api/desktop-doctor",
            "/api/desktop-doctor/fix",
            "/api/cache/clear",
            "/api/open-output-folder",
            "/api/log/export",
            "/api/run",
            "/api/stop",
            "/api/run-pd2",
            "/api/watchlist",
            "/api/watchlist/delete",
            "/api/selection-review",
        ):
            self.assertIn(f"localMutableFetch('{endpoint}'", app_js)
        self.assertNotIn("steam-tools-local-token", index_html)

    def test_desktop_forced_web_fallback_has_user_visible_hint(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("'forced-web-fallback'", app_js)
        self.assertIn("Fallback web forzado", app_js)
        self.assertIn("desktop_fallback", app_js)

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
        self.assertIn("source.appid || source.steam_appid", app_js)
        self.assertIn("historical_low", app_js)
        self.assertIn("steam_appid: appid", app_js)
        self.assertIn("historical_low: minHistLabel", app_js)
        self.assertIn("steam_url: steamUrl", app_js)
        self.assertIn("v: Number(source.v || fallbackDeal.v || 1) || 1", app_js)
        self.assertIn("'steamtools://share?data=' + encoded", app_js)
        self.assertNotIn("Compartir Deal", index_html)
        self.assertNotIn("Compartir Top Picks", app_js)
        self.assertNotIn("payload más reciente", app_js)

    def test_latest_report_renders_recommended_collections(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestRecommendedCollections", app_js)
        self.assertIn("report.recommended_collections", app_js)
        self.assertIn("data-latest-recommended-collections", app_js)
        self.assertIn("data-latest-recommended-collection", app_js)
        self.assertIn("Colecciones recomendadas", app_js)
        self.assertIn("Atajos curados desde el último reporte", app_js)
        self.assertIn("latestRecommendedCollectionItemKey", app_js)
        self.assertIn("renderLatestReportDetails(activeReport, files)", app_js)
        self.assertIn("renderLatestRecommendedCollections(report)", app_js)
        self.assertIn(".latest-collections-section", app_css)
        self.assertIn(".latest-collections-grid", app_css)
        self.assertIn(".latest-collection-card", app_css)
        self.assertIn(".latest-collection-item-meta", app_css)

    def test_latest_report_renders_personalized_recommendations_inside_details(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestPersonalizedRecommendations", app_js)
        self.assertIn("report.personalized_recommendations", app_js)
        self.assertIn("data-latest-personalized-recommendations", app_js)
        self.assertIn("data-latest-personalized-recommendation", app_js)
        self.assertIn("latestActivitySummaryChips", app_js)
        self.assertIn("activity_summary", app_js)
        self.assertIn("Actividad local", app_js)
        self.assertIn("Más jugado", app_js)
        self.assertIn("items.slice(0, 3)", app_js)
        self.assertIn("renderLatestPersonalizedRecommendations(report, files)", app_js)
        self.assertIn("renderLatestReportDetails(activeReport, files)", app_js)
        self.assertIn("Recomendaciones personalizadas", app_js)
        self.assertIn("Ver detalle HTML", app_js)
        self.assertIn("Ver JSON completo", app_js)
        self.assertIn(".latest-personalized-section", app_css)
        self.assertIn(".latest-personalized-list", app_css)
        self.assertIn(".latest-personalized-item", app_css)
        self.assertIn(".latest-personalized-footer", app_css)

    def test_latest_report_renders_gift_ideas_inside_details(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestGiftIdeas", app_js)
        self.assertIn("report.gift_ideas", app_js)
        self.assertIn("data-latest-gift-ideas", app_js)
        self.assertIn("data-latest-gift-idea", app_js)
        self.assertIn("function latestGiftIdeaReasons", app_js)
        self.assertIn("source.social_reasons", app_js)
        self.assertIn("Regalos${escapeHtml(friendCopy)}", app_js)
        self.assertIn("razones sociales compactas", app_js)
        self.assertIn("No abre carrito ni compra nada", app_js)
        self.assertIn("compareData.friend_name || compareData.friend_vanity", app_js)
        self.assertIn("items.slice(0, 3)", app_js)
        self.assertIn("renderLatestGiftIdeas(report)", app_js)
        self.assertIn("renderLatestReportDetails(activeReport, files)", app_js)
        self.assertIn(".latest-gift-section", app_css)
        self.assertIn(".latest-gift-list", app_css)
        self.assertIn(".latest-gift-item", app_css)
        self.assertIn(".latest-gift-item-reasons", app_css)

    def test_latest_report_renders_wishlist_hygiene_inside_details(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestWishlistHygiene", app_js)
        self.assertIn("report.wishlist_hygiene", app_js)
        self.assertIn("data-latest-wishlist-hygiene", app_js)
        self.assertIn("data-latest-wishlist-hygiene-item", app_js)
        self.assertIn("function latestWishlistHygieneSignalLabel", app_js)
        self.assertIn("items.slice(0, 3)", app_js)
        self.assertIn("Revisar wishlist", app_js)
        self.assertIn("Solo revisión", app_js)
        self.assertIn("No borra ni auto-excluye", app_js)
        self.assertIn("más en el JSON completo", app_js)
        self.assertIn("const safeAppid = /^\\d+$/.test(appid) ? appid : '';", app_js)
        self.assertIn("https://store.steampowered.com/app/${escapeHtml(safeAppid)}/", app_js)
        self.assertIn("renderLatestWishlistHygiene(report)", app_js)
        self.assertIn("renderLatestReportDetails(activeReport, files)", app_js)
        self.assertIn(".latest-wishlist-section", app_css)
        self.assertIn(".latest-wishlist-list", app_css)
        self.assertIn(".latest-wishlist-item", app_css)
        self.assertIn(".latest-wishlist-item-signals", app_css)

    def test_latest_report_surfaces_active_promo_context_inside_details(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestPromoContext", app_js)
        self.assertIn("meta.active_promo_context", app_js)
        self.assertIn("LATEST_PROMO_CATEGORY_LABELS", app_js)
        self.assertIn("LATEST_PROMO_CATEGORY_PRIORITY", app_js)
        self.assertIn("function latestPromoDisplayLabel", app_js)
        self.assertIn("function latestPromoPrimaryPromo", app_js)
        self.assertIn("context.display_label", app_js)
        self.assertIn("promos adicionales", app_js)
        self.assertIn("data-latest-promo-context", app_js)
        self.assertIn("Contexto de promo activa", app_js)
        self.assertIn("Promo detectada con más peso", app_js)
        self.assertIn("Promo destacada", app_js)
        self.assertIn("context.simultaneous_hint", app_js)
        self.assertIn("context.decision_hint", app_js)
        self.assertIn("latest-promo-hint", app_js)
        self.assertIn("Lanzamiento", app_js)
        self.assertIn("no es predicción ni cambia el score", app_js)
        self.assertIn("También activas", app_js)
        self.assertIn("renderLatestPromoContext(report)", app_js)
        self.assertIn("renderLatestReportDetails(activeReport, files)", app_js)
        self.assertIn(".latest-promo-section", app_css)
        self.assertIn(".latest-promo-pills", app_css)
        self.assertIn(".latest-promo-extra", app_css)
        self.assertIn(".latest-promo-hint", app_css)

    def test_latest_report_surfaces_partial_cache_coverage(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestCacheCoverage", app_js)
        self.assertIn("report.cache_coverage", app_js)
        self.assertIn("data-latest-cache-coverage", app_js)
        self.assertIn("Caché parcial", app_js)
        self.assertIn("pendientes por confirmar", app_js)
        self.assertIn("Las ofertas mostradas pueden no incluir juegos aún no verificados", app_js)
        self.assertIn("misma caché, en una corrida normal con --warm-cache y sin --no-cache", app_js)
        self.assertIn("function renderLatestCacheStateSummary", app_js)
        self.assertIn("coverage.state_summary", app_js)
        self.assertIn("Estados derivados", app_js)
        self.assertIn("function renderLatestNoPriceClassification", app_js)
        self.assertIn("coverage.no_price_classification_counts", app_js)
        self.assertIn("data-latest-no-price-classification", app_js)
        self.assertIn("Juegos sin precio clasificados", app_js)
        self.assertIn("Juegos por salir", app_js)
        self.assertIn("Gratis o sin precio normal", app_js)
        self.assertIn("Revisar disponibilidad", app_js)
        self.assertIn("No confirmado todavía", app_js)
        self.assertIn("Sin precio confirmado", app_js)
        self.assertIn("Solo revisión: estas categorías no eliminan juegos", app_js)
        self.assertIn("no cambian ranking", app_js)
        self.assertIn("no prueban que un juego esté retirado", app_js)
        self.assertIn("data-latest-action=\"continue-warm-cache\"", app_js)
        self.assertIn("data-latest-cache-continue-status", app_js)
        self.assertIn("role=\"status\" aria-live=\"polite\"", app_js)
        self.assertIn("function buildWarmCacheContinueFilters", app_js)
        self.assertIn("function setWarmCacheContinueStatus", app_js)
        self.assertIn("filters.warm_cache = true", app_js)
        self.assertIn("filters.no_cache = false", app_js)
        self.assertIn("Continuando warm-cache...", app_js)
        self.assertIn(
            "Continuando con la misma caché: revalidando otra tanda con --warm-cache, sin --no-cache.",
            app_js,
        )
        self.assertIn("Continuación warm-cache finalizada", app_js)
        self.assertIn("No se pudo continuar warm-cache", app_js)
        self.assertIn("Continuando warm-cache con la caché actual (sin --no-cache).", app_js)
        self.assertIn("renderLatestCacheCoverage(activeReport)", app_js)
        self.assertIn(".latest-cache-coverage", app_css)
        self.assertIn(".latest-cache-coverage-copy", app_css)
        self.assertIn(".latest-cache-state-summary", app_css)
        self.assertIn(".latest-cache-no-price", app_css)
        self.assertIn(".latest-cache-no-price-pills", app_css)
        self.assertIn(".latest-cache-no-price-samples", app_css)
        self.assertIn(".latest-cache-coverage-action", app_css)
        self.assertIn(".latest-cache-continue-status", app_css)
        self.assertIn(".latest-cache-continue-status-progress", app_css)

    def test_warm_cache_continue_uses_internal_background_banner(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function warmCacheBackgroundBannerEl", app_js)
        self.assertIn("data-warm-cache-background-banner", app_js)
        self.assertIn("role', 'status'", app_js)
        self.assertIn("aria-live', 'polite'", app_js)
        self.assertIn("function setWarmCacheBackgroundBanner", app_js)
        self.assertIn("function updateWarmCacheBackgroundBannerFromEvent", app_js)
        self.assertIn("function refreshLatestReportSummaryFromBanner", app_js)
        self.assertIn("data-warm-cache-refresh-summary", app_js)
        self.assertIn("preserveOutputFiles: true", app_js)
        self.assertIn("preserveLatestReportOnDone: true", app_js)
        self.assertIn("updateWarmCacheBackgroundBannerFromEvent", app_js)
        self.assertIn("preserveLatestReportOnDone === true && !hasFiles", app_js)
        self.assertIn("Puedes seguir revisando el último reporte", app_js)
        self.assertIn("se usa --warm-cache, sin --no-cache", app_js)
        self.assertIn("Caché actualizada; refresca el resumen", app_js)
        self.assertIn("No se asume cobertura completa si todavía quedan pendientes/deferred", app_js)
        self.assertIn("Refrescar resumen", app_js)
        self.assertIn(".warm-cache-background-banner", app_css)
        self.assertIn(".warm-cache-background-banner-progress", app_css)
        self.assertIn(".warm-cache-background-banner-ok", app_css)
        self.assertIn(".warm-cache-background-banner-warn", app_css)
        self.assertIn(".warm-cache-background-refresh", app_css)

    def test_latest_report_renders_selection_review_ui_inside_details(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestSelectionReviewPanel", app_js)
        self.assertIn("buildLatestSelectionCandidates(report)", app_js)
        self.assertIn("data-latest-selection-review", app_js)
        self.assertIn("data-selection-candidate", app_js)
        self.assertIn("data-selection-input", app_js)
        self.assertIn("data-selection-evaluate", app_js)
        self.assertIn("localMutableFetch('/api/selection-review'", app_js)
        self.assertIn("function latestSelectionSignalLabel", app_js)
        self.assertIn("latest-selection-result-signals", app_js)
        self.assertIn("Señales:", app_js)
        self.assertIn("renderLatestSelectionReviewPanel(report)", app_js)
        self.assertIn("bindLatestSelectionReviewActions()", app_js)
        self.assertIn("Evalúa mi selección", app_js)
        self.assertIn("No abre carrito ni compra nada", app_js)
        self.assertIn("conservar", app_js)
        self.assertIn("dudar", app_js)
        self.assertIn("quitar", app_js)
        self.assertIn(".latest-selection-section", app_css)
        self.assertIn(".latest-selection-candidates", app_css)
        self.assertIn(".latest-selection-result-list", app_css)
        self.assertIn(".latest-selection-result-conservar", app_css)
        self.assertIn(".latest-selection-result-signals", app_css)

    def test_selection_review_ui_keeps_no_commerce_copy_guardrail(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        panel_start = app_js.index("function renderLatestSelectionReviewPanel")
        panel_end = app_js.index("function latestSelectionRecordsFromText", panel_start)
        panel_block = app_js[panel_start:panel_end]

        self.assertIn("Simulador local", panel_block)
        self.assertIn("No abre carrito ni compra nada", panel_block)
        self.assertIn("Usa datos del último JSON local", panel_block)
        self.assertNotIn("checkout", panel_block.lower())
        self.assertNotIn("pago", panel_block.lower())
        self.assertNotIn("Fanatical", panel_block)
        self.assertNotIn("tienda externa", panel_block.lower())
        self.assertNotIn("Abrir carrito", panel_block)
        self.assertNotIn("Comprar ahora", panel_block)
        self.assertNotIn("remoción automática", panel_block.lower())

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
        self.assertIn("Carpeta de reportes", index_html)
        self.assertIn("Generar reportes", index_html)
        self.assertIn("/api/open-output-folder", app_js)
        self.assertIn("openOutputFolderUI", app_js)
        self.assertIn("GENERATED_FILE_ACTION_GROUPS", app_js)
        self.assertIn("HTML interactivo", app_js)
        self.assertIn("Share HTML", app_js)
        self.assertIn("Carpeta local", app_js)
        self.assertIn(".file-link-group", app_css)
        self.assertIn(".file-link-button", app_css)

    def test_primary_run_actions_precede_secondary_deals_sections(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        run_button_index = index_html.index('id="btn-run"')
        utility_actions_index = index_html.index('id="btn-preflight"')
        watchlist_index = index_html.index("Alertas de precio")
        history_index = index_html.index('id="history-card"')
        pd2_panel_index = index_html.index('id="panel-pd2"')

        self.assertIn('id="panel-deals-secondary"', index_html)
        self.assertLess(pd2_panel_index, run_button_index)
        self.assertLess(utility_actions_index, watchlist_index)
        self.assertLess(run_button_index, watchlist_index)
        self.assertLess(run_button_index, history_index)
        self.assertIn("const dealsSecondaryPanel = $('panel-deals-secondary');", app_js)
        self.assertIn(
            "if (dealsSecondaryPanel) dealsSecondaryPanel.style.display = isPd2 ? 'none' : 'block';",
            app_js,
        )

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

    def test_payday2_mutable_requests_send_local_csrf_header(self) -> None:
        index_html = (ROOT / "web" / "payday2" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "payday2" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("const LOCAL_CSRF_HEADER = 'X-Steam-Tools-Local-Token'", app_js)
        self.assertIn('meta[name="steam-tools-local-token"]', app_js)
        self.assertIn("function localMutableFetch", app_js)
        for endpoint in (
            "/api/toggle",
            "/api/toggle-bundle",
            "/api/refresh",
            "/api/config",
        ):
            self.assertIn(f"localMutableFetch('{endpoint}'", app_js)
        self.assertIn("fetch('/api/data')", app_js)
        self.assertIn("fetch('/api/config')", app_js)
        self.assertNotIn("steam-tools-local-token", index_html)

    def test_payday2_cache_status_and_force_refresh_are_visible(self) -> None:
        index_html = (ROOT / "web" / "payday2" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "payday2" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "payday2" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="btn-force-refresh"', index_html)
        self.assertIn('id="cache-status-card"', index_html)
        self.assertIn("Actualizar datos respeta caché/TTL", index_html)
        self.assertIn("no borra tus marcados manuales", index_html)
        self.assertIn("function renderCacheStatus", app_js)
        self.assertIn("function setRefreshButtonsBusy", app_js)
        self.assertIn("setRefreshButtonsBusy(true)", app_js)
        self.assertIn("doRefresh({ force: true })", app_js)
        self.assertIn("JSON.stringify(force ? { force: true } : {})", app_js)
        self.assertIn("status.diagnostic", app_js)
        self.assertIn("Actualizar datos = refresh normal con caché/TTL", app_js)
        self.assertIn("Forzar catálogo = --no-cache", app_js)
        self.assertIn("no inventa DLCs que Steam no expone", app_js)
        self.assertIn("Actualizando datos de PAYDAY 2 con caché/TTL normal", app_js)
        self.assertIn("Forzando catálogo PAYDAY 2 con --no-cache", app_js)
        self.assertIn(
            "Steam puede no exponerlo",
            (ROOT / "payday2_web.py").read_text(encoding="utf-8"),
        )
        self.assertIn(".cache-status-card", app_css)
        self.assertIn(".cache-refresh-help", app_css)
        self.assertIn(".refresh-mode-help", app_css)
        self.assertIn(".btn-refresh-secondary", app_css)

    def test_payday2_force_refresh_adds_no_cache_without_secret_argv(self) -> None:
        cmd, proc_env = payday2_web.build_refresh_command_and_env(
            {"vanity": "wolf", "key": "SECRET-KEY"},
            force_refresh=True,
        )
        normal_cmd, _normal_env = payday2_web.build_refresh_command_and_env(
            {"vanity": "wolf", "key": "SECRET-KEY"},
        )

        self.assertIn("--no-cache", cmd)
        self.assertNotIn("--no-cache", normal_cmd)
        self.assertNotIn("SECRET-KEY", " ".join(cmd))
        self.assertIn("SECRET-KEY", proc_env.values())
        self.assertEqual(
            (payday2_web.parse_force_refresh_flag({"force": True}),
             payday2_web.parse_force_refresh_flag({"force_refresh": "true"}),
             payday2_web.parse_force_refresh_flag({"force": "false"}),
             payday2_web.parse_force_refresh_flag({})),
            (True, True, False, False),
        )

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

    def test_desktop_dependency_installs_use_constraints(self) -> None:
        constraints = (ROOT / "constraints" / "desktop.txt").read_text(
            encoding="utf-8"
        )
        install_cmd = build_desktop.build_dependency_install_command()

        self.assertIn("pyinstaller==6.20.0", constraints)
        self.assertIn("pywebview==6.2.1", constraints)
        self.assertIn("PyQt6==6.11.0", constraints)
        self.assertIn(str(ROOT / "requirements-desktop.txt"), install_cmd)
        self.assertIn("-c", install_cmd)
        self.assertIn(str(ROOT / "constraints" / "desktop.txt"), install_cmd)


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

    def test_buy_now_uses_importance_not_only_big_discount(self) -> None:
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
                "orig_raw": 12800,
                "discount": 50,
            },
        ]

        rec = payday2_dlc_tracker.compute_recommendations(
            missing, budget=None, alert_price=None, min_deal=50
        )

        self.assertEqual(
            [d["steam_name"] for d in rec["buy_now"]],
            ["PAYDAY 2: Important Bank Heist"],
        )
        self.assertEqual(rec["buy_now"][0]["purchase_label"], "Comprar ahora")
        self.assertIn("Contenido jugable prioritario", rec["buy_now"][0]["purchase_reasons"])
        self.assertEqual(
            [d["steam_name"] for d in rec["review_deals"]],
            ["PAYDAY 2: Very Cheap Tailor Pack"],
        )
        self.assertEqual(rec["review_deals"][0]["purchase_action"], "review")

    def test_general_dlc_can_be_buy_now_when_price_is_compelling(self) -> None:
        missing = [
            {
                "appid": "300",
                "steam_name": "PAYDAY 2: Legacy Pack",
                "price_raw": 4900,
                "price_fmt": "Mex$ 49.00",
                "orig_raw": 9800,
                "discount": 50,
            }
        ]

        rec = payday2_dlc_tracker.compute_recommendations(
            missing, budget=None, alert_price=None, min_deal=50
        )

        self.assertEqual([d["appid"] for d in rec["buy_now"]], ["300"])
        self.assertIn("Buen valor para completar", rec["buy_now"][0]["purchase_reasons"])

    def test_payday2_web_payload_exposes_budget_value_metadata(self) -> None:
        original_store = copy.deepcopy(payday2_web._store)
        all_dlcs = {
            "200": {
                "appid": "200",
                "steam_name": "PAYDAY 2: Important Bank Heist",
                "price_raw": 6400,
                "price_fmt": "Mex$ 64.00",
                "orig_raw": 12800,
                "orig_fmt": "",
                "discount": 50,
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
                        "cache_status": {
                            "source": "Steam appdetails data.dlc del app 218620",
                            "catalog": {"count": 1, "ageHours": 2.0, "ttlHours": 168, "stale": False},
                            "names": {"count": 1, "ageHours": 2.0, "ttlHours": 168, "stale": False},
                            "prices": {"count": 1, "ageHours": 2.0, "ttlHours": 24, "stale": False},
                            "bundles": {"count": 0, "ageHours": None, "ttlHours": 168, "stale": True},
                            "diagnostic": "diagnóstico seguro",
                        },
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
        self.assertEqual(payload["buyNow"][0]["importanceTier"], "S")
        self.assertEqual(payload["buyNow"][0]["recommendationLabel"], "Comprar ahora")
        self.assertIn("Contenido jugable prioritario", payload["buyNow"][0]["recommendationReasons"])
        self.assertEqual(payload["cacheStatus"]["catalog"]["count"], 1)

    def test_payday2_cache_status_payload_reports_counts_and_staleness(self) -> None:
        payload = payday2_web.build_cache_status_payload(
            dlc_list_cache={"appids": ["10", "20"], "saved_at": "2026-05-05T00:00:00"},
            dlc_list_age=2.0,
            mapping_cache={"names": {"10": "A"}},
            mapping_age=3.0,
            prices_cache={"prices": {"10": {}}},
            prices_age=30.0,
            bundles_cache={"bundles": [{"bundle_id": "1"}]},
            bundles_age=float("inf"),
        )

        self.assertEqual(payload["source"], "Steam appdetails data.dlc del app 218620")
        self.assertEqual(payload["catalog"]["count"], 2)
        self.assertEqual(payload["prices"]["count"], 1)
        self.assertEqual(payload["prices"]["stale"], True)
        self.assertIsNone(payload["bundles"]["ageHours"])
        self.assertIn("Steam puede no exponerlo", payload["diagnostic"])


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
