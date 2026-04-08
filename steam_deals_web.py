#!/usr/bin/env python3
"""
Steam Deals Web UI — Interfaz web para steam_deals_generator.py
Ejecuta: python3 steam_deals_web.py
Abre: http://127.0.0.1:8080
"""

import json
import os
import re
import signal
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "steam_deals_generator.py"
PD2_SCRIPT_PATH = Path(__file__).resolve().parent / "payday2_dlc_tracker.py"
CONFIG_FILE = Path.home() / ".config" / "steam_deals.json"
DEFAULT_PORT = 8080

_running_proc = None
_proc_lock = threading.Lock()

WATCHLIST_FILE = Path.home() / ".config" / "steam_deals_watchlist.json"
LOCAL_CACHE_DIR = SCRIPT_PATH.parent / ".cache" / "steam_deals"

# ─── Config I/O ──────────────────────────────────

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def load_watchlist() -> list:
    if not WATCHLIST_FILE.exists():
        return []
    try:
        return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_watchlist(items: list) -> None:
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def has_local_cache() -> bool:
  try:
    return LOCAL_CACHE_DIR.exists() and any(LOCAL_CACHE_DIR.iterdir())
  except OSError:
    return False


# ─── ANSI helpers ────────────────────────────────

_ANSI_RE = re.compile(r'\033\[[0-9;]*m')
_STEP_RE = re.compile(r'\[(\d+)/(\d+)\]\s*(.*)')


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)


def classify_line(raw: str) -> tuple[str, str]:
    """Return (cleaned_text, css_class)."""
    text = strip_ansi(raw).rstrip()
    if not text:
        return text, "dim"
    if '✓' in raw or '✓' in text:
        return text, "ok"
    if '⚠' in raw or '⚠' in text:
        return text, "warn"
    if '✗' in raw or '✗' in text:
        return text, "err"
    if '\033[36m' in raw:  # cyan = step header
        return text, "step"
    if '\033[2m' in raw:  # dim
        return text, "dim"
    if '───' in text or '===' in text:
        return text, "bold"
    return text, "normal"


def extract_progress(text: str) -> tuple[int, int, str] | None:
    m = _STEP_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2)), m.group(3).strip()
    return None


def detect_file_path(text: str) -> str | None:
    """Detect generated file paths from ✓ output lines."""
    m = re.search(r'✓\s+(.+\.(?:md|html|csv))$', text.strip())
    return m.group(1).strip() if m else None


# ─── Build CLI command ───────────────────────────

def build_command(config: dict, filters: dict) -> list[str]:
    cmd = [sys.executable, str(SCRIPT_PATH), "--web-run"]
    if config.get("vanity"):
        cmd += ["--vanity", config["vanity"]]
    if config.get("key"):
        cmd += ["--key", config["key"]]
    if config.get("hltb"):
        cmd += ["--hltb", config["hltb"]]
    if config.get("output"):
        cmd += ["--output", config["output"]]
    if config.get("discount") is not None:
        cmd += ["--discount", str(config["discount"])]
    if config.get("genres"):
        genres = config["genres"]
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(",") if g.strip()]
        if genres:
            cmd += ["--genre"] + genres
    if config.get("family_json"):
        cmd += ["--family-json", config["family_json"]]
    if config.get("itad_key"):
        cmd += ["--itad-key", config["itad_key"]]
    # Filters
    if filters.get("no_cache"):
        cmd.append("--no-cache")
    if filters.get("max_price"):
        cmd += ["--max-price", str(filters["max_price"])]
    if filters.get("deck_only"):
        cmd.append("--deck-only")
    if filters.get("deck_verified"):
        cmd.append("--deck-verified")
    if filters.get("min_reviews"):
        cmd += ["--min-reviews", str(filters["min_reviews"])]
    if filters.get("min_review_count"):
        cmd += ["--min-review-count", str(filters["min_review_count"])]
    if filters.get("max_hours"):
        cmd += ["--max-hours", str(filters["max_hours"])]
    if filters.get("top"):
        cmd += ["--top", str(filters["top"])]
    if filters.get("sort") and filters["sort"] != "discount":
        cmd += ["--sort", filters["sort"]]
    if filters.get("new_only"):
        cmd.append("--new-only")
    if filters.get("csv"):
        cmd.append("--csv")
    if filters.get("budget"):
        cmd += ["--budget", str(filters["budget"])]
    if config.get("compare"):
        cmd += ["--compare", config["compare"]]
    if config.get("telegram_token"):
        cmd += ["--telegram-token", config["telegram_token"]]
    if config.get("telegram_chat"):
        cmd += ["--telegram-chat", config["telegram_chat"]]
    if config.get("discord_webhook"):
        cmd += ["--discord-webhook", config["discord_webhook"]]
    return cmd


def build_pd2_command(config: dict, filters: dict) -> list[str]:
    cmd = [sys.executable, str(PD2_SCRIPT_PATH)]
    if config.get("vanity"):
        cmd += ["--vanity", config["vanity"]]
    if config.get("key"):
        cmd += ["--key", config["key"]]
    if config.get("itad_key"):
        cmd += ["--itad-key", config["itad_key"]]
    if config.get("output"):
        cmd += ["--output", config["output"]]
    if filters.get("no_cache"):
        cmd.append("--no-cache")
    if filters.get("budget"):
        cmd += ["--budget", str(filters["budget"])]
    if filters.get("alert_price"):
        cmd += ["--alert-price", str(filters["alert_price"])]
    if filters.get("csv"):
        cmd.append("--csv")
    if filters.get("min_deal"):
        cmd += ["--min-deal", str(filters["min_deal"])]
    return cmd


# ─── HTML page ───────────────────────────────────

