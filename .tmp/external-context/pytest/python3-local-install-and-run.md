---
source: Context7 API + official docs
library: pytest
package: pytest
topic: python3 local install and invocation
fetched: 2026-04-16T00:00:00Z
official_docs: https://docs.pytest.org/en/stable/getting-started.html
---

## Linux local development

Recommended install pattern:

```bash
python3 -m pip install pytest
```

Create an isolated local environment first when working on a project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install pytest
```

Run pytest:

```bash
pytest
pytest -q
pytest path/to/test_file.py
pytest --version
```

Relevant notes:

- pip documents running pip through the interpreter (`python -m pip`); for Linux with Python 3, use `python3 -m pip ...` to target that interpreter explicitly.
- Python `venv` docs recommend `venv` for creating virtual environments; by default they are isolated from the base Python installation.
- Inside an activated virtual environment, package installs go into that environment.
- Activation is convenient but not strictly required; you can also invoke the venv's interpreter directly.
- pytest's getting started guide shows `pip install -U pytest`; if you want the interpreter-specific form on Linux, use `python3 -m pip install -U pytest`.
