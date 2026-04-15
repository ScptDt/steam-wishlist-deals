---
source: Context7 API
library: Pytest
package: pytest
topic: install and run with Python 3
fetched: 2026-04-15T00:00:00Z
official_docs: https://docs.pytest.org/en/stable/getting-started.html
---

## Instalación básica con pip

```bash
python3 -m pip install -U pytest
```

## Instalación dentro de un venv

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pytest
```

## Ejecución recomendada

```bash
python -m pytest
```

También puedes ejecutar un archivo concreto:

```bash
python -m pytest tests/test_example.py
```

## Nota práctica

La documentación de pytest recomienda usar entornos virtuales (`venv` + `pip`) para aislar dependencias del Python del sistema.
