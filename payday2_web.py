#!/usr/bin/env python3
"""
PAYDAY 2 DLC Dashboard — Web UI interactiva.

Abre un dashboard en el navegador con todo el estado de tus DLCs:
stats, ofertas, bundles, simulador de descuento, y puedes marcar
DLCs como comprados directamente desde la web.

Uso:
    python3 payday2_web.py              # http://127.0.0.1:8081
    python3 payday2_web.py --port 9090
"""

import argparse
import json
import signal
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import date, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from shared_web_infra import (
    build_missing_assets_html,
    load_html_with_fallback,
    load_text_asset,
    ProcessStreamUnavailable,
    read_json_body,
    send_html,
    send_json,
    send_text,
    start_text_subprocess,
    stop_process,
    stream_process_as_sse,
)

# Import tracker logic
import payday2_dlc_tracker as pd2

DEFAULT_PORT = 8081
WEB_DIR = Path(__file__).resolve().parent / "web" / "payday2"
PAYDAY2_HTML_FILE = WEB_DIR / "index.html"
PAYDAY2_CSS_FILE = WEB_DIR / "app.css"
PAYDAY2_JS_FILE = WEB_DIR / "app.js"
PAYDAY2_FAVICON_FILE = WEB_DIR / "favicon.svg"
PAYDAY2_MISSING_ASSETS_HTML = build_missing_assets_html(
    "PAYDAY 2 DLC Dashboard",
    "web/payday2/index.html + app.css + app.js",
)
PAYDAY2_MASK_ROUTES = {
    "/masks/heist_mask_blue.svg": WEB_DIR / "masks" / "heist_mask_blue.svg",
    "/masks/heist_mask_gold.svg": WEB_DIR / "masks" / "heist_mask_gold.svg",
    "/masks/heist_mask_red.svg": WEB_DIR / "masks" / "heist_mask_red.svg",
    "/masks/heist_mask_shadow.svg": WEB_DIR / "masks" / "heist_mask_shadow.svg",
}

# ─── In-memory data store ─────────────────────────

_store = {
    "loaded": False,
    "refreshing": False,
    "last_refresh": None,
    "vanity": "",
    "steam_id": None,
    "pd2_dlc_appids": [],
    "all_dlcs": {},
    "owned": set(),
    "prices": {},
    "sale_name": "",
    "recommendations": {},
    "bundles": [],
    "history_data": {},
    "comparison": {},
    "itad_lows": {},
}
_store_lock = threading.Lock()

# Running subprocess for refresh
_refresh_proc = None
_refresh_lock = threading.Lock()


