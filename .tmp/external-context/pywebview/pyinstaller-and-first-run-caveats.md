---
source: Context7 API + official docs
library: pywebview + PyInstaller + Apple Support
package: pywebview
topic: pyinstaller-and-first-run-caveats
fetched: 2026-04-12T00:00:00Z
official_docs: https://pywebview.flowrl.com/guide/freezing
---

## PyInstaller caveats for pywebview apps

### General packaging

- Basic pattern:

```bash
pyinstaller main.py --add-data index.html:.
```

- Include all frontend build artifacts (HTML/CSS/JS) using `--add-data`.
- If using Vite, avoid default output dir `dist` to prevent conflicts with PyInstaller's `dist` usage.

### pywebview-specific bundle bloat caveat (Windows/Linux)

- pywebview docs note that PyInstaller may collect **all detected GUI dependencies** even if unused (e.g., PyQt bundled while using EdgeChromium).
- Mitigation: define `excludes` in `.spec` to remove unused backends.

### Linux caveat

- If you hit `cannot find python3.xx.so` in onefile builds, add the Python shared library explicitly:

```bash
pyinstaller main.py --add-data index.html:. --add-binary /usr/lib/x86_64-linux-gnu/libpython3.x.so:. --onefile
```

### macOS signing / Gatekeeper / first-open behavior

- Gatekeeper checks downloaded apps for developer identity and notarization; unsigned or unnotarized apps trigger warnings and may require manual **Open Anyway** override.
- For smooth first-run UX on distributed builds, use proper Apple code signing + notarization.
- PyInstaller supports macOS signing options:

```bash
pyinstaller --windowed \
  --osx-bundle-identifier=com.example.app \
  --codesign-identity="Developer ID Application: Your Name" \
  --osx-entitlements-file=entitlements.plist \
  myscript.py
```

- PyInstaller automatically (re)signs binaries; with `--codesign-identity` it enables hardened runtime.
- Use a valid Apple-issued signing identity (self-signed certs can fail library validation at runtime).

### Optional user workaround for quarantined/untrusted app

- Users can open once via **System Settings → Privacy & Security → Open Anyway** after initial block (Apple guidance).
- Document this as fallback only; preferred distribution remains signed + notarized app.

## Sources

- https://pywebview.flowrl.com/guide/freezing
- https://github.com/r0x0r/pywebview/blob/master/docs/guide/freezing.md
- https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing
- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
- https://support.apple.com/en-us/102445