PAGE_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Steam Tools</title>
<style>
:root {
  --bg: #1b2838; --bg2: #2a475e; --card: #16202d; --card-border: #2a475e;
  --accent: #66c0f4; --accent-hover: #4db8e8; --text: #c7d5e0; --text2: #8f98a0;
  --green: #6cc644; --yellow: #f0b232; --red: #c7322e; --console-bg: #0e1a26;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg); color: var(--text); min-height: 100vh;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Header */
.header {
  background: linear-gradient(135deg, #171a21, #1b2838);
  border-bottom: 1px solid var(--card-border);
  padding: 1.2rem 0; text-align: center;
}
.header h1 { font-size: 1.5rem; font-weight: 600; letter-spacing: 0.02em; }
.header h1 span { color: var(--accent); }

/* Container */
.container { max-width: 720px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }

/* Cards */
.card {
  background: var(--card); border: 1px solid var(--card-border);
  border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem;
}
.card h2 { font-size: 1rem; color: var(--accent); margin-bottom: 1rem; font-weight: 600; }

/* Form fields */
.field { margin-bottom: 1rem; }
.field label {
  display: block; font-size: 0.85rem; color: var(--text2);
  margin-bottom: 0.3rem; font-weight: 500;
}
.field .hint { font-size: 0.75rem; color: var(--text2); margin-top: 0.25rem; opacity: 0.7; }
.optional { color: var(--text2); font-weight: 400; font-size: 0.75rem; }
input[type="text"], input[type="number"], input[type="password"], select {
  width: 100%; padding: 0.55rem 0.75rem; font-size: 0.9rem;
  background: var(--bg); border: 1px solid var(--card-border); border-radius: 6px;
  color: var(--text); outline: none; transition: border-color 0.2s;
}
input:focus, select:focus { border-color: var(--accent); }
input::placeholder { color: var(--text2); opacity: 0.5; }

/* Password toggle */
.pw-wrap { position: relative; }
.pw-wrap input { padding-right: 2.5rem; }
.pw-toggle {
  position: absolute; right: 0.5rem; top: 50%; transform: translateY(-50%);
  background: none; border: none; color: var(--text2); cursor: pointer;
  font-size: 1.1rem; padding: 0.25rem;
}
.pw-toggle:hover { color: var(--text); }

/* Row (multi-column) */
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 500px) { .row { grid-template-columns: 1fr; } }

/* Range slider */
.range-wrap { display: flex; align-items: center; gap: 0.75rem; }
.range-wrap input[type="range"] {
  flex: 1; -webkit-appearance: none; height: 6px; background: var(--bg2);
  border-radius: 3px; outline: none;
}
.range-wrap input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none; width: 18px; height: 18px; border-radius: 50%;
  background: var(--accent); cursor: pointer; border: 2px solid var(--card);
}
.range-wrap .range-val {
  min-width: 3rem; text-align: center; font-weight: 600;
  font-size: 0.95rem; color: var(--accent);
}

/* Details / collapsible */
details { margin-bottom: 1rem; }
details summary {
  cursor: pointer; font-size: 0.9rem; color: var(--text2); padding: 0.4rem 0;
  font-weight: 500; user-select: none; list-style: none;
}
details summary::before { content: '▸ '; transition: transform 0.2s; }
details[open] summary::before { content: '▾ '; }
details summary:hover { color: var(--text); }
details .details-body { padding-top: 0.75rem; }

/* Checkboxes */
.checks {
  display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem 1rem;
}
@media (max-width: 500px) { .checks { grid-template-columns: 1fr; } }
.checks label {
  display: flex; align-items: center; gap: 0.5rem;
  font-size: 0.85rem; color: var(--text2); cursor: pointer;
}
.checks input[type="checkbox"] {
  accent-color: var(--accent); width: 16px; height: 16px;
}

