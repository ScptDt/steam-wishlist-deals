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
        PAGE_HTML,
    )


def load_payday2_asset(asset_file: Path) -> str | None:
    return load_text_asset(asset_file)


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


# ─── HTML Page ────────────────────────────────────

PAGE_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PAYDAY 2 DLC Dashboard</title>
<style>
:root {
  --bg: #1b2838; --bg2: #2a475e; --card: #16202d; --border: #2a475e;
  --text: #c7d5e0; --text2: #8f98a0; --accent: #66c0f4; --accent2: #4b9cd3;
  --green: #6cc644; --yellow: #f0b232; --red: #c7322e; --gold: #d4a84b;
  --console-bg: #0e1a26;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }
a { color: var(--accent); text-decoration: none; } a:hover { text-decoration: underline; }

/* Header */
.hdr {
  background: linear-gradient(135deg, #0e1a26 0%, #1b2838 40%, #1a2636 100%);
  border-bottom: 2px solid var(--gold); padding: 1.2rem 1rem; text-align: center;
  position: sticky; top: 0; z-index: 100; backdrop-filter: blur(8px);
}
.hdr-inner { max-width: 1200px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.hdr h1 { font-size: 1.4rem; color: var(--gold); letter-spacing: .02em; display: flex; align-items: center; gap: .5rem; }
.hdr h1 .mask-icon { font-size: 1.6rem; }
.hdr-info { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.hdr-vanity { color: var(--accent); font-size: .85rem; font-weight: 500; }
.hdr-refresh-time { color: var(--text2); font-size: .72rem; }
.btn-refresh {
  background: linear-gradient(135deg, var(--gold), #b8922e); color: #1b2838;
  border: none; border-radius: 6px; padding: .5rem 1.2rem; font-weight: 700;
  font-size: .85rem; cursor: pointer; transition: all .2s; display: flex; align-items: center; gap: .4rem;
}
.btn-refresh:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(212,168,75,.3); }
.btn-refresh:disabled { opacity: .5; cursor: not-allowed; transform: none; box-shadow: none; }
.btn-refresh .spinner { display: none; width: 14px; height: 14px; border: 2px solid rgba(27,40,56,.3); border-top-color: #1b2838; border-radius: 50%; animation: spin .6s linear infinite; }
.btn-refresh.loading .spinner { display: inline-block; }
.btn-refresh.loading .refresh-icon { display: none; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Container */
.container { max-width: 1200px; margin: 0 auto; padding: 1rem; }

/* Empty state */
.empty-state {
  text-align: center; padding: 4rem 1rem; color: var(--text2);
}
.empty-state h2 { font-size: 1.4rem; color: var(--accent); margin-bottom: .5rem; }
.empty-state p { font-size: .9rem; margin-bottom: 1.5rem; max-width: 500px; margin-left: auto; margin-right: auto; }
.empty-state .btn-refresh { display: inline-flex; font-size: 1rem; padding: .7rem 2rem; }

/* Stats grid */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: .6rem; margin-bottom: 1rem; }
.st { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: .7rem; text-align: center; transition: border-color .2s; }
.st:hover { border-color: var(--accent); }
.st .v { font-size: 1.4rem; font-weight: 700; color: var(--accent); }
.st .l { font-size: .7rem; color: var(--text2); margin-top: .1rem; }
.st.g .v { color: var(--green); } .st.y .v { color: var(--yellow); } .st.r .v { color: var(--red); } .st.gold .v { color: var(--gold); }

/* Donut */
.overview-row { display: grid; grid-template-columns: auto 1fr; gap: 1.5rem; align-items: center; margin-bottom: 1rem; }
.donut-wrap { display: flex; flex-direction: column; align-items: center; gap: .5rem; }
.donut-svg { width: 150px; height: 150px; }
.donut-center { font-size: 1.4rem; font-weight: 700; fill: var(--text); }
.donut-label { font-size: .65rem; fill: var(--text2); }
.donut-ring { fill: none; stroke: var(--bg2); stroke-width: 18; }
.donut-fill { fill: none; stroke-width: 18; stroke-linecap: round; transition: stroke-dashoffset .8s ease; }
.legend { display: grid; grid-template-columns: 1fr 1fr; gap: .3rem .8rem; font-size: .82rem; }
.legend-item { display: flex; align-items: center; gap: .4rem; color: var(--text2); }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }

/* Cards */
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1.2rem; margin-bottom: 1rem; }
.card h2 { font-size: .95rem; color: var(--accent); margin-bottom: .8rem; font-weight: 600; display: flex; align-items: center; gap: .4rem; }
.card h2 .badge { font-size: .7rem; background: var(--bg2); color: var(--text2); padding: .1rem .5rem; border-radius: 10px; font-weight: 500; }

/* Banners */
.sale-banner { background: var(--gold); color: #1b2838; padding: .6rem 1rem; border-radius: 8px; font-weight: 600; text-align: center; margin-bottom: .75rem; font-size: .9rem; }
.rec-buy { background: rgba(108,198,68,.1); border: 1px solid rgba(108,198,68,.3); padding: .7rem 1rem; border-radius: 8px; margin-bottom: .75rem; font-size: .85rem; }
.rec-buy a { background: rgba(108,198,68,.15); padding: .15rem .5rem; border-radius: 4px; margin: 0 .2rem; white-space: nowrap; }
.rec-wait { background: rgba(240,178,50,.07); border: 1px solid rgba(240,178,50,.25); color: var(--yellow); padding: .7rem 1rem; border-radius: 8px; margin-bottom: .75rem; font-size: .85rem; }
.comp-row { font-size: .78rem; color: var(--text2); margin-bottom: .6rem; text-align: center; }
.comp-badge { display: inline-block; padding: .1rem .4rem; border-radius: 3px; font-size: .7rem; font-weight: 600; }
.comp-green { background: rgba(108,198,68,.2); color: var(--green); }
.comp-red { background: rgba(199,50,46,.2); color: var(--red); }
.comp-blue { background: rgba(102,192,244,.2); color: var(--accent); }

/* Tabs */
.tabs { display: flex; gap: 0; margin-bottom: 1rem; }
.tab { flex: 1; padding: .6rem; border: 1px solid var(--border); background: var(--card); color: var(--text2);
  font-weight: 600; font-size: .85rem; cursor: pointer; transition: all .2s; text-align: center; }
.tab:first-child { border-radius: 8px 0 0 8px; }
.tab:last-child { border-radius: 0 8px 8px 0; }
.tab:not(:first-child) { border-left: none; }
.tab.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.tab-panel { display: none; } .tab-panel.active { display: block; }

/* Simulator */
.sim-row { display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; }
.sim-row input[type=range] { flex: 1; min-width: 180px; accent-color: var(--gold); height: 6px; }
.sim-pct { font-size: 1.3rem; font-weight: 700; color: var(--gold); min-width: 3.5rem; text-align: center; }
.sim-results { display: flex; gap: 1.5rem; margin-top: .5rem; font-size: .88rem; flex-wrap: wrap; }
.sim-results .val { color: var(--green); font-weight: 700; }

/* Budget planner */
.budget-row { display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; margin-bottom: .75rem; }
.budget-row input[type=number] {
  background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: .45rem .7rem;
  border-radius: 6px; font-size: .9rem; width: 140px; outline: none;
}
.budget-row input:focus { border-color: var(--accent); }
.budget-btn {
  background: var(--accent); color: #fff; border: none; border-radius: 6px; padding: .45rem 1rem;
  font-weight: 600; font-size: .85rem; cursor: pointer; transition: all .2s;
}
.budget-btn:hover { background: var(--accent2); }
.budget-result { font-size: .85rem; color: var(--text2); }
.budget-result .val { color: var(--green); font-weight: 600; }
.budget-list { margin-top: .5rem; }
.budget-item { display: flex; align-items: center; gap: .5rem; padding: .3rem 0; border-bottom: 1px solid rgba(42,71,94,.3); font-size: .82rem; }
.budget-item:last-child { border: none; }
.budget-item .bi-tier { font-weight: 700; width: 22px; text-align: center; }
.budget-item .bi-price { margin-left: auto; color: var(--text2); white-space: nowrap; }

/* Bundle cards */
.bundles-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: .75rem; }
.bcard { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; transition: border-color .2s; }
.bcard:hover { border-color: var(--accent); }
.bcard-head { padding: .6rem .8rem; display: flex; justify-content: space-between; align-items: center; background: rgba(212,168,75,.06); }
.bcard-name { font-weight: 600; font-size: .85rem; }
.bcard-cost { color: var(--gold); font-weight: 700; font-size: .9rem; }
.bcard-phase { font-size: .68rem; color: var(--text2); }
.bcard-dlcs { padding: .4rem .8rem .6rem; }
.bcard-dlc { display: flex; align-items: center; gap: .5rem; padding: .2rem 0; font-size: .78rem; border-bottom: 1px solid rgba(42,71,94,.25); }
.bcard-dlc:last-child { border: none; }
.bcard-dlc img { width: 70px; height: 26px; border-radius: 3px; object-fit: cover; flex-shrink: 0; }
.bcard-dlc .bd-price { margin-left: auto; color: var(--text2); font-size: .72rem; white-space: nowrap; }

/* DLC Table */
.filters { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: .6rem; align-items: center; }
.filters select, .filters input[type=text] {
  background: var(--bg); border: 1px solid var(--border); color: var(--text);
  padding: .35rem .5rem; border-radius: 4px; font-size: .78rem;
}
.filters select:focus, .filters input:focus { border-color: var(--accent); outline: none; }
.filters .fcount { font-size: .72rem; color: var(--text2); margin-left: auto; }
.tbl-wrap { overflow-x: auto; max-height: 70vh; overflow-y: auto; }
table { width: 100%; border-collapse: collapse; font-size: .8rem; }
th {
  background: var(--bg2); color: var(--text2); text-align: left; padding: .5rem .45rem;
  font-weight: 600; position: sticky; top: 0; cursor: pointer; white-space: nowrap; user-select: none; z-index: 2;
}
th:hover { color: var(--accent); }
th .sort-arrow { font-size: .6rem; margin-left: .2rem; }
td { padding: .4rem .45rem; border-bottom: 1px solid rgba(42,71,94,.35); vertical-align: middle; }
tr:hover { background: rgba(102,192,244,.04); }
tr.owned-row { opacity: .35; }
tr.owned-row td { text-decoration: line-through; }
.tier-badge { font-weight: 700; text-align: center; display: inline-block; width: 24px; }
.tier-S { color: var(--gold); } .tier-A { color: var(--green); } .tier-B { color: var(--accent); } .tier-C { color: var(--text2); }
.dlc-cell { display: flex; align-items: center; gap: .5rem; }
.dlc-cell img { width: 88px; height: 33px; border-radius: 3px; object-fit: cover; flex-shrink: 0; transition: transform .25s; }
.dlc-cell img:hover { transform: scale(2.8); position: relative; z-index: 10; box-shadow: 0 4px 20px rgba(0,0,0,.7); }
.dlc-info .dlc-name { font-weight: 500; }
.dlc-info .dlc-notes { font-size: .66rem; color: var(--text2); max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dlc-info .dlc-notes:hover { white-space: normal; }
.sale-tag { color: var(--green); font-weight: 700; }
.chk { width: 16px; height: 16px; accent-color: var(--green); cursor: pointer; }
.sparkline { width: 70px; height: 22px; } .sparkline polyline { fill: none; stroke: var(--accent); stroke-width: 1.5; }

/* Owned panel */
.owned-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: .4rem; }
.owned-item { display: flex; align-items: center; gap: .4rem; padding: .3rem .5rem; background: var(--bg); border-radius: 4px; font-size: .78rem; }
.owned-item img { width: 50px; height: 19px; border-radius: 2px; object-fit: cover; }
.owned-item .remove-btn { margin-left: auto; color: var(--red); cursor: pointer; background: none; border: none; font-size: .9rem; padding: 0 .2rem; }
.owned-item .remove-btn:hover { color: #ff5555; }

/* Upcoming sales */
.sales-table { width: 100%; font-size: .82rem; }
.sales-table td { padding: .4rem .5rem; }
.sales-table .est { color: var(--green); font-weight: 600; }

/* Refresh console */
.refresh-panel { display: none; margin-bottom: 1rem; }
.refresh-panel.visible { display: block; }
.progress-wrap { background: var(--bg); border-radius: 4px; height: 26px; position: relative; overflow: hidden; margin-bottom: .5rem; }
.progress-bar { height: 100%; background: linear-gradient(90deg, var(--gold), #b8922e); border-radius: 4px; transition: width .4s ease; width: 0%; }
.progress-text { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: .75rem; font-weight: 600; color: var(--text); text-shadow: 0 1px 2px rgba(0,0,0,.5); }
.console {
  background: var(--console-bg); border: 1px solid var(--border); border-radius: 6px;
  padding: .6rem; font-family: 'Consolas','Monaco','Courier New',monospace;
  font-size: .75rem; line-height: 1.5; max-height: 200px; overflow-y: auto;
}
.console .line { white-space: pre-wrap; word-break: break-all; }
.console .line-ok { color: var(--green); } .console .line-warn { color: var(--yellow); }
.console .line-err { color: var(--red); } .console .line-step { color: var(--accent); font-weight: 600; }
.console .line-bold { color: var(--text); font-weight: 700; }

/* Settings card */
.settings-row { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; margin-bottom: .75rem; }
.settings-field label { display: block; font-size: .78rem; color: var(--text2); margin-bottom: .2rem; font-weight: 500; }
.settings-field input {
  width: 100%; background: var(--bg); border: 1px solid var(--border); color: var(--text);
  padding: .4rem .6rem; border-radius: 6px; font-size: .85rem; outline: none;
}
.settings-field input:focus { border-color: var(--accent); }
.settings-save {
  background: var(--accent); color: #fff; border: none; border-radius: 6px; padding: .4rem 1rem;
  font-weight: 600; font-size: .82rem; cursor: pointer;
}
.settings-save:hover { background: var(--accent2); }
.pw-wrap { position: relative; }
.pw-wrap input { padding-right: 2.2rem; }
.pw-toggle { position: absolute; right: .4rem; top: 50%; transform: translateY(-50%); background: none; border: none; color: var(--text2); cursor: pointer; font-size: 1rem; }

/* Footer */
.footer { text-align: center; color: var(--text2); font-size: .7rem; padding: 2rem 0 1rem; }
.bcard { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: .8rem; display: flex; align-items: center; gap: .8rem; transition: border-color .2s; }
.bcard:hover { border-color: var(--accent); }
.bcard .bcard-info { flex: 1; }
.bcard .bcard-name { font-weight: 600; font-size: .9rem; }
.bcard .bcard-meta { font-size: .72rem; color: var(--text2); margin-top: .15rem; }
.bcard .bcard-btn { background: var(--accent); color: #1b2838; border: none; padding: .4rem .8rem; border-radius: 4px; font-weight: 600; font-size: .8rem; cursor: pointer; white-space: nowrap; }
.bcard .bcard-btn:hover { opacity: .85; }
.bcard .bcard-btn.done { background: var(--green); cursor: default; }

/* Responsive */
@media (max-width: 700px) {
  .hdr-inner { flex-direction: column; text-align: center; }
  .stats { grid-template-columns: repeat(3, 1fr); }
  .overview-row { grid-template-columns: 1fr; justify-items: center; }
  .legend { justify-content: center; }
  .bundles-grid { grid-template-columns: 1fr; }
  .settings-row { grid-template-columns: 1fr; }
  .dlc-cell img { width: 60px; height: 22px; }
}
</style>
</head>
<body>

<!-- Header -->
<div class="hdr">
  <div class="hdr-inner">
    <h1><span class="mask-icon">&#127917;</span> PAYDAY 2 DLC Dashboard</h1>
    <div class="hdr-info">
      <span class="hdr-vanity" id="hdr-vanity"></span>
      <span class="hdr-refresh-time" id="hdr-time"></span>
      <button class="btn-refresh" id="btn-refresh" onclick="doRefresh()">
        <span class="refresh-icon">&#8635;</span>
        <span class="spinner"></span>
        Actualizar datos
      </button>
    </div>
  </div>
</div>

<div class="container">
  <!-- Empty state (shown when no data) -->
  <div class="empty-state" id="empty-state" style="display:none">
    <h2>&#127917; Bienvenido al Dashboard de PAYDAY 2</h2>
    <p>No hay datos en cache. Configura tu perfil de Steam y haz click en actualizar para cargar tus DLCs.</p>
    <div class="card" style="max-width:500px;margin:0 auto 1.5rem;text-align:left">
      <h2>&#9881; Configuracion rapida</h2>
      <div class="settings-field" style="margin-bottom:.75rem">
        <label>Perfil de Steam (Vanity URL o Steam ID)</label>
        <input type="text" id="setup-vanity" placeholder="tu_vanity_url">
      </div>
      <div class="settings-field" style="margin-bottom:.75rem">
        <label>Steam API Key <span style="color:var(--text2);font-size:.75rem">(opcional — no detecta DLCs, solo juegos)</span></label>
        <input type="text" id="setup-key" placeholder="Tu Steam API Key (opcional)">
        <div style="font-size:.72rem;color:var(--text2);margin-top:.3rem">Nota: la API de Steam no permite detectar DLCs poseidos. Usa los checkboxes en la tabla para marcarlos manualmente.</div>
      </div>
      <button class="btn-refresh" onclick="quickSetup()" style="width:100%;justify-content:center">
        <span class="refresh-icon">&#128640;</span> Configurar y cargar datos
      </button>
    </div>
  </div>

  <!-- Main dashboard (shown when data loaded) -->
  <div id="dashboard" style="display:none">

    <!-- Refresh console (hidden until refresh) -->
    <div class="refresh-panel" id="refresh-panel">
      <div class="progress-wrap">
        <div class="progress-bar" id="prog-bar"></div>
        <div class="progress-text" id="prog-text">Actualizando...</div>
      </div>
      <div class="console" id="console"></div>
    </div>

    <!-- Banners -->
    <div id="banners"></div>

    <!-- Stats -->
    <div class="stats" id="stats-grid"></div>

    <!-- Overview: donut + legend -->
    <div class="card">
      <div class="overview-row">
        <div class="donut-wrap">
          <svg class="donut-svg" viewBox="0 0 180 180" id="donut">
            <circle class="donut-ring" cx="90" cy="90" r="70"/>
            <circle class="donut-fill" id="donut-fill" cx="90" cy="90" r="70" stroke="var(--accent)" stroke-dasharray="440" stroke-dashoffset="440" transform="rotate(-90 90 90)"/>
            <text class="donut-center" id="donut-pct" x="90" y="86" text-anchor="middle">0%</text>
            <text class="donut-label" id="donut-lbl" x="90" y="105" text-anchor="middle">0/0 DLCs</text>
          </svg>
        </div>
        <div>
          <div class="legend" id="legend"></div>
          <div style="margin-top:.8rem" id="upcoming-sales"></div>
        </div>
      </div>
    </div>

    <!-- Main tabs -->
    <div class="tabs">
      <div class="tab active" onclick="switchTab('dlcs')">&#128203; DLCs Faltantes</div>
      <div class="tab" onclick="switchTab('tools')">&#128295; Herramientas</div>
      <div class="tab" onclick="switchTab('owned')">&#9989; Comprados</div>
      <div class="tab" onclick="switchTab('settings')">&#9881; Config</div>
    </div>

    <!-- Tab: DLCs -->
    <div class="tab-panel active" id="panel-dlcs">
      <div class="card">
        <div class="filters">
          <select id="f-sale" onchange="renderTable()"><option value="">Oferta</option><option value="y">En oferta</option><option value="n">Precio normal</option></select>
          <input type="text" id="f-q" placeholder="&#128269; Buscar DLC..." oninput="renderTable()" style="min-width:140px">
          <span class="fcount" id="f-count"></span>
        </div>
        <div class="tbl-wrap">
          <table>
            <thead><tr>
              <th style="width:28px" title="Marcar como comprado">&#9745;</th>
              <th onclick="doSort('name')">DLC <span class="sort-arrow" id="sa-name"></span></th>
              <th onclick="doSort('price')">Precio <span class="sort-arrow" id="sa-price"></span></th>
              <th onclick="doSort('discount')">Oferta <span class="sort-arrow" id="sa-discount"></span></th>
              <th>Hist.</th>
            </tr></thead>
            <tbody id="tbody"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Bundles section (mark entire bundle as owned) -->
    <div class="card" id="bundles-card" style="display:none">
      <h2>&#128230; Tienes un bundle? Marca todos sus DLCs de una vez</h2>
      <div id="bundles-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.6rem"></div>
    </div>

    <!-- Tab: Tools -->
    <div class="tab-panel" id="panel-tools">
      <!-- Discount Simulator -->
      <div class="card">
        <h2>&#128270; Simulador de Descuento</h2>
        <p style="font-size:.82rem;color:var(--text2);margin-bottom:.8rem">Desliza para ver cuanto costarian tus DLCs faltantes con un descuento global</p>
        <div class="sim-row">
          <span style="color:var(--text2);font-size:.8rem">0%</span>
          <input type="range" id="sim-slider" min="0" max="90" step="5" value="0" oninput="simulate()">
          <span class="sim-pct" id="sim-pct">0%</span>
          <span style="color:var(--text2);font-size:.8rem">90%</span>
        </div>
        <div class="sim-results">
          <div>Costo simulado: <span class="val" id="sim-cost">--</span></div>
          <div>Ahorro: <span class="val" id="sim-save">--</span></div>
          <div>Por DLC: <span class="val" id="sim-avg">--</span></div>
        </div>
      </div>

      <!-- Budget Planner -->
      <div class="card">
        <h2>&#128176; Budget Planner</h2>
        <p style="font-size:.82rem;color:var(--text2);margin-bottom:.8rem">Cuantos DLCs puedes comprar con tu presupuesto (priorizando por mejor oferta)</p>
        <div class="budget-row">
          <span style="font-size:.85rem">Mex$</span>
          <input type="number" id="budget-input" min="0" step="50" placeholder="500" value="500">
          <button class="budget-btn" onclick="calcBudget()">Calcular</button>
        </div>
        <div id="budget-result"></div>
      </div>

      <!-- Upcoming sales -->
      <div class="card">
        <h2>&#128197; Proximas Ofertas Estimadas</h2>
        <table class="sales-table" id="sales-table"></table>
      </div>
    </div>

    <!-- Tab: Owned -->
    <div class="tab-panel" id="panel-owned">
      <div class="card">
        <h2>&#9989; DLCs Comprados <span class="badge" id="owned-count-badge">0</span></h2>
        <p style="font-size:.82rem;color:var(--text2);margin-bottom:.8rem">DLCs marcados como tuyos. Click en &#10005; para desmarcar.</p>
        <div class="owned-grid" id="owned-grid"></div>
      </div>
    </div>

    <!-- Tab: Settings -->
    <div class="tab-panel" id="panel-settings">
      <div class="card">
        <h2>&#9881; Configuracion</h2>
        <div class="settings-row">
          <div class="settings-field">
            <label>Perfil de Steam</label>
            <input type="text" id="cfg-vanity" placeholder="tu_vanity_url">
          </div>
          <div class="settings-field">
            <label>Steam API Key <span style="color:var(--text2);font-size:.75rem">(opcional — no detecta DLCs, solo juegos)</span></label>
            <div class="pw-wrap">
              <input type="password" id="cfg-key" placeholder="Tu Steam API Key">
              <button class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
            </div>
            <div style="font-size:.72rem;color:var(--text2);margin-top:.3rem">Obtenla en <a href="https://steamcommunity.com/dev/apikey" target="_blank">steamcommunity.com/dev/apikey</a></div>
          </div>
        </div>
        <div class="settings-row">
          <div class="settings-field">
            <label>ITAD API Key (opcional)</label>
            <div class="pw-wrap">
              <input type="password" id="cfg-itad" placeholder="IsThereAnyDeal Key">
              <button class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
            </div>
          </div>
          <div class="settings-field">
            <label>&nbsp;</label>
            <button class="settings-save" onclick="saveConfig()">&#128190; Guardar configuracion</button>
          </div>
        </div>
        <div id="cfg-status" style="font-size:.8rem;color:var(--green);margin-top:.3rem"></div>
      </div>
    </div>

  </div><!-- /dashboard -->
</div>

<div class="footer">PAYDAY 2 DLC Dashboard &middot; <span id="footer-date"></span></div>

<script>
/* ──── Globals ─���── */
let DATA = null;
let sortKey = 'discount', sortAsc = false;
const STORE = 'https://store.steampowered.com/app/';
const CAP = 'https://cdn.akamai.steamstatic.com/steam/apps/';
/* No curated DB — no tier/bundle/phase constants */

function $(id) { return document.getElementById(id); }
function esc(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function fmt(n) { return n.toLocaleString('en', {maximumFractionDigits:0}); }
function togglePw(btn) { const i=btn.previousElementSibling; i.type=i.type==='password'?'text':'password'; }

/* ──── Load data ──── */
async function loadData() {
  try {
    const r = await fetch('/api/data');
    DATA = await r.json();
    if (DATA.loaded && DATA.totalDlcs > 0) {
      $('empty-state').style.display = 'none';
      $('dashboard').style.display = 'block';
      renderAll();
    } else if (DATA.loaded) {
      // Data loaded but no DLCs found — show dashboard anyway
      $('empty-state').style.display = 'none';
      $('dashboard').style.display = 'block';
      renderAll();
    } else {
      $('empty-state').style.display = 'block';
      $('dashboard').style.display = 'none';
    }
  } catch(e) {}
  // Load config into settings
  try {
    const r = await fetch('/api/config');
    const cfg = await r.json();
    if (cfg.vanity) $('cfg-vanity').value = cfg.vanity;
    if (cfg.key) $('cfg-key').value = cfg.key;
    if (cfg.itad_key) $('cfg-itad').value = cfg.itad_key;
  } catch(e) {}
}

/* ──── Render everything ──── */
function renderAll() {
  if (!DATA) return;
  renderHeader();
  renderBanners();
  renderStats();
  renderDonut();
  renderLegend();
  renderTable();
  renderBundles();
  renderOwned();
  renderSales();
  simulate();
  $('footer-date').textContent = new Date().toLocaleDateString('es-MX', {year:'numeric',month:'long',day:'numeric'});
}

function renderHeader() {
  $('hdr-vanity').textContent = DATA.vanity ? ('&#128100; ' + DATA.vanity) : '';
  $('hdr-vanity').innerHTML = DATA.vanity ? ('&#128100; ' + esc(DATA.vanity)) : '';
  if (DATA.lastRefresh) {
    const d = new Date(DATA.lastRefresh);
    $('hdr-time').textContent = 'Actualizado: ' + d.toLocaleDateString('es-MX') + ' ' + d.toLocaleTimeString('es-MX', {hour:'2-digit',minute:'2-digit'});
  }
}

function renderBanners() {
  let html = '';
  // Comparison
  const c = DATA.comparison || {};
  if (c.newSales || c.endedSales || c.priceDrops) {
    let parts = [];
    if (c.newSales) parts.push('<span class="comp-badge comp-green">' + c.newSales + ' nuevas ofertas</span>');
    if (c.endedSales) parts.push('<span class="comp-badge comp-red">' + c.endedSales + ' terminaron</span>');
    if (c.priceDrops) parts.push('<span class="comp-badge comp-blue">' + c.priceDrops + ' bajaron</span>');
    html += '<div class="comp-row">vs ' + esc(c.prevDate) + ': ' + parts.join(' ') + '</div>';
  }
  // Sale
  if (DATA.saleName) {
    html += '<div class="sale-banner">&#127991; ' + esc(DATA.saleName) + '</div>';
  }
  // Recommendation
  if (DATA.buyNow && DATA.buyNow.length > 0) {
    const items = DATA.buyNow.slice(0,5).map(d =>
      '<a href="' + STORE + d.id + '/" target="_blank">' + esc(d.name) + ' <small>-' + d.discount + '%</small></a>'
    ).join(' ');
    html += '<div class="rec-buy">&#128722; <strong>Comprar ahora:</strong> ' + items + '</div>';
  } else if (DATA.onSaleCount === 0 && DATA.missingCount > 0) {
    html += '<div class="rec-wait">&#9203; Sin ofertas activas &mdash; espera al <strong>Summer Sale</strong> (25 jun, ~75% off). Costo estimado: <strong>Mex$ ' + fmt(DATA.estSummer75) + '</strong></div>';
  }
  $('banners').innerHTML = html;
}

function renderStats() {
  const d = DATA;
  const savings = d.costOrig - d.costCurr;
  let html = '';
  html += '<div class="st gold"><div class="v">' + d.ownedCount + '/' + d.totalDlcs + '</div><div class="l">Posees</div></div>';
  html += '<div class="st"><div class="v">' + d.missingCount + '</div><div class="l">Faltan</div></div>';
  html += '<div class="st y"><div class="v">$' + fmt(d.costCurr) + '</div><div class="l">Costo actual</div></div>';
  if (savings > 0) {
    html += '<div class="st g"><div class="v">-$' + fmt(savings) + '</div><div class="l">Ahorro ofertas</div></div>';
  } else {
    html += '<div class="st"><div class="v">$' + fmt(d.costOrig) + '</div><div class="l">Precio normal</div></div>';
  }
  html += '<div class="st g"><div class="v">' + d.onSaleCount + '</div><div class="l">En oferta</div></div>';
  html += '<div class="st g"><div class="v">$' + fmt(d.estSummer75) + '</div><div class="l">Est. Summer 75%</div></div>';
  $('stats-grid').innerHTML = html;
}

function renderDonut() {
  const pct = DATA.totalDlcs > 0 ? Math.round(DATA.ownedCount / DATA.totalDlcs * 100) : 0;
  const offset = 440 - (440 * pct / 100);
  $('donut-fill').setAttribute('stroke-dashoffset', offset);
  $('donut-pct').textContent = pct + '%';
  $('donut-lbl').textContent = DATA.ownedCount + '/' + DATA.totalDlcs + ' DLCs';
}

function renderLegend() {
  const onSale = DATA.dlcs.filter(d => d.discount > 0).length;
  const fullPrice = DATA.dlcs.length - onSale;
  let html = '';
  html += '<div class="legend-item"><span class="legend-dot" style="background:var(--accent)"></span>Poseidos: ' + DATA.ownedCount + '</div>';
  html += '<div class="legend-item"><span class="legend-dot" style="background:var(--green)"></span>En oferta: ' + onSale + '</div>';
  html += '<div class="legend-item"><span class="legend-dot" style="background:var(--text2)"></span>Precio normal: ' + fullPrice + '</div>';
  html += '<div class="legend-item"><span class="legend-dot" style="background:var(--red)"></span>Faltan: ' + DATA.missingCount + '</div>';
  $('legend').innerHTML = html;
}

/* ──── DLC Table ──── */
function renderTable() {
  const sale = $('f-sale').value;
  const q = $('f-q').value.toLowerCase();

  let dlcs = DATA.dlcs.filter(d => {
    if (sale === 'y' && d.discount === 0) return false;
    if (sale === 'n' && d.discount > 0) return false;
    if (q && !d.name.toLowerCase().includes(q)) return false;
    return true;
  });

  // Sort
  dlcs.sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? (va - vb) : (vb - va);
  });

  // Sort arrows
  document.querySelectorAll('.sort-arrow').forEach(el => el.textContent = '');
  const arrow = $('sa-' + sortKey);
  if (arrow) arrow.innerHTML = sortAsc ? '&#9650;' : '&#9660;';

  const tbody = $('tbody');
  tbody.innerHTML = dlcs.map(d => {
    const disc = d.discount > 0
      ? '<span class="sale-tag">-' + d.discount + '%</span>'
      : '&mdash;';
    const spark = sparkSvg(d.id);
    return '<tr data-id="' + d.id + '">' +
      '<td><input type="checkbox" class="chk" onchange="toggleOwned(\'' + d.id + '\')"></td>' +
      '<td><div class="dlc-cell"><img src="' + CAP + d.id + '/capsule_231x87.jpg" loading="lazy" onerror="this.style.display=\'none\'"><div class="dlc-info"><div class="dlc-name"><a href="' + STORE + d.id + '/" target="_blank">' + esc(d.name) + '</a></div></div></div></td>' +
      '<td>' + esc(d.priceFmt) + '</td>' +
      '<td>' + disc + '</td>' +
      '<td>' + spark + '</td></tr>';
  }).join('');

  $('f-count').textContent = dlcs.length + '/' + DATA.dlcs.length + ' DLCs';
}

function doSort(key) {
  if (sortKey === key) sortAsc = !sortAsc;
  else { sortKey = key; sortAsc = (key === 'name'); }
  renderTable();
}

function sparkSvg(id) {
  const pts = DATA.history[id];
  if (!pts || pts.length < 2) return '';
  const max = Math.max(...pts), min = Math.min(...pts), range = max - min || 1;
  const w = 70, h = 22, step = w / (pts.length - 1);
  const coords = pts.map((p, i) => Math.round(i * step) + ',' + Math.round(h - 2 - (p - min) / range * (h - 4))).join(' ');
  return '<svg class="sparkline" viewBox="0 0 ' + w + ' ' + h + '"><polyline points="' + coords + '"/></svg>';
}

/* ──── Toggle owned ──── */
async function toggleOwned(appid) {
  try {
    const r = await fetch('/api/toggle', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({appid}),
    });
    const result = await r.json();
    // Reload data and re-render
    await loadData();
  } catch(e) {}
}

async function unmarkOwned(appid) {
  await toggleOwned(appid);
}

/* ──── Bundles ──── */
/* ──── Bundles ──── */
function renderBundles() {
  const card = $('bundles-card');
  const grid = $('bundles-grid');
  if (!DATA.bundles || !DATA.bundles.length) { card.style.display = 'none'; return; }
  card.style.display = 'block';
  grid.innerHTML = DATA.bundles.map(b => {
    const ownedInBundle = b.dlcAppids.filter(id => DATA.owned.some(o => o.id === id)).length;
    const allOwned = ownedInBundle === b.count;
    let btns = '';
    if (allOwned) {
      btns = '<button class="bcard-btn done" disabled>&#9989; Marcado</button>' +
             '<button class="bcard-btn" style="background:var(--red);margin-left:.3rem" onclick="unmarkBundle(\'' + b.id + '\')">Deshacer</button>';
    } else if (ownedInBundle > 0) {
      btns = '<button class="bcard-btn" onclick="markBundle(\'' + b.id + '\')">Marcar restantes</button>' +
             '<button class="bcard-btn" style="background:var(--red);margin-left:.3rem" onclick="unmarkBundle(\'' + b.id + '\')">Deshacer</button>';
    } else {
      btns = '<button class="bcard-btn" onclick="markBundle(\'' + b.id + '\')">Tengo este bundle</button>';
    }
    return '<div class="bcard">' +
      '<div class="bcard-info"><div class="bcard-name">' + esc(b.name) + '</div>' +
      '<div class="bcard-meta">' + b.count + ' DLCs &middot; ' + ownedInBundle + ' marcados</div></div>' +
      '<div style="display:flex;flex-wrap:wrap">' + btns + '</div></div>';
  }).join('');
}

async function markBundle(bundleId) {
  try {
    const r = await fetch('/api/toggle-bundle', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({bundle_id: bundleId, action: 'mark'}),
    });
    await r.json();
    await loadData();
  } catch(e) {}
}

async function unmarkBundle(bundleId) {
  try {
    const r = await fetch('/api/toggle-bundle', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({bundle_id: bundleId, action: 'unmark'}),
    });
    await r.json();
    await loadData();
  } catch(e) {}
}

/* ──── Owned panel ──── */
function renderOwned() {
  const el = $('owned-grid');
  $('owned-count-badge').textContent = DATA.owned.length;
  if (!DATA.owned.length) {
    el.innerHTML = '<p style="color:var(--text2);font-size:.85rem">No has marcado ningun DLC como comprado aun. Usa los checkboxes en la tabla de DLCs.</p>';
    return;
  }
  el.innerHTML = DATA.owned.map(d =>
    '<div class="owned-item"><img src="' + CAP + d.id + '/capsule_231x87.jpg" loading="lazy" onerror="this.style.display=\'none\'"><span>' + esc(d.name.replace(/PAYDAY 2:\s*/,'')) + '</span><button class="remove-btn" onclick="unmarkOwned(\'' + d.id + '\')" title="Desmarcar">&#10005;</button></div>'
  ).join('');
}

/* ───��� Simulator ──── */
function simulate() {
  if (!DATA) return;
  const pct = parseInt($('sim-slider').value);
  $('sim-pct').textContent = pct + '%';
  let total = 0;
  DATA.dlcs.forEach(d => {
    if (d.discount > 0) total += d.price; // already discounted
    else total += d.orig * (1 - pct / 100);
  });
  total /= 100;
  const orig = DATA.dlcs.reduce((s, d) => s + d.orig, 0) / 100;
  const count = DATA.dlcs.length;
  $('sim-cost').textContent = 'Mex$ ' + fmt(Math.round(total));
  $('sim-save').textContent = 'Mex$ ' + fmt(Math.round(orig - total));
  $('sim-avg').textContent = count > 0 ? ('~Mex$ ' + fmt(Math.round(total / count)) + '/DLC') : '--';
}

/* ──── Budget planner ──── */
function calcBudget() {
  const budget = parseFloat($('budget-input').value) || 0;
  if (budget <= 0) { $('budget-result').innerHTML = '<div class="budget-result">Ingresa un presupuesto mayor a 0</div>'; return; }

  const sorted = [...DATA.dlcs].sort((a, b) => b.discount - a.discount || a.price - b.price);
  let remaining = budget;
  const picks = [];
  sorted.forEach(d => {
    const price = d.price / 100;
    if (price > 0 && price <= remaining) {
      picks.push(d);
      remaining -= price;
    }
  });

  const totalSpent = budget - remaining;
  let html = '<div class="budget-result">Con <strong>Mex$ ' + fmt(budget) + '</strong> puedes comprar <span class="val">' + picks.length + ' DLCs</span> por <span class="val">Mex$ ' + fmt(Math.round(totalSpent)) + '</span>';
  if (remaining > 0) html += ' (sobran $' + fmt(Math.round(remaining)) + ')';
  html += '</div>';

  if (picks.length) {
    html += '<div class="budget-list">';
    picks.forEach((d, i) => {
      const disc = d.discount > 0 ? ' <small style="color:var(--green)">-' + d.discount + '%</small>' : '';
      html += '<div class="budget-item"><a href="' + STORE + d.id + '/" target="_blank">' + esc(d.name.replace(/PAYDAY 2:\s*/,'')) + disc + '</a><span class="bi-price">' + esc(d.priceFmt) + '</span></div>';
    });
    html += '</div>';
  }
  $('budget-result').innerHTML = html;
}

/* ──── Sales table ──── */
function renderSales() {
  if (!DATA.upcomingSales) return;
  $('sales-table').innerHTML = '<tr style="color:var(--text2);font-weight:600"><td>Evento</td><td>Fecha</td><td>Desc.</td><td>Costo estimado</td></tr>' +
    DATA.upcomingSales.map(s =>
      '<tr><td>' + esc(s.event) + '</td><td style="color:var(--text2)">' + esc(s.date) + '</td><td style="color:var(--yellow)">-' + s.discount + '%</td><td class="est">Mex$ ' + fmt(s.est) + '</td></tr>'
    ).join('');
}

/* ──── Tabs ──── */
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t, i) => {
    const panels = ['dlcs','tools','owned','settings'];
    t.classList.toggle('active', panels[i] === name);
  });
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  const panel = $('panel-' + name);
  if (panel) panel.classList.add('active');
}

