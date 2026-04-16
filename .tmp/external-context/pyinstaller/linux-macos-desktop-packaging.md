---
source: Context7 API
library: PyInstaller
package: pyinstaller
topic: linux-macos-desktop-packaging
fetched: 2026-04-16T00:00:00Z
official_docs: https://pyinstaller.org/en/stable/
---

- Prefer `--onedir` for desktop wrapper apps during development and for most macOS GUI distribution; `--onefile` is convenient but slower to start and adds extraction/runtime complexity.
- On macOS, `--windowed` also creates `dist/<app>.app`; if needed, define a `BUNDLE(...)` target in the `.spec` file to control bundle name, icon, bundle identifier, and `Info.plist` values.
- Avoid `--onefile --windowed` for macOS app bundles unless you specifically need it: PyInstaller documents it as inefficient because contents are unpacked on every launch, and sandboxed signed/notarized apps can fail.
- For drag-and-drop / “Open with…” behavior on macOS, enable `argv_emulation=True` in `EXE(...)`; add `CFBundleDocumentTypes` and related `Info.plist` entries in `BUNDLE(...)` if your wrapper app should accept files or custom URL schemes.
- Bundle non-Python assets explicitly with `datas=` / `--add-data` and native libraries with `binaries=` / `--add-binary`; this is especially important for desktop wrappers shipping icons, templates, embedded web assets, helper executables, or `.dylib` / `.so` dependencies.
- PyInstaller may miss libraries loaded dynamically (for example via absolute-path `ctypes.CDLL(...)`); for these cases, add them manually in the spec file or with `--add-binary`.
- Linux packaging depends on host toolchain utilities: PyInstaller requires `ldd`, `objdump`, and `objcopy` to analyze and build binaries correctly.
- On Linux, watch shared-library symlink behavior inside bundled apps; PyInstaller provides Linux-specific `bindepend_symlink_suppression` hook settings when bundled `.so` layouts or top-level symlinks cause problems.
- Build on the oldest target OS / distro you intend to support when possible; frozen binaries are not generally portable across newer-to-older glibc environments, so validate on representative Linux targets.
- Validate both generated forms after each packaging change: run the raw binary from `dist/` and, on macOS, launch the `.app` bundle directly to catch bundle-only issues.
- For validation, check: app startup without a Python installation, asset loading paths, native library resolution, working directory assumptions, file-open integration, and clean first-run behavior.
- For macOS validation, also verify bundle metadata (`Info.plist`), icon presence, launch behavior under Finder, and any signing/notarization workflow you plan to use.

References pulled from PyInstaller stable docs sections on usage, spec files, feature notes, hooks, man pages, and requirements.