/* Buttons */
.actions { display: flex; gap: 0.75rem; margin-top: 0.5rem; }
.btn {
  padding: 0.7rem 1.5rem; border: none; border-radius: 6px;
  font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.btn-primary {
  background: linear-gradient(135deg, var(--accent), #4b9cd3);
  color: #fff; flex: 1;
}
.btn-primary:hover:not(:disabled) { background: linear-gradient(135deg, var(--accent-hover), #3d8bc2); }
.btn-danger {
  background: var(--bg2); color: var(--red); border: 1px solid var(--red);
}
.btn-danger:hover:not(:disabled) { background: var(--red); color: #fff; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Progress bar */
.progress-container {
  background: var(--bg); border-radius: 4px; height: 28px; position: relative;
  overflow: hidden; margin-bottom: 0.75rem;
}
.progress-bar {
  height: 100%; background: linear-gradient(90deg, var(--accent), #4b9cd3);
  border-radius: 4px; transition: width 0.4s ease; width: 0%;
}
.progress-text {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.8rem; font-weight: 600; color: var(--text);
  text-shadow: 0 1px 2px rgba(0,0,0,0.5);
}

/* Console */
.console {
  background: var(--console-bg); border: 1px solid var(--card-border);
  border-radius: 6px; padding: 0.75rem; font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.8rem; line-height: 1.5; max-height: 55vh; overflow-y: auto;
  min-height: 120px;
}
.console:empty::before {
  content: 'Listo para ejecutar...'; color: var(--text2); opacity: 0.5;
}
.console .line { white-space: pre-wrap; word-break: break-all; }
.console .line-ok { color: var(--green); }
.console .line-warn { color: var(--yellow); }
.console .line-err { color: var(--red); }
.console .line-step { color: var(--accent); font-weight: 600; }
.console .line-dim { color: var(--text2); opacity: 0.7; }
.console .line-bold { color: var(--text); font-weight: 700; }

/* File links */
.file-links {
  display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem;
}
.file-link {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.5rem 1rem; background: var(--bg2); border: 1px solid var(--card-border);
  border-radius: 6px; color: var(--accent); font-size: 0.85rem;
  font-weight: 500; transition: all 0.2s;
}
.file-link:hover { background: var(--accent); color: #fff; text-decoration: none; border-color: var(--accent); }
.hidden { display: none !important; }

/* Wizard */
.wizard-overlay { display: none; position: fixed; inset: 0; background: var(--bg); z-index: 1000; overflow-y: auto; }
.wizard { max-width: 560px; margin: 0 auto; padding: 2rem 1rem 3rem; }
.wizard h1 { font-size: 1.6rem; text-align: center; margin-bottom: 0.3rem; }
.wizard .subtitle { text-align: center; color: var(--text2); font-size: 0.9rem; margin-bottom: 2rem; }
.wizard .step { display: none; }
.wizard .step.active { display: block; }
.wizard .step-card { background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1rem; }
.wizard .step-num { display: inline-block; background: var(--accent); color: #000; font-weight: 700; font-size: 0.8rem; padding: 0.15rem 0.6rem; border-radius: 10px; margin-bottom: 0.6rem; }
.wizard .step-card h2 { font-size: 1.1rem; margin-bottom: 0.6rem; }
.wizard .step-card p { font-size: 0.88rem; color: var(--text2); line-height: 1.6; margin-bottom: 0.8rem; }
.wizard .step-card .example { background: var(--bg); border: 1px solid var(--card-border); border-radius: 6px; padding: 0.6rem 0.8rem; font-family: monospace; font-size: 0.85rem; color: var(--accent); margin: 0.5rem 0; word-break: break-all; }
.wizard .step-card .tip { background: #1a2a1a; border: 1px solid #2a4a2a; border-radius: 6px; padding: 0.5rem 0.8rem; font-size: 0.82rem; color: var(--green); margin-top: 0.5rem; }
.wizard .step-card .optional-tag { display: inline-block; background: var(--bg2); color: var(--text2); font-size: 0.7rem; padding: 0.1rem 0.4rem; border-radius: 4px; margin-left: 0.3rem; font-weight: 400; }
.wizard .nav { display: flex; gap: 0.75rem; margin-top: 1rem; }
.wizard .nav .btn { flex: 1; }
.wizard .btn-secondary { background: var(--bg2); color: var(--text); border: 1px solid var(--card-border); }
.wizard .btn-secondary:hover { border-color: var(--accent); }
.wizard .dots { display: flex; justify-content: center; gap: 0.5rem; margin-bottom: 1.5rem; }
.wizard .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--bg2); border: 1px solid var(--card-border); transition: all 0.3s; }
.wizard .dot.active { background: var(--accent); border-color: var(--accent); }
.wizard .dot.done { background: var(--green); border-color: var(--green); }
</style>
</head>
<body>

<!-- ══ Setup Wizard ══ -->
<div class="wizard-overlay" id="wizard-overlay">
<div class="wizard">
  <h1>&#127918; Steam Deals Generator</h1>
  <p class="subtitle">Configura tu perfil en unos pasos</p>
  <div class="dots">
    <div class="dot active" id="dot-0"></div>
    <div class="dot" id="dot-1"></div>
    <div class="dot" id="dot-2"></div>
    <div class="dot" id="dot-3"></div>
  </div>

  <!-- Step 0: Vanity URL -->
  <div class="step active" id="wiz-step-0">
    <div class="step-card">
      <span class="step-num">Paso 1 de 4</span>
      <h2>&#128100; Tu perfil de Steam</h2>
      <p>Necesitamos tu <strong>Vanity URL</strong> o <strong>Steam ID</strong> para encontrar tu wishlist.</p>
      <p>Lo encuentras en tu perfil de Steam &rarr; la parte final de la URL:</p>
      <div class="example">https://steamcommunity.com/id/<strong>TU_VANITY_URL</strong>/</div>
      <p>Tambien puede ser tu Steam ID (17 digitos):</p>
      <div class="example">https://steamcommunity.com/profiles/<strong>76561198012345678</strong>/</div>
      <div class="field" style="margin-top:1rem">
        <label>Tu perfil de Steam</label>
        <input type="text" id="wiz-vanity" placeholder="tu_vanity_url, Steam ID, o URL completa">
      </div>
      <div class="tip">&#128161; Si pegas la URL completa del perfil, se extrae automaticamente.</div>
    </div>
    <div class="nav">
      <button class="btn btn-primary" onclick="wizNext()">Siguiente &#8594;</button>
    </div>
  </div>

  <!-- Step 1: Steam API Key -->
  <div class="step" id="wiz-step-1">
    <div class="step-card">
      <span class="step-num">Paso 2 de 4</span>
      <h2>&#128273; Steam API Key <span class="optional-tag">opcional</span></h2>
      <p>Con una API Key obtienes datos extra:</p>
      <ul style="font-size:.88rem;color:var(--text2);margin:0.3rem 0 0.8rem 1.2rem;line-height:1.8">
        <li>Ver juegos que ya tienes (para limpiar la wishlist)</li>
        <li>Mejor deteccion de biblioteca familiar</li>
        <li>Nota: la API de Steam no detecta DLCs poseidos, solo juegos</li>
      </ul>
      <p><strong>Sin key tambien funciona</strong> para wishlist &mdash; solo necesitas que sea publica.</p>
      <p>Para obtenerla:</p>
      <ol style="font-size:.85rem;color:var(--text2);margin:0.3rem 0 0.8rem 1.2rem;line-height:1.8">
        <li>Ve a <a href="https://steamcommunity.com/dev/apikey" target="_blank">steamcommunity.com/dev/apikey</a></li>
        <li>Pon cualquier nombre de dominio (ej: <code>localhost</code>)</li>
        <li>Copia la key que te da</li>
      </ol>
      <div class="field">
        <label>Steam API Key</label>
        <div class="pw-wrap">
          <input type="password" id="wiz-key" placeholder="Dejalo vacio si no tienes">
          <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
        </div>
      </div>
    </div>
    <div class="nav">
      <button class="btn btn-secondary" onclick="wizPrev()">&#8592; Atras</button>
      <button class="btn btn-primary" onclick="wizNext()">Siguiente &#8594;</button>
    </div>
  </div>

  <!-- Step 2: ITAD Key -->
  <div class="step" id="wiz-step-2">
    <div class="step-card">
      <span class="step-num">Paso 3 de 4</span>
      <h2>&#128176; IsThereAnyDeal API Key <span class="optional-tag">opcional</span></h2>
      <p>ITAD agrega datos de otras tiendas:</p>
      <ul style="font-size:.88rem;color:var(--text2);margin:0.3rem 0 0.8rem 1.2rem;line-height:1.8">
        <li><strong>Minimo historico</strong> &mdash; el precio mas bajo que ha tenido en Steam</li>
        <li><strong>Precios multi-tienda</strong> &mdash; si otra tienda lo tiene mas barato ahora</li>
        <li><strong>Bundles activos</strong> &mdash; si el juego esta en algun bundle</li>
      </ul>
      <p>Para obtenerla:</p>
      <ol style="font-size:.85rem;color:var(--text2);margin:0.3rem 0 0.8rem 1.2rem;line-height:1.8">
        <li>Crea cuenta en <a href="https://isthereanydeal.com/" target="_blank">isthereanydeal.com</a></li>
        <li>Ve a <a href="https://isthereanydeal.com/dev/app/" target="_blank">isthereanydeal.com/dev/app/</a></li>
        <li>Crea una app y copia la API key</li>
      </ol>
      <div class="field">
        <label>ITAD API Key</label>
        <div class="pw-wrap">
          <input type="password" id="wiz-itad" placeholder="Dejalo vacio si no tienes">
          <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
        </div>
      </div>
    </div>
    <div class="nav">
      <button class="btn btn-secondary" onclick="wizPrev()">&#8592; Atras</button>
      <button class="btn btn-primary" onclick="wizNext()">Siguiente &#8594;</button>
    </div>
  </div>

  <!-- Step 3: Confirm -->
  <div class="step" id="wiz-step-3">
    <div class="step-card">
      <span class="step-num">Paso 4 de 4</span>
      <h2>&#9989; Listo!</h2>
      <p>Tu configuracion:</p>
      <div style="background:var(--bg);border-radius:6px;padding:0.8rem;margin:0.8rem 0;font-size:0.88rem">
        <div style="margin-bottom:0.3rem"><strong>Perfil:</strong> <span id="wiz-summary-vanity" style="color:var(--accent)"></span></div>
        <div style="margin-bottom:0.3rem"><strong>Steam API Key:</strong> <span id="wiz-summary-key" style="color:var(--text2)"></span></div>
        <div><strong>ITAD Key:</strong> <span id="wiz-summary-itad" style="color:var(--text2)"></span></div>
      </div>
      <p>Puedes cambiar esto cuando quieras desde el formulario principal.</p>
      <div class="tip">&#128161; La configuracion se guarda automaticamente. No tendras que hacer esto de nuevo.</div>
    </div>
    <div class="nav">
      <button class="btn btn-secondary" onclick="wizPrev()">&#8592; Atras</button>
      <button class="btn btn-primary" onclick="wizFinish()">&#128640; Empezar</button>
    </div>
  </div>
</div>
</div>

<div class="header">
  <h1><span>&#127918;</span> Steam <span>Tools</span></h1>
</div>

<div class="container">
  <!-- Tab navigation -->
  <div class="tabs" style="display:flex;gap:0;margin-bottom:1rem">
    <button class="tab-btn active" id="tab-deals" onclick="switchTab('deals')" style="flex:1;padding:.7rem;border:1px solid var(--card-border);border-radius:8px 0 0 8px;background:var(--accent);color:#fff;font-weight:600;font-size:.95rem;cursor:pointer;transition:all .2s">&#128640; Steam Deals</button>
    <button class="tab-btn" id="tab-pd2" onclick="switchTab('pd2')" style="flex:1;padding:.7rem;border:1px solid var(--card-border);border-left:none;border-radius:0 8px 8px 0;background:var(--card);color:var(--text2);font-weight:600;font-size:.95rem;cursor:pointer;transition:all .2s">&#127918; PAYDAY 2</button>
  </div>

  <!-- Shared config -->
  <div class="card">
      <h2 style="display:flex;align-items:center;justify-content:space-between;gap:.6rem">
        <span>Cuenta de Steam</span>
        <button type="button" class="btn" onclick="openWizard()" style="padding:.35rem .75rem;font-size:.8rem;background:var(--bg2);color:var(--text);border:1px solid var(--card-border)">
          Abrir wizard
        </button>
      </h2>
    <div class="field">
      <label>Perfil de Steam</label>
      <input type="text" id="vanity" placeholder="tu_vanity_url, Steam ID, o URL del perfil">
      <div class="hint">Vanity URL, Steam ID (17 digitos), o link completo del perfil</div>
    </div>
    <div class="row">
      <div class="field">
        <label>Steam API Key <span class="optional">(opcional)</span></label>
        <div class="pw-wrap">
          <input type="password" id="key" placeholder="Tu Steam API Key">
          <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
        </div>
        <div style="font-size:.72rem;color:var(--text2);margin-top:.3rem">Obtenla en <a href="https://steamcommunity.com/dev/apikey" target="_blank">steamcommunity.com/dev/apikey</a> — habilita juegos propios y biblioteca familiar</div>
      </div>
      <div class="field">
        <label>ITAD API Key <span class="optional">(opcional)</span></label>
        <div class="pw-wrap">
          <input type="password" id="itad_key" placeholder="IsThereAnyDeal Key">
          <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
        </div>
      </div>
    </div>
  </div>

  <!-- ═══ TAB: Steam Deals ═══ -->
  <div id="panel-deals">
  <div class="card">
    <h2>Configuracion</h2>
    <div class="field">
      <label>Descuento minimo</label>
      <div class="range-wrap">
        <input type="range" id="discount" min="10" max="95" step="5" value="50" oninput="document.getElementById('disc-val').textContent=this.value+'%'">
        <span class="range-val" id="disc-val">50%</span>
      </div>
    </div>
    <div class="row">
      <div class="field">
        <label>Top picks</label>
        <input type="number" id="top" value="10" min="1" max="50">
      </div>
      <div class="field">
        <label>Ordenar por</label>
        <select id="sort">
          <option value="discount">Descuento</option>
          <option value="price">Precio</option>
          <option value="reviews">Reviews</option>
          <option value="priority">Prioridad wishlist</option>
          <option value="score">Score</option>
        </select>
      </div>
    </div>
    <div class="field">
      <label>Generos <span class="optional">(opcional, separados por coma)</span></label>
      <input type="text" id="genres" placeholder="roguelike, indie, rpg">
    </div>
  </div>

  <div class="card">
    <details>
      <summary>Fuentes de datos</summary>
      <div class="details-body">
        <div class="field">
          <label>HLTB CSV <span class="optional">(opcional)</span></label>
          <input type="text" id="hltb" placeholder="~/hltb-export.csv">
          <div class="hint">Exporta desde tu perfil de HowLongToBeat</div>
        </div>
        <div class="field">
          <label>Family JSON <span class="optional">(opcional)</span></label>
          <input type="text" id="family_json" placeholder="~/familia.json">
        </div>
        <div class="field">
          <label>Directorio de salida</label>
          <input type="text" id="output" placeholder="(mismo directorio del script)">
        </div>
      </div>
    </details>

    <details>
      <summary>Filtros avanzados</summary>
      <div class="details-body">
        <div class="row">
          <div class="field">
            <label>Precio maximo (MXN)</label>
            <input type="number" id="max_price" min="0" placeholder="Sin limite">
          </div>
          <div class="field">
            <label>Min reviews %</label>
            <input type="number" id="min_reviews" min="0" max="100" placeholder="Cualquiera">
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Min # de reviews</label>
            <input type="number" id="min_review_count" min="0" placeholder="Cualquiera">
          </div>
          <div class="field">
            <label>Max HLTB horas</label>
            <input type="number" id="max_hours" min="0" placeholder="Sin limite">
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Presupuesto (MXN) <span class="optional">(Budget Mode)</span></label>
            <input type="number" id="budget" min="0" step="50" placeholder="Sin limite">
            <div class="hint">Recomienda la mejor combinacion de juegos</div>
          </div>
          <div class="field">
            <label>Comparar con <span class="optional">(opcional)</span></label>
            <input type="text" id="compare" placeholder="Vanity URL del amigo">
            <div class="hint">Wishlist del amigo debe ser publica</div>
          </div>
        </div>
        <div class="checks" style="margin-top:0.5rem">
          <label><input type="checkbox" id="deck_only"> Solo Deck compatible</label>
          <label><input type="checkbox" id="deck_verified"> Solo Deck Verified</label>
          <label><input type="checkbox" id="new_only"> Solo deals nuevos</label>
          <label><input type="checkbox" id="csv"> Generar CSV</label>
          <label><input type="checkbox" id="no_cache"> Ignorar cache</label>
        </div>
      </div>
    </details>

    <details>
      <summary>Notificaciones</summary>
      <div class="details-body">
        <div class="field">
          <label>Telegram Bot Token <span class="optional">(opcional)</span></label>
          <div class="pw-wrap">
            <input type="password" id="telegram_token" placeholder="123456:ABC-DEF...">
            <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Telegram Chat ID</label>
            <input type="text" id="telegram_chat" placeholder="-100123456789">
          </div>
          <div class="field">
            <label>Discord Webhook</label>
            <div class="pw-wrap">
              <input type="password" id="discord_webhook" placeholder="https://discord.com/api/webhooks/...">
              <button type="button" class="pw-toggle" onclick="togglePw(this)">&#128065;</button>
            </div>
          </div>
        </div>
        <div class="hint">Envia un resumen cuando hay deals nuevos o price drops</div>
      </div>
    </details>
  </div>

  <!-- Watchlist -->
  <div class="card">
    <h2>&#127919; Watchlist (Price Alerts)</h2>
    <div class="field">
      <div class="row">
        <div class="field"><label>AppID</label><input type="text" id="wl-appid" placeholder="730"></div>
        <div class="field"><label>Nombre</label><input type="text" id="wl-name" placeholder="Counter-Strike 2"></div>
        <div class="field"><label>Precio objetivo (MXN)</label><input type="number" id="wl-price" placeholder="200" min="0"></div>
      </div>
      <button class="btn btn-primary" style="margin-top:.5rem;padding:.4rem 1rem;font-size:.85rem" onclick="addWatchlist()">+ Agregar</button>
    </div>
    <div id="wl-list" style="margin-top:.75rem"></div>
  </div>

  </div><!-- /panel-deals -->

  <!-- ═══ TAB: PAYDAY 2 ═══ -->
  <div id="panel-pd2" style="display:none">
  <div class="card">
    <h2>&#127918; PAYDAY 2 DLC Tracker</h2>
    <div class="row">
      <div class="field">
        <label>Presupuesto MXN <span class="optional">(opcional)</span></label>
        <div class="range-wrap">
          <input type="range" id="pd2_budget" min="0" max="5000" step="50" value="0" oninput="document.getElementById('pd2-bval').textContent=this.value>0?('$'+this.value):'Sin limite'">
          <span class="range-val" id="pd2-bval">Sin limite</span>
        </div>
      </div>
      <div class="field">
        <label>Alerta de precio <span class="optional">(MXN)</span></label>
        <input type="number" id="pd2_alert" min="0" placeholder="Alertar si DLC baja de este precio">
      </div>
    </div>
    <div class="row">
      <div class="field">
        <label>Min. descuento para recomendar <span class="optional">(%)</span></label>
        <input type="number" id="pd2_min_deal" min="0" max="100" value="50" placeholder="50">
      </div>
      <div class="field">
        <label>Directorio de salida</label>
        <input type="text" id="pd2_output" placeholder="(mismo directorio del script)">
      </div>
    </div>
    <div class="checks" style="margin-top:0.5rem">
      <label><input type="checkbox" id="pd2_csv"> Generar CSV</label>
      <label><input type="checkbox" id="pd2_no_cache"> Ignorar cache</label>
    </div>
  </div>
  </div><!-- /panel-pd2 -->

  <div class="actions" style="margin-bottom:1rem">
    <button class="btn btn-primary" id="btn-run">&#128640; Ejecutar</button>
    <button class="btn btn-danger" id="btn-stop" disabled>&#9209; Detener</button>
  </div>

  <!-- Output panel -->
  <div class="card" id="output-card">
    <h2>Ejecucion</h2>
    <div class="progress-container">
      <div class="progress-bar" id="progress-bar"></div>
      <div class="progress-text" id="progress-text">Listo</div>
    </div>
    <div class="console" id="console"></div>
    <div class="file-links hidden" id="file-links"></div>
  </div>
</div>

<script>
// ── Helpers ──
function $(id) { return document.getElementById(id); }
function togglePw(btn) {
  const inp = btn.previousElementSibling;
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

// ── Config fields (saveable) ──
const CONFIG_FIELDS = ['vanity','key','hltb','output','discount','genres','family_json','itad_key','compare','telegram_token','telegram_chat','discord_webhook'];
const FILTER_FIELDS = ['max_price','min_reviews','min_review_count','max_hours','top','sort','budget'];
const CHECK_FIELDS  = ['deck_only','deck_verified','new_only','csv','no_cache'];

function getConfig() {
  const c = {};
  CONFIG_FIELDS.forEach(f => {
    const el = $(f);
    if (!el) return;
    if (f === 'discount') c[f] = parseInt(el.value);
    else c[f] = el.value.trim() || null;
  });
  return c;
}

function getFilters() {
  const f = {};
  FILTER_FIELDS.forEach(k => {
    const el = $(k);
    if (!el) return;
    const v = el.value.trim();
    if (k === 'sort') f[k] = v;
    else if (v) f[k] = parseFloat(v);
  });
  CHECK_FIELDS.forEach(k => {
    const el = $(k);
    if (el) f[k] = el.checked;
  });
  return f;
}

function fillForm(cfg) {
  if (!cfg) return;
  CONFIG_FIELDS.forEach(f => {
    const el = $(f);
    if (!el || cfg[f] == null) return;
    if (f === 'discount') {
      el.value = cfg[f];
      $('disc-val').textContent = cfg[f] + '%';
    } else if (f === 'genres') {
      el.value = Array.isArray(cfg[f]) ? cfg[f].join(', ') : (cfg[f] || '');
    } else if (f === 'output') {
      el.value = cfg.output_dir || cfg.output || '';
    } else {
      el.value = cfg[f] || '';
    }
  });
}

// ── Wizard ──
let wizStep = 0;
const WIZ_TOTAL = 4;

function wizUpdateDots() {
  for (let i = 0; i < WIZ_TOTAL; i++) {
    const d = document.getElementById('dot-' + i);
    d.className = 'dot' + (i === wizStep ? ' active' : i < wizStep ? ' done' : '');
  }
}

function wizShowStep(n) {
  for (let i = 0; i < WIZ_TOTAL; i++) {
    document.getElementById('wiz-step-' + i).classList.toggle('active', i === n);
  }
  wizStep = n;
  wizUpdateDots();
  if (n === 3) {
    // Update summary
    document.getElementById('wiz-summary-vanity').textContent = document.getElementById('wiz-vanity').value.trim() || '(no configurado)';
    document.getElementById('wiz-summary-key').textContent = document.getElementById('wiz-key').value.trim() ? 'Configurada' : 'No (modo publico)';
    document.getElementById('wiz-summary-itad').textContent = document.getElementById('wiz-itad').value.trim() ? 'Configurada' : 'No';
  }
}

function wizNext() {
  if (wizStep === 0 && !document.getElementById('wiz-vanity').value.trim()) {
    const inp = document.getElementById('wiz-vanity');
    inp.style.borderColor = 'var(--red)';
    inp.focus();
    setTimeout(() => inp.style.borderColor = '', 2000);
    return;
  }
  if (wizStep < WIZ_TOTAL - 1) wizShowStep(wizStep + 1);
}

function wizPrev() {
  if (wizStep > 0) wizShowStep(wizStep - 1);
}

function wizFinish() {
  const vanity = document.getElementById('wiz-vanity').value.trim();
  const key = document.getElementById('wiz-key').value.trim();
  const itad = document.getElementById('wiz-itad').value.trim();
  // Fill main form
  document.getElementById('vanity').value = vanity;
  if (key) document.getElementById('key').value = key;
  if (itad) document.getElementById('itad_key').value = itad;
  // Save config
  const cfg = {vanity};
  if (key) cfg.key = key;
  if (itad) cfg.itad_key = itad;
  fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(cfg)}).catch(() => {});
  closeWizard();
}

function prefillWizard(cfg) {
  if (!cfg) return;
  if (cfg.vanity) document.getElementById('wiz-vanity').value = cfg.vanity;
  if (cfg.key) document.getElementById('wiz-key').value = cfg.key;
  if (cfg.itad_key) document.getElementById('wiz-itad').value = cfg.itad_key;
}

function openWizard() {
  prefillWizard(getConfig());
  wizShowStep(0);
  document.getElementById('wizard-overlay').style.display = 'block';
}

function closeWizard() {
  document.getElementById('wizard-overlay').style.display = 'none';
}

// ── Load config on startup ──
Promise.all([
  fetch('/api/config').then(r => r.json()),
  fetch('/api/ui-state').then(r => r.json()),
]).then(([cfg, state]) => {
  fillForm(cfg);
  prefillWizard(cfg);
  if (state && state.has_cache) {
    closeWizard();
  } else {
    openWizard();
  }
}).catch(() => {
  fetch('/api/config').then(r => r.json()).then(cfg => {
    fillForm(cfg);
    prefillWizard(cfg);
    if (cfg && cfg.vanity) closeWizard();
    else openWizard();
  }).catch(() => {});
});

// ── Run ──
const btnRun = $('btn-run');
const btnStop = $('btn-stop');
const consoleEl = $('console');
const progressBar = $('progress-bar');
const progressText = $('progress-text');
const fileLinks = $('file-links');
let abortCtrl = null;

function appendLine(text, cls) {
  const div = document.createElement('div');
  div.className = 'line line-' + cls;
  div.textContent = text;
  consoleEl.appendChild(div);
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

btnRun.addEventListener('click', async () => {
  if (!$('vanity').value.trim()) {
    $('vanity').focus();
    $('vanity').style.borderColor = 'var(--red)';
    setTimeout(() => $('vanity').style.borderColor = '', 2000);
    return;
  }

  // Reset UI
  consoleEl.innerHTML = '';
  progressBar.style.width = '0%';
  progressText.textContent = 'Iniciando...';
  fileLinks.innerHTML = '';
  fileLinks.classList.add('hidden');
  btnRun.disabled = true;
  btnStop.disabled = false;

  abortCtrl = new AbortController();

  try {
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({config: getConfig(), filters: getFilters()}),
      signal: abortCtrl.signal,
    });

    if (resp.status === 409) {
      appendLine('Ya hay una ejecucion en curso.', 'warn');
      btnRun.disabled = false;
      btnStop.disabled = true;
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
            try {
              const ev = JSON.parse(line.slice(6));
              handleEvent(ev);
            } catch(e) {}
          }
        }
      }
    }
  } catch(e) {
    if (e.name !== 'AbortError') {
      appendLine('Error de conexion: ' + e.message, 'err');
    }
  }

  btnRun.disabled = false;
  btnStop.disabled = true;
  abortCtrl = null;
});

btnStop.addEventListener('click', async () => {
  try { await fetch('/api/stop', {method: 'POST'}); } catch(e) {}
  appendLine('--- Cancelado por el usuario ---', 'warn');
  btnStop.disabled = true;
  if (abortCtrl) abortCtrl.abort();
});

// PD2 Tracker button
$('btn-run-pd2').addEventListener('click', async () => {
  if (!$('vanity').value.trim()) { $('vanity').focus(); return; }
  consoleEl.innerHTML = '';
  progressBar.style.width = '0%';
  progressBar.style.background = 'linear-gradient(90deg, #d4a84b, #b8922e)';
  progressText.textContent = 'PAYDAY 2 Tracker...';
  fileLinks.innerHTML = '';
  fileLinks.classList.add('hidden');
  btnRun.disabled = true;
  $('btn-run-pd2').disabled = true;
  btnStop.disabled = false;
  abortCtrl = new AbortController();
  try {
    const resp = await fetch('/api/run-pd2', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        config: getConfig(),
        filters: {
          no_cache: $('pd2_no_cache').checked,
          csv: $('pd2_csv').checked,
          budget: $('pd2_budget').value ? parseFloat($('pd2_budget').value) : null,
          alert_price: $('pd2_alert').value ? parseFloat($('pd2_alert').value) : null,
          min_deal: $('pd2_min_deal').value ? parseInt($('pd2_min_deal').value) : null,
        }
      }),
      signal: abortCtrl.signal,
    });
    if (resp.status === 409) { appendLine('Ya hay una ejecucion en curso.', 'warn'); }
    else {
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
              try { handleEvent(JSON.parse(line.slice(6))); } catch(e) {}
            }
          }
        }
      }
    }
  } catch(e) { if (e.name !== 'AbortError') appendLine('Error: ' + e.message, 'err'); }
  btnRun.disabled = false;
  $('btn-run-pd2').disabled = false;
  btnStop.disabled = true;
  abortCtrl = null;
});