/* ──── Refresh ──── */
async function doRefresh() {
  const btn = $('btn-refresh');
  btn.classList.add('loading');
  btn.disabled = true;
  window._refreshStart = Date.now();

  const panel = $('refresh-panel');
  const consoleEl = $('console');
  panel.classList.add('visible');
  consoleEl.innerHTML = '';
  $('prog-bar').style.width = '0%';
  $('prog-bar').style.background = 'linear-gradient(90deg, var(--gold), #b8922e)';
  $('prog-text').textContent = 'Iniciando... (puede tardar 1-3 min con cache vacio)';

  try {
    const resp = await fetch('/api/refresh', {method: 'POST'});
    if (resp.status === 409) {
      appendConsole('Ya hay una actualizacion en curso.', 'warn');
      btn.classList.remove('loading'); btn.disabled = false;
      return;
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of block.split('\n')) {
          if (line.startsWith('data: ')) {
            try { handleSSE(JSON.parse(line.slice(6))); } catch(e) {}
          }
        }
      }
    }
  } catch(e) {
    appendConsole('Error: ' + e.message, 'err');
  }

  btn.classList.remove('loading');
  btn.disabled = false;

  // Reload data — if loadData doesn't populate, force full page reload
  await loadData();
  if (!DATA || !DATA.totalDlcs) {
    location.reload();
  }
}