def load_from_cache():
    """Load whatever data we have from disk cache for instant display."""
    cfg = pd2.load_user_config()
    vanity = cfg.get("vanity", "gaben")
    key = cfg.get("key")
    itad_key = cfg.get("itad_key")

    # Get Steam ID from owned cache (no network call)
    steam_id = None
    owned_cache, _ = pd2._load_cache(pd2.OWNED_CACHE)
    steam_id = owned_cache.get("steam_id")

    # DLC list from cache
    dlc_list_cache, _ = pd2._load_cache(pd2.DLC_LIST_CACHE)
    pd2_dlc_appids = [str(a) for a in dlc_list_cache.get("appids", [])]

    # Names from cache
    mapping_cache, _ = pd2._load_cache(pd2.DLC_MAPPING_CACHE)
    dlc_names = mapping_cache.get("names", {})

    # Owned from cache
    owned = set(str(a) for a in owned_cache.get("appids", [])) if steam_id else set()

    # Prices from cache
    prices_cache, _ = pd2._load_cache(pd2.PRICES_CACHE)
    prices = prices_cache.get("prices", {})

    # Build merged DLC data (no curated DB — just prices + names)
    all_dlcs = {}
    for appid in pd2_dlc_appids:
        d = {}
        if appid in prices:
            d.update(prices[appid])
        if appid in dlc_names:
            d["steam_name"] = pd2._strip_prefix(dlc_names[appid])
        d.setdefault("appid", appid)
        all_dlcs[appid] = d

    # Compute derived data
    missing_appids = [a for a in pd2_dlc_appids if a not in owned]
    missing_list = [all_dlcs[a] for a in missing_appids if a in all_dlcs]
    cfg = pd2.load_user_config()
    min_deal = cfg.get("payday2_min_deal", 50)
    recommendations = pd2.compute_recommendations(missing_list, None, None, min_deal)

    itad_lows = {}

    # Bundles from cache
    bundles_cache, _ = pd2._load_cache(pd2.BUNDLES_CACHE)
    bundles = bundles_cache.get("bundles", [])

    # Price history sparklines
    history = pd2.load_price_history()
    history_data = {}
    for snap in history.get("snapshots", [])[-30:]:
        for appid, sp in snap.get("prices", {}).items():
            if appid not in history_data:
                history_data[appid] = []
            history_data[appid].append(sp.get("price", 0))

    # Run comparison
    prev_run = pd2.load_previous_run()
    comparison = pd2.compute_run_comparison(prices, prev_run) if prev_run else {}

    # Last refresh time
    last_refresh = None
    if prices_cache.get("saved_at"):
        last_refresh = prices_cache["saved_at"]

    with _store_lock:
        _store.update(
            {
                "loaded": bool(pd2_dlc_appids),
                "last_refresh": last_refresh,
                "vanity": vanity,
                "steam_id": steam_id,
                "pd2_dlc_appids": pd2_dlc_appids,
                "all_dlcs": all_dlcs,
                "owned": owned,
                "prices": prices,
                "sale_name": "",
                "recommendations": recommendations,
                "history_data": history_data,
                "comparison": comparison,
                "itad_lows": itad_lows,
                "bundles": bundles,
            }
        )


def get_data_json() -> dict:
    """Build JSON payload for the frontend."""
    with _store_lock:
        s = _store
        pd2_dlc_appids = s["pd2_dlc_appids"]
        all_dlcs = s["all_dlcs"]
        owned = s["owned"]
        prices = s["prices"]
        itad_lows = s["itad_lows"]
        history_data = s["history_data"]
        recommendations = s["recommendations"]
        comparison = s["comparison"]

        total = len(pd2_dlc_appids)
        owned_count = sum(1 for a in pd2_dlc_appids if a in owned)
        missing = total - owned_count
        cost_orig = (
            sum(d.get("orig_raw", 0) for a, d in all_dlcs.items() if a not in owned)
            / 100
        )
        cost_curr = (
            sum(d.get("price_raw", 0) for a, d in all_dlcs.items() if a not in owned)
            / 100
        )
        on_sale = sum(
            1
            for a, d in all_dlcs.items()
            if a not in owned and d.get("discount", 0) > 0
        )

        # Build DLC list sorted by discount desc
        dlc_list = []
        for d in sorted(
            [d for a, d in all_dlcs.items() if a not in owned and d.get("steam_name")],
            key=lambda d: (-d.get("discount", 0), d.get("price_raw", 0)),
        ):
            appid = d.get("appid", "")
            low = itad_lows.get(appid)
            dlc_list.append(
                {
                    "id": appid,
                    "name": d.get("steam_name", "?"),
                    "price": d.get("price_raw", 0),
                    "orig": d.get("orig_raw", 0),
                    "priceFmt": d.get("price_fmt", "?"),
                    "origFmt": d.get("orig_fmt", "?"),
                    "discount": d.get("discount", 0),
                    "low": low["price"] if low else None,
                    "lowDate": low["date"] if low else None,
                }
            )

        # Owned DLC list
        owned_list = []
        for a in pd2_dlc_appids:
            if a in owned and a in all_dlcs:
                d = all_dlcs[a]
                owned_list.append(
                    {
                        "id": a,
                        "name": d.get("steam_name", a),
                    }
                )

        # Recommendation data
        rec = recommendations or {}
        buy_now = []
        for d in rec.get("buy_now", []):
            buy_now.append(
                {
                    "id": d.get("appid", ""),
                    "name": d.get("steam_name", "?"),
                    "discount": d.get("discount", 0),
                    "priceFmt": d.get("price_fmt", "?"),
                }
            )

        # Comparison
        comp = {}
        if comparison:
            comp = {
                "prevDate": comparison.get("prev_date", ""),
                "newSales": len(comparison.get("new_sales", [])),
                "endedSales": len(comparison.get("ended_sales", [])),
                "priceDrops": len(comparison.get("price_drops", [])),
            }

        return {
            "loaded": s["loaded"],
            "refreshing": s["refreshing"],
            "lastRefresh": s["last_refresh"],
            "vanity": s["vanity"],
            "totalDlcs": total,
            "ownedCount": owned_count,
            "missingCount": missing,
            "costOrig": round(cost_orig),
            "costCurr": round(cost_curr),
            "onSaleCount": on_sale,
            "estSummer75": round(cost_orig * 0.25),
            "saleName": s["sale_name"],
            "dlcs": dlc_list,
            "owned": owned_list,
            "history": history_data,
            "buyNow": buy_now,
            "onSaleSavings": round(rec.get("on_sale_savings", 0)),
            "comparison": comp,
            "upcomingSales": [
                {
                    "event": sl["event"],
                    "date": sl["date"],
                    "discount": sl["discount"],
                    "est": round(cost_orig * (1 - sl["discount"] / 100)),
                }
                for sl in pd2.UPCOMING_SALES
            ],
            "bundles": [
                {
                    "name": b["name"],
                    "id": b["bundle_id"],
                    "dlcAppids": b["dlc_appids"],
                    "count": len(b["dlc_appids"]),
                }
                for b in s.get("bundles", [])
            ],
        }