function handleEvent(ev) {
  if (ev.type === 'line') {
    appendLine(ev.text, ev.cls || 'normal');
  }
  else if (ev.type === 'progress') {
    const pct = Math.round(ev.current / ev.total * 100);
    progressBar.style.width = pct + '%';
    progressText.textContent = '[' + ev.current + '/' + ev.total + '] ' + ev.label;
  }
  else if (ev.type === 'done') {
    progressBar.style.width = '100%';
    if (ev.exit_code === 0) {
      progressText.textContent = 'Completado';
      progressBar.style.background = 'linear-gradient(90deg, var(--green), #4eaa5a)';
    } else {
      progressText.textContent = 'Error (codigo ' + ev.exit_code + ')';
      progressBar.style.background = 'linear-gradient(90deg, var(--red), #a02020)';
    }
    if (ev.files && ev.files.length) {
      showFiles(ev.files);
    }
  }
}

function showFiles(files) {
  fileLinks.innerHTML = '';
  const icons = {'.html': '&#128202;', '.md': '&#128196;', '.csv': '&#128203;'};
  files.forEach(f => {
    const name = f.split('/').pop();
    const ext = name.slice(name.lastIndexOf('.'));
    const icon = icons[ext] || '&#128196;';
    const a = document.createElement('a');
    a.className = 'file-link';
    a.href = '/files/' + encodeURIComponent(name);
    a.target = '_blank';
    a.innerHTML = icon + ' ' + name;
    fileLinks.appendChild(a);
  });
  fileLinks.classList.remove('hidden');
}