function handleSSE(ev) {
  if (ev.type === 'line') {
    appendConsole(ev.text, ev.cls || 'normal');
  } else if (ev.type === 'progress') {
    const pct = Math.round(ev.current / ev.total * 100);
    $('prog-bar').style.width = pct + '%';
    let eta = '';
    if (ev.current > 1 && window._refreshStart) {
      const elapsed = (Date.now() - window._refreshStart) / 1000;
      const remaining = (elapsed / ev.current) * (ev.total - ev.current);
      if (remaining > 60) eta = ' ~' + Math.round(remaining / 60) + 'min';
      else if (remaining > 5) eta = ' ~' + Math.round(remaining) + 's';
    }
    $('prog-text').textContent = '[' + ev.current + '/' + ev.total + '] ' + ev.label + eta;
  } else if (ev.type === 'done') {
    $('prog-bar').style.width = '100%';
    if (ev.exit_code === 0) {
      $('prog-text').textContent = 'Completado!';
      $('prog-bar').style.background = 'linear-gradient(90deg, var(--green), #4eaa5a)';
      // Auto-hide after 3s
      setTimeout(() => { $('refresh-panel').classList.remove('visible'); }, 3000);
    } else {
      $('prog-text').textContent = 'Error (codigo ' + ev.exit_code + ')';
      $('prog-bar').style.background = 'linear-gradient(90deg, var(--red), #a02020)';
    }
  }
}

