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
        self.assertIn("renderLatestReportQuickSummary", app_js)
        self.assertIn("renderLatestPrimaryReportAction", app_js)
        self.assertIn("renderLatestReportActionsPanel", app_js)
        self.assertIn("renderLatestRecommendationsPanel", app_js)
        self.assertIn("renderLatestReportToolsPanel", app_js)
        self.assertIn("function renderLatestReportIntentWrapper", app_js)
        self.assertIn("function latestReportIntents", app_js)
        self.assertIn("function latestReportIntentKeyFromHash", app_js)
        self.assertIn("function isLatestReportIntentHash", app_js)
        self.assertIn("function syncLatestReportIntentActiveState", app_js)
        self.assertIn("function bindLatestReportIntentToolbarActions", app_js)
        self.assertIn("renderLatestReportDetails", app_js)
        self.assertIn('data-latest-report-quick-summary', app_js)
        self.assertIn('data-latest-report-intent-wrapper', app_js)
        self.assertIn('data-latest-report-intent-intro', app_js)
        self.assertIn('data-latest-report-intent-toolbar', app_js)
        self.assertIn("function renderLatestReportIntentIntro", app_js)
        self.assertIn("key: 'review'", app_js)
        self.assertIn("key: 'history'", app_js)
        self.assertIn("Selector del último reporte", app_js)
        self.assertIn("Elige qué quieres revisar", app_js)
        self.assertIn("Cambia de vista sin recalcular nada", app_js)
        self.assertIn("Atajo: usa ←/→, Home o End", app_js)
        self.assertIn("Sin cambios de datos", app_js)
        self.assertIn("function setLatestReportIntentHash", app_js)
        self.assertIn("function activateLatestReportIntentTab", app_js)
        self.assertIn("function handleLatestReportIntentTabKeydown", app_js)
        self.assertIn('aria-current="true"', app_js)
        self.assertIn('role="tablist"', app_js)
        self.assertIn('aria-describedby="latest-report-intent-help"', app_js)
        self.assertIn('role="tab" aria-selected="${isActive ? \'true\' : \'false\'}"', app_js)
        self.assertIn('role="tabpanel" tabindex="0"', app_js)
        self.assertIn('data-latest-report-intent-tab="${escapeHtml(intent.key)}"', app_js)
        self.assertIn('data-latest-report-intent-section="${escapeHtml(intent.key)}"', app_js)
        self.assertIn("classList.toggle('is-active', isActive)", app_js)
        self.assertIn("tab.setAttribute('aria-current', 'true')", app_js)
        self.assertIn("tab.setAttribute('aria-selected', 'true')", app_js)
        self.assertIn("tab.removeAttribute('aria-current')", app_js)
        self.assertIn("tab.setAttribute('aria-selected', 'false')", app_js)
        self.assertIn("panel.hidden = !isActive", app_js)
        self.assertIn("event.preventDefault()", app_js)
        self.assertIn("key === 'ArrowRight'", app_js)
        self.assertIn("key === 'Home'", app_js)
        self.assertIn("activateLatestReportIntentTab(tabs[nextIndex], { focus: true })", app_js)
        self.assertIn("window.history.replaceState(null, '', hash)", app_js)
        self.assertIn("if (isLatestReportIntentHash()) syncLatestReportIntentActiveState()", app_js)
        self.assertIn("bindLatestReportIntentToolbarActions()", app_js)
        self.assertIn('<details class="latest-report-details latest-report-actions-panel">', app_js)
        self.assertIn('<details class="latest-report-details latest-report-recommendations-panel">', app_js)
        self.assertIn('<details class="latest-report-details latest-report-tools-panel">', app_js)
        self.assertIn("Revisar reporte", app_js)
        self.assertIn("Resumen rápido", app_js)
        self.assertIn("Última ejecución", app_js)
        self.assertIn("Resultado rápido:", app_js)
        self.assertIn("Acciones del reporte", app_js)
        self.assertIn("Recomendaciones y señales", app_js)
        self.assertIn("Herramientas del reporte", app_js)
        self.assertIn("Histórico/continuar", app_js)
        self.assertIn("Ir al histórico", app_js)
        self.assertIn("Secciones del último reporte por intención", app_js)
        self.assertIn("renderLatestReportIntentWrapper(activeReport, meta, summary, files)", app_js)
        self.assertIn("HTML interactivo, Share, JSON técnico y carpeta", app_js)
        self.assertIn("renderLatestSmartAlertDigest", app_js)
        self.assertIn("data-latest-smart-alert-digest", app_js)
        self.assertIn("No envía Telegram/Discord ni activa notificaciones por juego", app_js)
        self.assertIn(".latest-smart-alert-digest", app_css)
        self.assertIn(".latest-smart-alert-section", app_css)
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
        self.assertIn(".latest-report-quick-summary", app_css)
        self.assertIn(".latest-report-intent-wrapper", app_css)
        self.assertIn(".latest-report-intent-intro", app_css)
        self.assertIn(".latest-report-intent-intro-badge", app_css)
        self.assertIn(".latest-report-intent-toolbar", app_css)
        self.assertIn(".latest-report-intent-tab:focus-visible", app_css)
        self.assertIn('.latest-report-intent-tab[aria-selected="true"]', app_css)
        self.assertIn('.latest-report-intent-tab[aria-selected="true"] strong::after', app_css)
        self.assertIn('content: "Activa"', app_css)
        self.assertIn(".latest-report-intent-section", app_css)
        self.assertIn(".latest-report-intent-section[hidden]", app_css)
        self.assertIn(".latest-report-intent-section.is-active", app_css)
        self.assertIn(".latest-report-history-card", app_css)
        self.assertIn(".latest-report-sections", app_css)
        self.assertIn(".latest-report-primary-action", app_css)
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

    def test_wishlist_external_matches_import_is_visible_and_advisory_only(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("Matches externos wishlist (JSON)", index_html)
        self.assertIn('id="wishlist_external_matches_json"', index_html)
        self.assertIn("Import local advisory-only", index_html)
        self.assertIn("No borra, no auto-excluye y no cambia el score", index_html)
        self.assertIn("wishlist_external_matches_json", app_js)
        self.assertIn(
            "'wishlist_external_matches_json'",
            app_js,
        )

    def test_itad_external_offers_cache_import_is_visible_and_local_only(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("Caché ITAD external_offers (JSON)", index_html)
        self.assertIn('id="itad_external_offers_cache"', index_html)
        self.assertIn("Import local de precios ITAD", index_html)
        self.assertIn("No hace red live por sí solo", index_html)
        self.assertIn("no prueba ownership", index_html)
        self.assertIn("no cambia score, ranking ni wishlist hygiene", index_html)
        self.assertIn("itad_external_offers_cache", app_js)
        self.assertIn(
            "'itad_external_offers_cache'",
            app_js,
        )

    def test_hltb_path_copy_handles_windows_paths_without_quotes(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("CSV de HowLongToBeat", index_html)
        self.assertIn("C:/Users/TuUsuario/Downloads/HLTB_Games_2026-05-15.csv", index_html)
        self.assertNotIn("Bryan Grijalva", index_html)
        self.assertIn("En Web/Desktop no uses comillas", index_html)
        self.assertIn("rutas de Windows con espacios", index_html)
        self.assertIn("se envían como un solo argumento", index_html)
        self.assertIn("[ruta]", index_html)
        self.assertIn('id="hltb-autodetect-suggestion"', index_html)
        self.assertIn("hltb_autodetect", app_js)
        self.assertIn("No se usará automáticamente", app_js)
        self.assertIn("'hltb'", app_js)

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
        self.assertIn("renderLatestReportIntentWrapper(activeReport, meta, summary, files)", app_js)
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
        self.assertIn("renderLatestReportIntentWrapper(activeReport, meta, summary, files)", app_js)
        self.assertIn("Recomendaciones personalizadas", app_js)
        self.assertIn("Ver detalle HTML", app_js)
        self.assertIn("Ver JSON completo", app_js)
        self.assertIn(".latest-personalized-section", app_css)
        self.assertIn(".latest-personalized-list", app_css)
        self.assertIn(".latest-personalized-item", app_css)
        self.assertIn(".latest-personalized-footer", app_css)

    def test_latest_report_renders_taste_priority_advisory_inside_details(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestTastePriority", app_js)
        self.assertIn("function latestTastePriorityPayload", app_js)
        self.assertIn("function latestTastePriorityItems", app_js)
        self.assertIn("function latestTastePrioritySignals", app_js)
        self.assertIn("LATEST_TASTE_PRIORITY_CATEGORY_LABELS", app_js)
        self.assertIn("report.taste_priority", app_js)
        self.assertIn("data-latest-taste-priority", app_js)
        self.assertIn("data-latest-taste-priority-appid", app_js)
        self.assertIn("items.filter(item => item && typeof item === 'object')", app_js)
        self.assertIn("items.slice(0, 3)", app_js)
        self.assertIn("Prioridad por gustos", app_js)
        self.assertIn("Sin impacto en ranking", app_js)
        self.assertIn("Advisory-only", app_js)
        self.assertIn("no cambia score, ranking, Top Picks, defaults, cache ni fetching", app_js)
        self.assertIn("no cambia score, ranking ni Top Picks", app_js)
        self.assertIn("renderLatestTastePriority(report)", app_js)
        self.assertIn("renderLatestReportIntentWrapper(activeReport, meta, summary, files)", app_js)
        self.assertNotIn("data-share-taste-priority", app_js)
        self.assertNotIn("renderLatestShareTastePriority", app_js)
        self.assertIn(".latest-taste-priority-section", app_css)
        self.assertIn(".latest-taste-priority-list", app_css)
        self.assertIn(".latest-taste-priority-item", app_css)
        self.assertIn(".latest-taste-priority-badge", app_css)
        self.assertIn(".latest-taste-priority-more", app_css)

    def test_latest_report_renders_advisory_offer_highlights(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function latestOfferHighlight", app_js)
        self.assertIn("function renderLatestOfferHighlight", app_js)
        self.assertIn("function latestOfferScoreReasons", app_js)
        self.assertIn("function latestOfferHistoricalLow", app_js)
        self.assertIn("function latestOfferNearHistoricalLow", app_js)
        self.assertIn("function latestOfferHasActivePromoSignal", app_js)
        self.assertIn("data-latest-offer-highlight", app_js)
        self.assertIn("score_reasons", app_js)
        self.assertIn("historical_lows", app_js)
        self.assertIn("meta.active_promo_context", app_js)
        self.assertIn("renderLatestOfferHighlight(pick, report)", app_js)
        self.assertIn("renderLatestOfferHighlight(source, report)", app_js)
        self.assertIn("Muy buena oferta", app_js)
        self.assertIn("Cerca de mínimo histórico", app_js)
        self.assertIn("Promo destacada", app_js)
        self.assertIn("Buena para revisar hoy", app_js)
        self.assertIn("Esperar mejor oferta", app_js)
        self.assertIn("Solo si ya estaba en tu radar", app_js)
        self.assertIn(".latest-offer-highlight", app_css)
        self.assertIn(".latest-offer-highlight-label", app_css)
        self.assertIn(".latest-offer-highlight-reason", app_css)

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
        self.assertIn("renderLatestReportIntentWrapper(activeReport, meta, summary, files)", app_js)
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
        self.assertIn("function latestWishlistHygieneCountLabel", app_js)
        self.assertIn("summary.total_wishlist_items", app_js)
        self.assertIn("summary.review_items_count", app_js)
        self.assertIn("items.slice(0, 3)", app_js)
        self.assertIn("Revisar wishlist", app_js)
        self.assertIn("Higiene local", app_js)
        self.assertIn("sugerencias para revisar", app_js)
        self.assertIn("juegos en wishlist", app_js)
        self.assertIn("Solo revisión", app_js)
        self.assertIn("Advisory-only", app_js)
        self.assertIn("No borra ni auto-excluye", app_js)
        self.assertIn("Razón para revisar", app_js)
        self.assertIn("Mostramos ${formatLatestCoverageCount(selectedItems.length)} aquí", app_js)
        self.assertIn("más en el JSON completo", app_js)
        self.assertIn("const safeAppid = /^\\d+$/.test(appid) ? appid : '';", app_js)
        self.assertIn("AppID ${appid}", app_js)
        self.assertIn("No tenemos nombre local para este AppID", app_js)
        self.assertIn("latest-wishlist-item-placeholder", app_js)
        self.assertIn("Sin link Steam seguro", app_js)
        self.assertIn("latest-wishlist-steam-link", app_js)
        self.assertIn("Abrir en Steam", app_js)
        self.assertIn("https://store.steampowered.com/app/${escapeHtml(safeAppid)}/", app_js)
        self.assertIn("renderLatestWishlistHygiene(report)", app_js)
        self.assertIn("renderLatestReportIntentWrapper(activeReport, meta, summary, files)", app_js)
        self.assertIn(".latest-wishlist-section", app_css)
        self.assertIn(".latest-wishlist-count", app_css)
        self.assertIn(".latest-wishlist-list", app_css)
        self.assertIn(".latest-wishlist-item", app_css)
        self.assertIn(".latest-wishlist-item-placeholder", app_css)
        self.assertIn(".latest-wishlist-item-signals", app_css)
        self.assertIn(".latest-wishlist-item-reason-label", app_css)
        self.assertIn(".latest-wishlist-item-actions", app_css)

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
        self.assertIn("renderLatestReportIntentWrapper(activeReport, meta, summary, files)", app_js)
        self.assertIn(".latest-promo-section", app_css)
        self.assertIn(".latest-promo-pills", app_css)
        self.assertIn(".latest-promo-extra", app_css)
        self.assertIn(".latest-promo-hint", app_css)

    def test_latest_report_surfaces_free_weekend_now_inside_details(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestFreeWeekendNow", app_js)
        self.assertIn("function latestFreeWeekendPayload", app_js)
        self.assertIn("function latestFreeWeekendConfidenceLabel", app_js)
        self.assertIn("function latestFreeWeekendCrossReasons", app_js)
        self.assertIn("function renderLatestFreeWeekendCross", app_js)
        self.assertIn("LATEST_FREE_WEEKEND_CONFIDENCE_LABELS", app_js)
        self.assertIn("report.free_weekend_now", app_js)
        self.assertIn("data-latest-free-weekend-now", app_js)
        self.assertIn("data-latest-free-weekend-appid", app_js)
        self.assertIn("source.cross_reasons", app_js)
        self.assertIn("source.cross_signals", app_js)
        self.assertIn("en tu wishlist", app_js)
        self.assertIn("ya en biblioteca", app_js)
        self.assertIn("similar a tus gustos", app_js)
        self.assertIn("Free Weekend ahora", app_js)
        self.assertIn("Señales locales/cache", app_js)
        self.assertIn("Revisa confianza y vigencia", app_js)
        self.assertIn("no cambia score, ranking ni caché de precios", app_js)
        self.assertIn("Activa el opt-in Free Weekend al generar", app_js)
        self.assertIn("no recalcula score ni invalida caché de precios", app_js)
        self.assertIn("Sin candidatos locales/cacheados de Free Weekend en el JSON actual", app_js)
        self.assertIn("renderLatestFreeWeekendNow(report)", app_js)
        self.assertIn("renderLatestReportIntentWrapper(activeReport, meta, summary, files)", app_js)
        self.assertIn(".latest-free-weekend-section", app_css)
        self.assertIn(".latest-free-weekend-list", app_css)
        self.assertIn(".latest-free-weekend-item", app_css)
        self.assertIn(".latest-free-weekend-cross", app_css)
        self.assertIn(".latest-free-weekend-empty", app_css)
        self.assertIn(".latest-free-weekend-badge", app_css)

    def test_latest_report_surfaces_external_offers_risk_gated_inside_details(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestExternalOffers", app_js)
        self.assertIn("function latestExternalOffersPayload", app_js)
        self.assertIn("function latestExternalOfferItems", app_js)
        self.assertIn("function latestExternalOfferSafeUrl", app_js)
        self.assertIn("LATEST_EXTERNAL_OFFER_VISIBLE_STORE_TYPES", app_js)
        self.assertIn("LATEST_EXTERNAL_OFFER_VISIBLE_STATES", app_js)
        self.assertIn("LATEST_EXTERNAL_OFFER_BLOCKING_RISKS", app_js)
        self.assertIn("LATEST_EXTERNAL_OFFER_CHECKOUT_RE", app_js)
        self.assertIn("report.external_offers", app_js)
        self.assertIn("data-latest-external-offers", app_js)
        self.assertIn("data-latest-external-offer-appid", app_js)
        self.assertIn("Comparativa externa", app_js)
        self.assertIn("Comparativa informativa", app_js)
        self.assertIn("no compra, no abre carrito", app_js)
        self.assertIn("no abre carrito ni checkout", app_js)
        self.assertIn("no abre carrito/checkout", app_js)
        self.assertIn("no verifica stock final", app_js)
        self.assertIn("no prueba ownership", app_js)
        self.assertIn("no cambia score, ranking ni wishlist hygiene", app_js)
        self.assertIn("Solo tiendas oficiales/autorizadas", app_js)
        self.assertIn("sin checkout", app_js)
        self.assertIn("Ver tienda (sin carrito)", app_js)
        self.assertIn("Sin link seguro", app_js)
        self.assertIn("renderLatestExternalOffers(report)", app_js)
        self.assertIn("renderLatestReportIntentWrapper(activeReport, meta, summary, files)", app_js)
        self.assertIn(".latest-external-offers-section", app_css)
        self.assertIn(".latest-external-offers-list", app_css)
        self.assertIn(".latest-external-offer-item", app_css)
        self.assertIn(".latest-external-offer-badge", app_css)
        self.assertIn(".latest-external-offer-link-disabled", app_css)
        self.assertIn(".latest-external-offer-link:focus-visible", app_css)
        self.assertIn("min-height: 32px", app_css)
        self.assertIn(".latest-external-offers-more", app_css)

    def test_advanced_filters_include_free_weekend_live_opt_in(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="free_weekend_live"', index_html)
        self.assertIn("Buscar Free Weekend ahora (opt-in)", index_html)
        self.assertIn("consulta señales Store JSON y usa cache separado", index_html)
        self.assertIn("'free_weekend_live'", app_js)

    def test_advanced_filters_include_itad_external_offers_refresh_opt_in(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="itad_refresh_external_offers_cache"', index_html)
        self.assertIn("Refrescar caché ITAD external_offers en vivo (opt-in)", index_html)
        self.assertIn("requiere ITAD key y ruta de caché", index_html)
        self.assertIn("sin cambiar score, ranking ni ownership", index_html)
        self.assertIn("'itad_refresh_external_offers_cache'", app_js)
        self.assertIn("const itadRefreshEl = $('itad_refresh_external_offers_cache')", app_js)
        self.assertIn("itadRefreshEl.checked = false", app_js)
        self.assertIn("itadRefreshEl.defaultChecked = false", app_js)
        self.assertIn("itadRefreshEl.removeAttribute('checked')", app_js)

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
        self.assertIn("latest-cache-details", app_js)
        self.assertIn("Ver detalles de caché", app_js)
        self.assertIn("Estados, bloques y juegos sin precio", app_js)
        self.assertIn("latest-cache-details-body", app_js)
        self.assertIn("function renderLatestCacheStateSummary", app_js)
        self.assertIn("coverage.state_summary", app_js)
        self.assertIn("Estados derivados", app_js)
        self.assertIn("function renderLatestFinalCacheStates", app_js)
        self.assertIn("coverage.final_state_summary", app_js)
        self.assertIn("data-latest-cache-final-states", app_js)
        self.assertIn("Cola resumible terminada", app_js)
        self.assertIn("deferred=0 indica que la cola resumible terminó", app_js)
        self.assertIn("no significa cobertura perfecta", app_js)
        self.assertIn("Precio confirmado/cache válido", app_js)
        self.assertIn("Fallos temporales/cooldown", app_js)
        self.assertIn("juegos sin precio confirmado", app_js)
        self.assertIn("function renderLatestFinalFailureActions", app_js)
        self.assertIn("coverage.final_failure_actions", app_js)
        self.assertIn("data-latest-cache-final-actions", app_js)
        self.assertIn("Acciones para fallidos finales", app_js)
        self.assertIn("Cierre seguro de warm-cache", app_js)
        self.assertIn("Espera antes de reintentar", app_js)
        self.assertIn("Retry seguro con warm-cache", app_js)
        self.assertIn("Solo revisión manual", app_js)
        self.assertIn("No borra juegos", app_js)
        self.assertIn("no excluye de la wishlist", app_js)
        self.assertIn("no cambia ranking", app_js)
        self.assertIn("no usa --no-cache", app_js)
        self.assertIn("Reintentar fallidos elegibles", app_js)
        self.assertIn("sin eliminar juegos", app_js)
        self.assertIn("function renderLatestNoPriceClassification", app_js)
        self.assertIn("coverage.no_price_classification_counts", app_js)
        self.assertIn("data-latest-no-price-classification", app_js)
        self.assertIn("function renderLatestWarmCacheBlockProgress", app_js)
        self.assertIn("coverage.block_progress", app_js)
        self.assertIn("data-latest-cache-block-progress", app_js)
        self.assertIn("Avance por bloques warm-cache", app_js)
        self.assertIn("Cobertura acumulada", app_js)
        self.assertIn("Pendientes dinámicos por presupuesto/stale/cooldown", app_js)
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
        self.assertIn("function buildUpdatedCacheReportFilters", app_js)
        self.assertIn("function setWarmCacheContinueStatus", app_js)
        self.assertIn("filters.warm_cache = true", app_js)
        self.assertIn("filters.warm_cache = false", app_js)
        self.assertIn("filters.no_cache = false", app_js)
        self.assertIn("Continuando warm-cache...", app_js)
        self.assertIn(
            "Continuando con la misma caché: revalidando otra tanda con --warm-cache, sin --no-cache.",
            app_js,
        )
        self.assertIn("Continuación warm-cache finalizada", app_js)
        self.assertIn("Actualizando el resumen visible desde el JSON local", app_js)
        self.assertIn("Continuación warm-cache finalizada y resumen actualizado", app_js)
        self.assertIn("No se pudo continuar warm-cache", app_js)
        self.assertIn("Continuando warm-cache con la caché actual (sin --no-cache).", app_js)
        self.assertIn("function syncLatestReportSummary", app_js)
        self.assertIn("return syncLatestReportCard(files)", app_js)
        self.assertIn("Generar reporte con caché actualizada", app_js)
        self.assertIn("Generando reporte normal con la caché actualizada (sin --warm-cache y sin --no-cache).", app_js)
        self.assertIn("renderLatestCacheCoverage(report)", app_js)
        self.assertIn("function normalizeRedactedPathMarkers", app_js)
        self.assertIn("replace(/(?:\\[ruta\\]){2,}/gi, '[ruta]')", app_js)
        self.assertIn(".latest-cache-coverage", app_css)
        self.assertIn(".latest-cache-coverage-copy", app_css)
        self.assertIn(".latest-cache-details", app_css)
        self.assertIn(".latest-cache-details-body", app_css)
        self.assertIn(".latest-cache-state-summary", app_css)
        self.assertIn(".latest-cache-block-progress", app_css)
        self.assertIn(".latest-cache-block-pills", app_css)
        self.assertIn(".latest-cache-final-states", app_css)
        self.assertIn(".latest-cache-final-pills", app_css)
        self.assertIn(".latest-cache-final-actions", app_css)
        self.assertIn(".latest-cache-final-actions-list", app_css)
        self.assertIn(".latest-cache-coverage-action-hint", app_css)
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
        self.assertIn("function startRunStatusHeartbeat", app_js)
        self.assertIn("function updateRunStatusHeartbeat", app_js)
        self.assertIn("function stopRunStatusHeartbeat", app_js)
        self.assertIn("function refreshLatestReportSummaryFromBanner", app_js)
        self.assertIn("function generateReportFromUpdatedCache", app_js)
        self.assertIn("data-warm-cache-refresh-summary", app_js)
        self.assertIn("data-warm-cache-generate-report", app_js)
        self.assertIn("preserveOutputFiles: true", app_js)
        self.assertIn("preserveLatestReportOnDone: true", app_js)
        self.assertIn("preserveOutputFiles: false", app_js)
        self.assertIn("preserveLatestReportOnDone: false", app_js)
        self.assertIn("updateWarmCacheBackgroundBannerFromEvent", app_js)
        self.assertIn("ev.type === 'done'", app_js)
        self.assertIn("Warm-cache finalizado", app_js)
        self.assertIn("preserveLatestReportOnDone === true && !hasFiles", app_js)
        self.assertIn("Puedes seguir revisando el último reporte", app_js)
        self.assertIn("se usa --warm-cache, sin --no-cache", app_js)
        self.assertIn("Resumen warm-cache actualizado", app_js)
        self.assertIn("Genera un reporte normal para que HTML/JSON usen la caché actualizada", app_js)
        self.assertIn("HTML/JSON se están regenerando con la caché disponible", app_js)
        self.assertIn("No está cacheando más juegos", app_js)
        self.assertIn("puede pasar varios segundos sin escribir nuevas líneas", app_js)
        self.assertIn("log sin novedades hace", app_js)
        self.assertIn("Reporte actualizado generado", app_js)
        self.assertIn("El HTML/JSON se regeneró con la caché actualizada", app_js)
        self.assertIn("Refrescar resumen", app_js)
        self.assertIn(".progress-container-indeterminate", app_css)
        self.assertIn("@keyframes steam-progress-indeterminate", app_css)
        self.assertIn(".warm-cache-background-banner", app_css)
        self.assertIn(".warm-cache-background-banner-progress", app_css)
        self.assertIn("@keyframes warm-cache-status-pulse", app_css)
        self.assertIn(".warm-cache-background-banner-ok", app_css)
        self.assertIn(".warm-cache-background-banner-warn", app_css)
        self.assertIn(".warm-cache-background-refresh", app_css)

    def test_latest_report_renders_selection_review_ui_as_standalone_tool(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("function renderLatestSelectionReviewPanel", app_js)
        self.assertIn("function renderLatestSelectionReviewTools", app_js)
        self.assertIn("buildLatestSelectionCandidates(report)", app_js)
        self.assertIn("data-latest-selection-review", app_js)
        self.assertIn("data-latest-selection-tools", app_js)
        self.assertIn("data-selection-candidate", app_js)
        self.assertIn("data-selection-input", app_js)
        self.assertIn("data-selection-evaluate", app_js)
        self.assertIn("localMutableFetch('/api/selection-review'", app_js)
        self.assertIn("function latestSelectionSignalLabel", app_js)
        self.assertIn("function latestSelectionConfidenceLabel", app_js)
        self.assertIn("function latestSelectionWhyItems", app_js)
        self.assertIn("function renderLatestSelectionWhyGroup", app_js)
        self.assertIn("latest-selection-result-signals", app_js)
        self.assertIn("Señales:", app_js)
        self.assertIn("latest-selection-result-confidence", app_js)
        self.assertIn("latest-selection-result-next-step", app_js)
        self.assertIn("latest-selection-result-why", app_js)
        self.assertIn("Confianza:", app_js)
        self.assertIn("Siguiente paso:", app_js)
        self.assertIn("A favor", app_js)
        self.assertIn("Cuidado", app_js)
        self.assertIn("Contexto", app_js)
        self.assertIn("source.next_step", app_js)
        self.assertIn("source.why", app_js)
        self.assertIn("Colección recomendada", app_js)
        self.assertIn("Duplicados omitidos", app_js)
        self.assertIn("source.price_final", app_js)
        self.assertIn("Evaluación local lista: ${total} juego(s).", app_js)
        self.assertIn("function latestSelectionCollectionItems", app_js)
        self.assertIn("recommended_collections", app_js)
        self.assertIn("'Top Picks'", app_js)
        self.assertIn("'Colección'", app_js)
        self.assertIn("'Oferta'", app_js)
        self.assertIn("report && report.deals", app_js)
        details_start = app_js.index("function renderLatestReportDetails")
        details_end = app_js.index("function latestCacheStateItems", details_start)
        details_block = app_js[details_start:details_end]
        self.assertNotIn("renderLatestSelectionReviewPanel(report)", details_block)
        self.assertIn("renderLatestSelectionReviewTools(report)", app_js)
        self.assertIn("bindLatestSelectionReviewActions()", app_js)
        self.assertIn("Evalúa mi selección", app_js)
        self.assertIn("Separado del resumen", app_js)
        self.assertIn("Herramientas de recomendaciones", app_js)
        self.assertIn("No abre carrito ni compra nada", app_js)
        self.assertIn("conservar", app_js)
        self.assertIn("dudar", app_js)
        self.assertIn("quitar", app_js)
        self.assertIn(".latest-selection-tools", app_css)
        self.assertIn(".latest-selection-tools-tabs", app_css)
        self.assertIn(".latest-selection-section", app_css)
        self.assertIn(".latest-selection-candidates", app_css)
        self.assertIn(".latest-selection-result-list", app_css)
        self.assertIn(".latest-selection-result-conservar", app_css)
        self.assertIn(".latest-selection-result-signals", app_css)
        self.assertIn(".latest-selection-result-confidence", app_css)
        self.assertIn(".latest-selection-result-next-step", app_css)
        self.assertIn(".latest-selection-result-why", app_css)

    def test_latest_budget_preview_normalizes_variant_rows_and_empty_state(self) -> None:
        app_js = (ROOT / "web" / "steam_deals" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("function budgetVariantRawRows", app_js)
        self.assertIn("Array.isArray(variant.selected) && variant.selected.length", app_js)
        self.assertIn("Array.isArray(variant.items) && variant.items.length", app_js)
        self.assertIn("function shouldUseRootBudgetRowsForVariant", app_js)
        self.assertIn("budgetVariantRowsForUi(budgetResult, variant).map", app_js)
        self.assertIn("Esta variante no trae filas de juegos", app_js)
        self.assertIn("latest-budget-empty", app_js)

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

    def test_wizard_finish_points_to_primary_next_actions(self) -> None:
        index_html = (ROOT / "web" / "steam_deals" / "index.html").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "steam_deals" / "app.css").read_text(
            encoding="utf-8"
        )

        wizard_start = index_html.index('id="wiz-step-3"')
        wizard_end = index_html.index('</div>\n</div>\n\n<div class="header">', wizard_start)
        wizard_markup = index_html[wizard_start:wizard_end]

        self.assertIn("Listo para volver a la pantalla principal", wizard_markup)
        self.assertIn("El asistente no inicia una corrida automática", wizard_markup)
        self.assertIn("Revisa filtros rápidos", wizard_markup)
        self.assertIn("Pulsa Generar reportes", wizard_markup)
        self.assertIn("Abre el último reporte si existe", wizard_markup)
        self.assertIn("Ver configuración que se guardará", wizard_markup)
        self.assertIn("Guardar y ver pantalla principal", wizard_markup)
        self.assertIn('class="wiz-summary-panel"', wizard_markup)
        self.assertIn('id="wiz-summary-vanity"', wizard_markup)
        self.assertIn(".wiz-next-actions", app_css)
        self.assertIn(".wiz-summary-panel", app_css)

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

    def test_payday2_bundle_undo_explains_manual_mark_scope(self) -> None:
        app_js = (ROOT / "web" / "payday2" / "app.js").read_text(
            encoding="utf-8"
        )
        app_css = (ROOT / "web" / "payday2" / "app.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("Solo desmarca DLCs de este bundle; conserva marcados manuales ajenos.", app_js)
        self.assertIn("Deshacer bundle", app_js)
        self.assertIn("aria-label=\"Deshacer bundle", app_js)
        self.assertIn("bcard-note", app_js)
        self.assertIn(".bcard .bcard-note", app_css)

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

    def test_recommendations_include_wait_deals_for_non_compelling_items(self) -> None:
        missing = [
            {
                "appid": "300",
                "steam_name": "PAYDAY 2: Legacy Pack",
                "price_raw": 8000,
                "price_fmt": "Mex$ 80.00",
                "orig_raw": 10000,
                "discount": 20,
            }
        ]

        rec = payday2_dlc_tracker.compute_recommendations(
            missing, budget=None, alert_price=None, min_deal=50
        )

        self.assertEqual([d["appid"] for d in rec["wait_deals"]], ["300"])
        self.assertEqual(rec["wait_deals"][0]["purchase_action"], "wait")
        self.assertIn("Descuento menor", rec["wait_deals"][0]["purchase_reasons"][0])

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
            },
            "100": {
                "appid": "100",
                "steam_name": "PAYDAY 2: Very Cheap Tailor Pack",
                "price_raw": 3900,
                "price_fmt": "Mex$ 39.00",
                "orig_raw": 39000,
                "orig_fmt": "",
                "discount": 90,
            },
            "300": {
                "appid": "300",
                "steam_name": "PAYDAY 2: Legacy Pack",
                "price_raw": 8000,
                "price_fmt": "Mex$ 80.00",
                "orig_raw": 10000,
                "orig_fmt": "",
                "discount": 20,
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
                        "pd2_dlc_appids": ["200", "100", "300"],
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
                            "catalog": {"count": 3, "ageHours": 2.0, "ttlHours": 168, "stale": False},
                            "names": {"count": 3, "ageHours": 2.0, "ttlHours": 168, "stale": False},
                            "prices": {"count": 3, "ageHours": 2.0, "ttlHours": 24, "stale": False},
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

        dlcs_by_id = {dlc["id"]: dlc for dlc in payload["dlcs"]}
        self.assertEqual(dlcs_by_id["200"]["importanceTier"], "S")
        self.assertGreater(dlcs_by_id["200"]["valueScore"], 0)
        self.assertIn("Heist", dlcs_by_id["200"]["valueReasons"][0])
        self.assertEqual(payload["buyNow"][0]["importanceTier"], "S")
        self.assertEqual(payload["buyNow"][0]["recommendationLabel"], "Comprar ahora")
        self.assertIn("Contenido jugable prioritario", payload["buyNow"][0]["recommendationReasons"])
        self.assertEqual(payload["reviewDeals"][0]["recommendationAction"], "review")
        self.assertEqual(payload["reviewDeals"][0]["recommendationLabel"], "Revisar si quieres completar")
        self.assertEqual(payload["waitDeals"][0]["recommendationAction"], "wait")
        self.assertIn("Descuento menor", payload["waitDeals"][0]["recommendationReasons"][0])
        self.assertEqual(payload["cacheStatus"]["catalog"]["count"], 3)

    def test_payday2_review_wait_advice_is_visible_and_advisory_only(self) -> None:
        app_js = (ROOT / "web" / "payday2" / "app.js").read_text(encoding="utf-8")
        app_css = (ROOT / "web" / "payday2" / "app.css").read_text(encoding="utf-8")

        self.assertIn("reviewDeals", app_js)
        self.assertIn("waitDeals", app_js)
        self.assertIn("Revisar antes de comprar", app_js)
        self.assertIn("Esperar mejor oferta", app_js)
        self.assertIn("Solo sugerencias", app_js)
        self.assertIn("no marca DLCs como comprados", app_js)
        self.assertIn(".rec-review", app_css)
        self.assertIn(".rec-note", app_css)

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
