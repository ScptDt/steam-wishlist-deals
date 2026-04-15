---
source: PyPA Packaging Guide + Python docs + pip docs
library: Python packaging / pip / venv
package: python
topic: externally-managed-environment pytest in project venv
fetched: 2026-04-15T00:00:00Z
official_docs: https://packaging.python.org/en/latest/specifications/externally-managed-environments/
---

`externally-managed-environment` is raised on Debian/Ubuntu-style system Python installs because the interpreter is marked with `EXTERNALLY-MANAGED` (PEP 668). pip is supposed to avoid modifying the default system environment outside a virtual environment, because doing so can conflict with or break packages managed by the OS.

Recommended fixes from current docs:

- **If you want a distro-managed tool/package system-wide:** use the OS package manager, e.g. Debian-style `apt install python3-pytest` (the spec explicitly recommends `apt install python3-xyz` for system-wide installs).
- **If you want project-local validation without touching system Python:** create a **virtual environment** and install `pytest` there. This is the preferred safe option for repo-local testing.

Safest practical commands for a repo:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip pytest
pytest
```

You do **not** need to run pip as root inside the venv. Avoid `--break-system-packages` unless you intentionally accept the risk of modifying an externally managed system Python.

Relevant docs used:

- PyPA Externally Managed Environments: system interpreters may block pip installs outside venvs and should guide users to venvs.
- Python `venv` docs: virtual environments are isolated from the base interpreter and pip installs into the venv by default.
- PyPA virtual environment guide: recommends creating `.venv` in the project directory and installing packages there.
