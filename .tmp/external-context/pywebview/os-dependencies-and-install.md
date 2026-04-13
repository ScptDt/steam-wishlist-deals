---
source: Context7 API + official docs
library: pywebview
package: pywebview
topic: os-dependencies-and-install
fetched: 2026-04-12T00:00:00Z
official_docs: https://pywebview.flowrl.com/guide/installation
---

## pywebview native backends by OS

- **Windows**: WinForms host with renderer priority **Edge Chromium (WebView2)**, fallback **MSHTML (deprecated)**.
- **macOS**: Cocoa + **WKWebView** via PyObjC (or Qt backend if selected).
- **Linux**: choose **Qt** or **GTK (WebKit2)** backend.

## Required dependencies and runtime notes

### Windows
- Python dependency: `pythonnet` (requires **.NET > 4.0** per pywebview docs; web engine table also calls out **>.NET 4.6.2** for EdgeChromium path).
- For modern Chromium rendering: install **Microsoft Edge WebView2 Runtime** on target systems.
- Optional backend: `cefpython` for CEF renderer.

### macOS
- Backend: PyObjC + Cocoa/WebKit.
- For non-system Python installs, install:
  - `pyobjc-core`
  - `pyobjc-framework-Cocoa`
  - `pyobjc-framework-Quartz`
  - `pyobjc-framework-WebKit`
  - `pyobjc-framework-security`
- Qt backend is also supported on macOS.

### Linux
- **Qt path**: `pip install pywebview[qt]` usually installs Python-side deps; distro packages may still be required.
- **GTK path**: requires PyGObject + WebKit2.
- Minimum WebKit2 version requirement: **2.22+**.

Debian/Ubuntu commands from pywebview docs:

```bash
# Qt WebEngine + Qt WebChannel path (preferred)
sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtwebchannel libqt5webkit5-dev

# GTK path
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

## Recommended install commands (README-ready)

```bash
# Base
pip install pywebview

# Linux explicit backend selection
pip install "pywebview[gtk]"
pip install "pywebview[qt]"

# Other optional extras
pip install "pywebview[cef]"   # Windows only
pip install "pywebview[ssl]"   # adds cryptography for local HTTPS server
```

Renderer forcing (useful for CI/debugging):

```bash
export PYWEBVIEW_GUI=qt
export PYWEBVIEW_GUI=cef
```

or in code:

```python
import webview
webview.start(gui='qt')
```

## Sources

- https://pywebview.flowrl.com/guide/installation
- https://pywebview.flowrl.com/guide/web_engine
- https://github.com/r0x0r/pywebview/blob/master/docs/guide/installation.md
- https://github.com/r0x0r/pywebview/blob/master/docs/guide/web_engine.md