function appendConsole(text, cls) {
  const div = document.createElement('div');
  div.className = 'line line-' + (cls || 'normal');
  div.textContent = text;
  $('console').appendChild(div);
  $('console').scrollTop = $('console').scrollHeight;
}

/* ──── Config ──── */
async function saveConfig() {
  const cfg = {};
  const v = $('cfg-vanity').value.trim(); if (v) cfg.vanity = v;
  const k = $('cfg-key').value.trim(); if (k) cfg.key = k;
  const i = $('cfg-itad').value.trim(); if (i) cfg.itad_key = i;
  try {
    await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(cfg)});
    $('cfg-status').textContent = 'Guardado! Haz click en "Actualizar datos" para aplicar.';
    setTimeout(() => $('cfg-status').textContent = '', 4000);
  } catch(e) {
    $('cfg-status').textContent = 'Error al guardar';
    $('cfg-status').style.color = 'var(--red)';
  }
}

async function quickSetup() {
  const v = $('setup-vanity').value.trim();
  const k = $('setup-key').value.trim();
  if (!v) { $('setup-vanity').style.borderColor='var(--red)'; $('setup-vanity').focus(); setTimeout(()=>$('setup-vanity').style.borderColor='',2000); return; }
  const cfg = {vanity: v};
  if (k) cfg.key = k;
  try {
    await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(cfg)});
    // Also fill settings
    $('cfg-vanity').value = v;
    if (k) $('cfg-key').value = k;
    // Trigger refresh
    $('empty-state').style.display = 'none';
    $('dashboard').style.display = 'block';
    doRefresh();
  } catch(e) { alert('Error: ' + e.message); }
}

/* ──── Init ──── */
loadData();
</script>
</body>
</html>"""


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