def toggle_owned(appid: str) -> dict:
    """Toggle a DLC as owned/unowned. Returns new state."""
    with _store_lock:
        owned = _store["owned"]
        if appid in owned:
            owned.discard(appid)
            now_owned = False
        else:
            owned.add(appid)
            now_owned = True
        _store["owned"] = owned

        # Recompute derived data
        missing_appids = [a for a in _store["pd2_dlc_appids"] if a not in owned]
        missing_list = [
            _store["all_dlcs"][a] for a in missing_appids if a in _store["all_dlcs"]
        ]
        cfg = pd2.load_user_config()
        min_deal = cfg.get("payday2_min_deal", 50)
        _store["recommendations"] = pd2.compute_recommendations(
            missing_list, None, None, min_deal
        )

        # Persist
        steam_id = _store["steam_id"]

    if steam_id:
        pd2.save_owned(steam_id, owned)

    return {"appid": appid, "owned": now_owned}


def mark_bundle_owned(bundle_id: str) -> dict:
    """Mark all DLCs in a bundle as owned. Returns list of marked appids."""
    with _store_lock:
        bundles = _store.get("bundles", [])
        bundle = next((b for b in bundles if b["bundle_id"] == bundle_id), None)
        if not bundle:
            return {"error": "Bundle not found", "marked": []}

        owned = _store["owned"]
        marked = []
        for appid in bundle["dlc_appids"]:
            if appid not in owned:
                owned.add(appid)
                marked.append(appid)
        _store["owned"] = owned

        # Recompute
        missing_appids = [a for a in _store["pd2_dlc_appids"] if a not in owned]
        missing_list = [
            _store["all_dlcs"][a] for a in missing_appids if a in _store["all_dlcs"]
        ]
        cfg = pd2.load_user_config()
        min_deal = cfg.get("payday2_min_deal", 50)
        _store["recommendations"] = pd2.compute_recommendations(
            missing_list, None, None, min_deal
        )

        steam_id = _store["steam_id"]

    if steam_id:
        pd2.save_owned(steam_id, owned)

    return {"bundle_id": bundle_id, "marked": marked, "total_marked": len(marked)}


