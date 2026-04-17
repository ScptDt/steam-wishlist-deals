---
source: Official docs
library: pytest + Python venv
package: pytest
topic: use project .venv interpreter for pytest execution on Debian/Linux
fetched: 2026-04-17T00:00:00Z
official_docs: https://docs.pytest.org/en/stable/how-to/usage.html ; https://docs.python.org/3/library/venv.html
---

Relevant current guidance:

- Pytest documents `python -m pytest [...]` as valid, and notes this uses the Python interpreter you invoke.
- Python `venv` docs say a virtual environment contains its own Python interpreter and installed scripts/packages, and you do not need to activate it if you run that interpreter directly.
- Therefore, if `python3 -m pytest` fails on Debian/Linux because system Python does not have `pytest`, the practical fix is to run the project's virtualenv interpreter instead of system `python3`.

Recommended commands:

```bash
./.venv/bin/python -m pytest
./.venv/bin/python -m pytest -q
./.venv/bin/pytest
```

If pytest is missing even inside the venv:

```bash
./.venv/bin/python -m pip install pytest
./.venv/bin/python -m pytest
```