// ── Watchlist ──
function renderWatchlist(items) {
  const el = document.getElementById('wl-list');
  if (!items.length) { el.innerHTML = '<div style="color:var(--text2);font-size:.85rem">Watchlist vacia</div>'; return; }
  el.innerHTML = '<div style="font-size:.85rem;color:var(--text2);margin-bottom:.3rem">' + items.length + ' juegos en watchlist</div>' +
    items.map(w => '<div style="display:flex;align-items:center;gap:.5rem;padding:.3rem 0;border-bottom:1px solid var(--card-border)">' +
      '<span style="flex:1;font-size:.85rem">' + w.name + ' <span style="color:var(--text2)">(AppID ' + w.appid + ')</span></span>' +
      '<span style="font-size:.85rem;color:var(--accent)">$' + w.target_price + '</span>' +
      '<button onclick="removeWatchlist(\'' + w.appid + '\')" style="background:none;border:none;color:var(--red);cursor:pointer;font-size:1rem">&times;</button>' +
    '</div>').join('');
}
async function loadWatchlist() {
  try { const r = await fetch('/api/watchlist'); renderWatchlist(await r.json()); } catch(e) {}
}
async function addWatchlist() {
  const appid = document.getElementById('wl-appid').value.trim();
  const name = document.getElementById('wl-name').value.trim() || appid;
  const price = parseFloat(document.getElementById('wl-price').value);
  if (!appid || !price) return;
  try {
    const r = await fetch('/api/watchlist', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({appid, name, target_price:price})});
    const d = await r.json(); renderWatchlist(d.items);
    document.getElementById('wl-appid').value = '';
    document.getElementById('wl-name').value = '';
    document.getElementById('wl-price').value = '';
  } catch(e) {}
}
async function removeWatchlist(appid) {
  try {
    const r = await fetch('/api/watchlist/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({appid})});
    const d = await r.json(); renderWatchlist(d.items);
  } catch(e) {}
}
loadWatchlist();
</script>
</body>
</html>"""


# ─── HTTP Handler ────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    output_dir = str(SCRIPT_PATH.parent)

    def log_message(self, fmt, *args):
        pass  # Silenciar logs del server

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    # ── GET routes ──

    def do_GET(self):
      path = urllib.parse.urlparse(self.path).path
      if path == "/":
        self._send_html(PAGE_HTML)
      elif path == "/api/config":
        self._send_json(load_config())
      elif path == "/api/ui-state":
        self._send_json({
          "has_cache": has_local_cache(),
          "has_config": bool(load_config().get("vanity")),
        })
      elif path == "/api/watchlist":
        self._send_json(load_watchlist())
      elif path == "/api/files":
        self._serve_files_list()
      elif path.startswith("/files/"):
        self._serve_file(path[7:])
      else:
        self.send_error(404)

    # ── POST routes ──

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/run":
            self._serve_run_sse()
        elif path == "/api/run-pd2":
            self._serve_run_sse(pd2=True)
        elif path == "/api/stop":
            self._serve_stop()
        elif path == "/api/config":
            self._serve_config_save()
        elif path == "/api/watchlist":
            self._serve_watchlist_add()
        elif path == "/api/watchlist/delete":
            self._serve_watchlist_delete()
        else:
            self.send_error(404)

    # ── Config save ──

    def _serve_config_save(self):
        body = self._read_body()
        cfg = load_config()
        cfg.update(body)
        save_config(cfg)
        self._send_json({"status": "saved"})

    # ── Watchlist CRUD ──

    def _serve_watchlist_add(self):
        body = self._read_body()
        appid = body.get("appid", "").strip()
        target = body.get("target_price")
        name = body.get("name", appid)
        if not appid or target is None:
            self._send_json({"error": "appid and target_price required"}, status=400)
            return
        items = load_watchlist()
        items = [w for w in items if w["appid"] != appid]
        items.append({"appid": appid, "name": name, "target_price": float(target)})
        save_watchlist(items)
        self._send_json({"status": "added", "items": items})

    def _serve_watchlist_delete(self):
        body = self._read_body()
        appid = body.get("appid", "").strip()
        if not appid:
            self._send_json({"error": "appid required"}, status=400)
            return
        items = load_watchlist()
        items = [w for w in items if w["appid"] != appid]
        save_watchlist(items)
        self._send_json({"status": "deleted", "items": items})

    # ── Serve generated files ──

    def _serve_files_list(self):
        out_dir = Path(Handler.output_dir)
        files = []
        for ext in ("*.md", "*.html", "*.csv"):
            for f in out_dir.glob(f"Steam Deals*{ext[1:]}"):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "mtime": f.stat().st_mtime,
                })
        files.sort(key=lambda x: -x["mtime"])
        self._send_json(files[:20])

    def _serve_file(self, encoded_name: str):
        name = urllib.parse.unquote(encoded_name)
        if ".." in name or "/" in name or "\\" in name:
            self.send_error(403)
            return
        fpath = Path(Handler.output_dir) / name
        if not fpath.exists():
            self.send_error(404)
            return
        content_types = {".html": "text/html", ".md": "text/plain", ".csv": "text/csv"}
        ct = content_types.get(fpath.suffix, "application/octet-stream")
        data = fpath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{ct}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── Run (SSE stream) ──

    def _serve_run_sse(self, pd2: bool = False):
        global _running_proc

        with _proc_lock:
            if _running_proc and _running_proc.poll() is None:
                self._send_json({"error": "Already running"}, status=409)
                return

        body = self._read_body()
        config = body.get("config", {})
        filters = body.get("filters", {})

        # Save config for future sessions
        save_cfg = {}
        for k in ("vanity", "key", "hltb", "family_json", "itad_key"):
            if config.get(k):
                save_cfg[k] = config[k]
        if config.get("output"):
            save_cfg["output_dir"] = config["output"]
        if not pd2:
            if config.get("discount") is not None:
                save_cfg["discount"] = config["discount"]
            if config.get("genres"):
                g = config["genres"]
                if isinstance(g, str):
                    g = [x.strip() for x in g.split(",") if x.strip()]
                save_cfg["genres"] = g
        try:
            save_config({**load_config(), **save_cfg})
        except Exception:
            pass

        # Update output_dir for file serving
        if config.get("output"):
            Handler.output_dir = str(Path(config["output"]).expanduser())
        else:
            Handler.output_dir = str(SCRIPT_PATH.parent)

        cmd = build_pd2_command(config, filters) if pd2 else build_command(config, filters)

        # Start subprocess
        env = {
          **os.environ,
          "PYTHONUNBUFFERED": "1",
          "PYTHONIOENCODING": "utf-8",
          "PYTHONUTF8": "1",
        }
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
          stdin=subprocess.DEVNULL, env=env, text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        with _proc_lock:
            _running_proc = proc

        # SSE response
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        generated_files = []

        def send_sse(data: dict):
            try:
                self.wfile.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
            except BrokenPipeError:
                pass

        try:
            for raw_line in proc.stdout:
                text, cls = classify_line(raw_line)
                if not text and not raw_line.strip():
                    continue

                # Detect progress
                prog = extract_progress(text)
                if prog:
                    send_sse({"type": "progress", "current": prog[0], "total": prog[1], "label": prog[2]})

                # Detect generated file paths
                fpath = detect_file_path(text)
                if fpath:
                    generated_files.append(fpath)

                send_sse({"type": "line", "text": text, "cls": cls})

            proc.wait()
        except Exception:
            proc.kill()

        with _proc_lock:
            _running_proc = None

        send_sse({"type": "done", "exit_code": proc.returncode, "files": generated_files})

    # ── Stop ──

    def _serve_stop(self):
        global _running_proc
        with _proc_lock:
            if _running_proc and _running_proc.poll() is None:
                _running_proc.terminate()
                try:
                    _running_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    _running_proc.kill()
                self._send_json({"status": "stopped"})
            else:
                self._send_json({"status": "not_running"})


# ─── Main ────────────────────────────────────────

def main():
    port = DEFAULT_PORT
    server = None
    for p in range(port, port + 10):
        try:
            server = HTTPServer(("127.0.0.1", p), Handler)
            port = p
            break
        except OSError:
            continue

    if not server:
        print(f"Error: no se pudo abrir ningún puerto ({DEFAULT_PORT}-{DEFAULT_PORT+9})")
        sys.exit(1)

    url = f"http://127.0.0.1:{port}"
    print(f"\n  \033[36m🎮 Steam Deals Web UI\033[0m")
    print(f"  \033[1m{url}\033[0m")
    print(f"  Ctrl+C para cerrar\n")

    threading.Timer(0.5, webbrowser.open, args=[url]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        with _proc_lock:
            if _running_proc and _running_proc.poll() is None:
                _running_proc.terminate()
        server.server_close()
        print("\n  Cerrado.")


if __name__ == "__main__":
    main()
