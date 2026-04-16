---
source: Context7 API + official docs
library: pywebview
package: pywebview
topic: linux-macos-dependencies-backend-packaging-browser-fallback
fetched: 2026-04-16T00:00:00Z
official_docs: https://pywebview.flowrl.com/guide/
---

# pywebview practical notes for Linux/macOS desktop wrappers

## Native dependencies

- **Linux requires choosing a renderer explicitly**: install either `pywebview[gtk]` or `pywebview[qt]`.
- **Linux GTK path** uses PyGObject and distro packages like `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-3.0`, and `gir1.2-webkit2-4.1`; **WebKit2 2.22+ is required**.
- **Linux Qt path** is usually handled by `pip install pywebview[qt]`, but some systems still need distro Qt packages, especially QtWebEngine / QtWebChannel packages.
- **macOS default backend is Cocoa via PyObjC**. On system Python, PyObjC may already exist; on standalone Python installs, install at least: `pyobjc-core`, `pyobjc-framework-Cocoa`, `pyobjc-framework-Quartz`, `pyobjc-framework-WebKit`, `pyobjc-framework-security`.
- **macOS can also use Qt**, but Cocoa/PyObjC is the native/default route.

## Backend/runtime behavior

- `webview.start()` runs the GUI loop and **blocks**; backend startup logic should run via `webview.start(func, *args)` or another thread/process.
- For a **local web UI**, pywebview can:
  - point to an already-running local URL,
  - auto-serve a **relative local path** with its built-in Bottle HTTP server,
  - or mount an external **WSGI app** such as Flask directly in `create_window`.
- Relative local paths automatically start pywebview's internal HTTP server; `webview.start(ssl=True)` can enable SSL if needed.
- `file://` loading is possible but **discouraged** for distribution because renderer support/limitations make packaging harder.

## Packaging

- **Linux/Windows**: official docs recommend **PyInstaller**.
- Include built frontend assets with `--add-data`; for a Vite/React build, add the build output directory instead of source files.
- On Linux one-file builds, if you hit `cannot find python3.xx.so`, add the matching `libpython3.x.so` via `--add-binary`.
- PyInstaller may bundle GUI dependencies you have installed even if unused; trim them via `excludes` in the spec file.
- **macOS**: official docs point to **py2app** for app bundling.

## Browser fallback / integration patterns

- pywebview does **not** document a first-class “fallback to default browser” mode; the practical pattern is to keep your local web server/UI independently launchable and open its URL with Python/browser tooling if native backend checks fail.
- For a shared local-web-ui + desktop-wrapper architecture, the most robust pattern is:
  1. start/validate the local HTTP server,
  2. attempt pywebview window creation,
  3. on backend/import/runtime failure, open the same local URL in the system browser.
- If you need richer backend integration, use a **WSGI server** (for example Flask) and pass the server app directly to `create_window`.

## Validation notes

- **Linux GTK validation**: verify WebKitGTK availability and that `gir1.2-webkit2-4.1` / WebKit2 version is present.
- **Linux Qt validation**: test that QtWebEngine / QtWebChannel imports resolve on the target machine.
- **macOS validation**: confirm the Python environment can import required PyObjC WebKit/Cocoa packages before launching the wrapper.
- For packaging validation, test both **dev mode** and the **frozen binary** because backend selection/import behavior can differ.

## Minimal examples from docs

```python
import webview

window = webview.create_window('App', 'src/index.html')
webview.start(ssl=True)
```

```python
from flask import Flask
import webview

server = Flask(__name__, static_folder='.', template_folder='.')
webview.create_window('App', server)
webview.start()
```

```bash
pyinstaller main.py --add-data output:. --onefile
```
