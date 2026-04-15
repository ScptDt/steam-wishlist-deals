---
source: Official docs (pytest)
library: pytest
package: pytest
topic: install-and-run-local-with-python-m-pytest
fetched: 2026-04-14T00:00:00Z
official_docs: https://docs.pytest.org/en/stable/getting-started.html
---

## Instalación mínima (entorno local, sin Poetry)

```bash
python -m pip install -U pytest
```

Verificar instalación:

```bash
python -m pytest --version
```

## Ejecución recomendada (robusta)

```bash
python -m pytest
```

Según la guía oficial de pytest, invocar con `python -m pytest` es casi equivalente a `pytest`, pero asegura usar el intérprete activo y añade el directorio actual a `sys.path`.

## Ejemplos de uso directo

```bash
python -m pytest -q
python -m pytest tests/
python -m pytest tests/test_mod.py::TestClass::test_method
```

## Notas breves de compatibilidad

- Si aparece `pytest: command not found`, normalmente falta el script en `PATH` o pytest no está instalado en ese entorno.
- `python -m pip ...` y `python -m pytest ...` evitan conflictos cuando hay múltiples instalaciones de Python.
- En Windows, para expresiones con `-k`, usar comillas dobles (`"..."`) en lugar de comillas simples.
- Recomendado usar entorno virtual local (`venv`) para aislar dependencias del sistema.

Fuentes usadas:
- https://docs.pytest.org/en/stable/getting-started.html
- https://docs.pytest.org/en/stable/how-to/usage.html#calling-pytest-through-python-m-pytest
