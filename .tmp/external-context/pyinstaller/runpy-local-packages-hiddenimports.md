---
source: Context7 API
library: PyInstaller
package: pyinstaller
topic: runpy-local-packages-hiddenimports
fetched: 2026-04-16T00:00:00Z
official_docs: https://pyinstaller.org/en/stable/
---

- If your frozen launcher later imports or executes code indirectly (for example via `runpy`, `importlib`, plugin loading, `exec`, or modules discovered from strings), PyInstaller may miss those imports during analysis. Add those modules/packages via `hiddenimports` or `--hidden-import`, and use `--debug=imports` to see what is missing.
- Use `collect_submodules('shared')` when the whole local package may be imported dynamically or submodules are selected at runtime. This is usually the safest fix for `ModuleNotFoundError: shared...` coming from code executed after startup.
- Use explicit `hiddenimports=['shared', 'shared.foo', 'shared.bar']` when you know the exact modules needed and want a smaller bundle.
- Use `collect_data_files('shared')` for non-code assets that the package needs at runtime (templates, JSON, YAML, binaries, etc.). It is for data, not normal import resolution.
- If the runtime tool needs actual `.py` source files to exist on disk (for example because `runpy.run_path()` executes embedded scripts by filename, or a library reads package source files directly), use `collect_data_files(..., include_py_files=True)` or `datas=[('src/shared', 'shared')]` / `--add-data` to copy source files into the bundle.
- Do not rely on adding raw `.py` files in `datas` as the primary fix for package imports. Files copied as data are not automatically part of Python's import graph; they only help if your runtime code loads them by path or genuinely requires source files on disk.
- Use `pathex` / `--paths` when PyInstaller analysis cannot find your local package source tree in the first place (for example monorepo layout, launcher in a different directory, or custom `sys.path` manipulation). `pathex` helps analysis locate `shared`; it does not replace `hiddenimports` for dynamic imports.
- Prefer packaging a real package directory (`shared/__init__.py`, etc.) and making it importable during analysis, instead of shipping loose `.py` files. Then add hidden imports/submodule collection only for the parts loaded dynamically.
- Practical rule of thumb for a desktop launcher that embeds scripts and later executes them with `runpy`:
  - `runpy.run_module('shared.tool')` or imports from dynamically executed code -> package `shared` as code, then add `hiddenimports` / `collect_submodules`.
  - `runpy.run_path('/path/to/script.py')` and the script file itself must exist -> also ship that script with `datas` or `collect_data_files(..., include_py_files=True)`.
  - package reads config/templates alongside code -> add `collect_data_files`.
  - analysis cannot see your source root -> add `pathex` / `--paths`.
- In spec files, common combinations are:

```python
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('shared')
datas = collect_data_files('shared')  # add include_py_files=True only if source files must exist on disk

a = Analysis(
    ['launcher.py'],
    pathex=['src'],
    hiddenimports=hiddenimports,
    datas=datas,
    ...
)
```

- For your symptom (`ModuleNotFoundError` for local package `shared` inside the frozen app), the likely fix order is: ensure `shared` is on `pathex` so analysis can see it, then add `collect_submodules('shared')` or targeted `hiddenimports`, and only add raw `.py` files via `datas` if the launcher truly executes files by path or needs source files physically present.

Sources used:
- PyInstaller docs on hidden imports / debugging imports
- PyInstaller hook utilities: `collect_submodules`, `collect_data_files`
- PyInstaller docs on `datas`, `--add-data`, and `pathex` / `--paths`