def unmark_bundle_owned(bundle_id: str) -> dict:
    """Unmark all DLCs in a bundle. Returns list of unmarked appids."""
    with _store_lock:
        bundles = _store.get("bundles", [])
        bundle = next((b for b in bundles if b["bundle_id"] == bundle_id), None)
        if not bundle:
            return {"error": "Bundle not found", "unmarked": []}

        owned = _store["owned"]
        unmarked = []
        for appid in bundle["dlc_appids"]:
            if appid in owned:
                owned.discard(appid)
                unmarked.append(appid)
        _store["owned"] = owned

        # Recompute
        missing_appids = [a for a in _store["pd2_dlc_appids"] if a not in owned]
        missing_list = [
            _store["all_dlcs"][a] for a in missing_appids if a in _store["all_dlcs"]
        ]
        cfg = pd2.load_user_config()
        min_deal = cfg.get("payday2_min_deal", 50)
        _store["recommendations"] = pd2.compute_recommendations(
            missing_list, None, None, min_deal
        )

        steam_id = _store["steam_id"]

    if steam_id:
        pd2.save_owned(steam_id, owned)

    return {
        "bundle_id": bundle_id,
        "unmarked": unmarked,
        "total_unmarked": len(unmarked),
    }


def load_payday2_html() -> str:
    return load_html_with_fallback(
        PAYDAY2_HTML_FILE,
        [PAYDAY2_CSS_FILE, PAYDAY2_JS_FILE],
        PAYDAY2_MISSING_ASSETS_HTML,
    )


def load_payday2_asset(asset_file: Path) -> str | None:
    return load_text_asset(asset_file)


def load_payday2_mask(route_path: str) -> str | None:
    asset_file = PAYDAY2_MASK_ROUTES.get(route_path)
    if asset_file is None:
        return None
    return load_payday2_asset(asset_file)


# ─── HTTP Handler ─────────────────────────────────


class Handler(BaseHTTPRequestHandler):
    max_json_body_bytes = 64 * 1024

    def log_message(self, format, *args):
        pass

    def _json(self, data, status=200):
        send_json(self, data, status=status)

    def _html(self, html):
        send_html(self, html)

    def _css(self, css: str):
        send_text(self, css, "text/css; charset=utf-8")

    def _js(self, script: str):
        send_text(self, script, "application/javascript; charset=utf-8")

    def _svg(self, svg: str):
        send_text(self, svg, "image/svg+xml; charset=utf-8")

    def _body(self) -> dict | None:
        return read_json_body(self, max_json_body_bytes=self.max_json_body_bytes)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._html(load_payday2_html())
        elif path == "/app.css":
            css = load_payday2_asset(PAYDAY2_CSS_FILE)
            if css is None:
                self.send_error(404)
                return
            self._css(css)
        elif path == "/app.js":
            script = load_payday2_asset(PAYDAY2_JS_FILE)
            if script is None:
                self.send_error(404)
                return
            self._js(script)
        elif path == "/favicon.svg":
            svg = load_payday2_asset(PAYDAY2_FAVICON_FILE)
            if svg is None:
                self.send_error(404)
                return
            self._svg(svg)
        elif path in PAYDAY2_MASK_ROUTES:
            svg = load_payday2_mask(path)
            if svg is None:
                self.send_error(404)
                return
            self._svg(svg)
        elif path == "/api/data":
            self._json(get_data_json())
        elif path == "/api/config":
            self._json(pd2.load_user_config())
        else:
            self.send_error(404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/toggle":
            body = self._body()
            if body is None:
                return
            appid = str(body.get("appid", "")).strip()
            if not appid:
                self._json({"error": "appid required"}, 400)
                return
            result = toggle_owned(appid)
            self._json(result)
        elif path == "/api/toggle-bundle":
            body = self._body()
            if body is None:
                return
            bundle_id = str(body.get("bundle_id", "")).strip()
            action = str(body.get("action", "mark")).strip().lower() or "mark"
            if not bundle_id:
                self._json({"error": "bundle_id required"}, 400)
                return
            if action not in ("mark", "unmark"):
                self._json(
                    {
                        "error": "invalid_action",
                        "message": "action debe ser 'mark' o 'unmark'.",
                    },
                    400,
                )
                return
            if action == "unmark":
                result = unmark_bundle_owned(bundle_id)
            else:
                result = mark_bundle_owned(bundle_id)
            self._json(result)
        elif path == "/api/refresh":
            self._serve_refresh()
        elif path == "/api/config":
            body = self._body()
            if body is None:
                return
            cfg = pd2.load_user_config()
            cfg.update(body)
            pd2.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            pd2.CONFIG_FILE.write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._json({"status": "saved"})
        else:
            self.send_error(404)

    def _serve_refresh(self):
        """Run the tracker script and stream progress via SSE."""
        global _refresh_proc

        def clear_refresh_proc() -> None:
            global _refresh_proc
            with _refresh_lock:
                _refresh_proc = None

        def finish_refresh() -> None:
            clear_refresh_proc()
            with _store_lock:
                _store["refreshing"] = False

        with _refresh_lock:
            if _refresh_proc and _refresh_proc.poll() is None:
                self._json({"error": "Already refreshing"}, 409)
                return

        with _store_lock:
            _store["refreshing"] = True

        cfg = pd2.load_user_config()
        cmd = [
            sys.executable,
            str(Path(__file__).resolve().parent / "payday2_dlc_tracker.py"),
        ]
        if cfg.get("vanity"):
            cmd += ["--vanity", cfg["vanity"]]
        if cfg.get("key"):
            cmd += ["--key", cfg["key"]]
        if cfg.get("itad_key"):
            cmd += ["--itad-key", cfg["itad_key"]]

        try:
            proc = start_text_subprocess(cmd)
        except Exception as exc:
            finish_refresh()
            self._json({"error": f"No se pudo iniciar proceso: {exc}"}, 500)
            return

        with _refresh_lock:
            _refresh_proc = proc

        import re

        ansi_re = re.compile(r"\033\[[0-9;]*m")
        step_re = re.compile(r"\[(\d+)/(\d+)\]\s*(.*)")

        def handle_process_line(raw_line: str, emit_sse):
            text = ansi_re.sub("", raw_line).rstrip()
            if not text:
                return

            cls = "normal"
            if "\u2713" in raw_line or "\u2713" in text:
                cls = "ok"
            elif "\u26a0" in raw_line or "\u26a0" in text:
                cls = "warn"
            elif "\u2717" in raw_line or "\u2717" in text:
                cls = "err"
            elif "\u2500" in text or "===" in text:
                cls = "bold"

            m = step_re.search(text)
            if m:
                emit_sse(
                    {
                        "type": "progress",
                        "current": int(m.group(1)),
                        "total": int(m.group(2)),
                        "label": m.group(3).strip(),
                    }
                )
                cls = "step"

            emit_sse({"type": "line", "text": text, "cls": cls})

        def handle_process_done(done_proc, emit_sse):
            finish_refresh()
            load_from_cache()
            emit_sse({"type": "done", "exit_code": done_proc.returncode})

        try:
            stream_process_as_sse(self, proc, handle_process_line, handle_process_done)
        except ProcessStreamUnavailable:
            finish_refresh()
            self._json({"error": "No se pudo leer salida del proceso"}, 500)
        finally:
            finish_refresh()


# ─── Main ─────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="PAYDAY 2 DLC Dashboard")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Puerto HTTP")
    parser.add_argument("--no-open", action="store_true", help="No abrir navegador")
    args = parser.parse_args()

    # Load cached data for instant display
    print("Cargando datos del cache...", flush=True)
    try:
        load_from_cache()
        with _store_lock:
            loaded = _store["loaded"]
        if loaded:
            n = len(_store["pd2_dlc_appids"])
            owned = sum(1 for a in _store["pd2_dlc_appids"] if a in _store["owned"])
            print(f"  {n} DLCs cargados, {owned} poseidos")
        else:
            print("  Sin datos en cache — usa el boton 'Actualizar' en la web")
    except Exception as e:
        print(f"  Cache no disponible: {e}")

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"\n  Dashboard: {url}\n")

    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    # Graceful shutdown
    shutdown_started = threading.Event()

    def stop_active_refresh():
        with _refresh_lock:
            if _refresh_proc and _refresh_proc.poll() is None:
                stop_process(_refresh_proc)

    def request_shutdown():
        if shutdown_started.is_set():
            return
        shutdown_started.set()
        print("\nCerrando...")
        stop_active_refresh()
        threading.Thread(target=server.shutdown, daemon=True).start()

    def shutdown(sig, frame):
        request_shutdown()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        request_shutdown()
    finally:
        stop_active_refresh()
        server.server_close()


if __name__ == "__main__":
    main()
