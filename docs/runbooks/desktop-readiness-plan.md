# Runbook Desktop Readiness Plan

Helper seguro para imprimir planes reproducibles de validación desktop por plataforma y, si se pide explícitamente, recolectar checks offline pequeños.

## Objetivo

Usar `desktop_readiness_plan.py` cuando necesites preparar un cierre Linux/Windows/macOS o revisar qué comandos mínimos aplican, sin lanzar builds, smokes manuales, red real ni artefactos generados accidentalmente.

Usar `desktop_readiness_collect.py` cuando quieras convertir ese plan en evidencia compacta de checks offline. Por defecto también es dry-run: solo lista qué checks ejecutaría.

## Uso

```bash
.venv/bin/python desktop_readiness_plan.py --platform all
.venv/bin/python desktop_readiness_plan.py --platform linux
.venv/bin/python desktop_readiness_plan.py --platform windows --format json
.venv/bin/python desktop_readiness_plan.py --platform macos
.venv/bin/python desktop_readiness_collect.py --platform linux
.venv/bin/python desktop_readiness_collect.py --platform linux --execute-safe-checks
.venv/bin/python desktop_readiness_collect.py --platform linux --execute-safe-checks --format json
```

El helper solo imprime:
- prerrequisitos y blockers por plataforma;
- guardrails de release hygiene;
- comandos de checks locales;
- pasos manuales/build marcados como tales;
- evidencia esperada para `BITACORA.md`.

El collector solo puede ejecutar los pasos seguros de `checks` en la plataforma actual:
- tests desktop/readiness sin red;
- Desktop Doctor source/frozen.

## Guardrails

- No ejecuta comandos, builds, smokes ni red por sí mismo.
- `desktop_readiness_collect.py` requiere `--execute-safe-checks` para ejecutar cualquier check.
- La ejecución segura se rechaza si apuntas a otra plataforma; usa dry-run para preparar Windows/macOS desde Linux.
- No cierra macOS: `desktop-macos.md` sigue requiriendo host macOS nativo, `.app`, apertura local, smoke pequeño y cierre limpio.
- No cierra Linux/Windows por sí solo: solo prepara el plan; la evidencia real vive en los runbooks específicos.
- No usar `BG00G`, `--no-cache`, cold-cache largo ni builds salvo objetivo explícito/aprobado.
- No versionar `output/`, `logs/`, `.cache/`, `build/`, `dist/`, reportes generados ni `*.spec`.

## Flujo recomendado

1. Genera el plan para la plataforma objetivo.
2. Revisa blockers y confirma que tienes host/sesión adecuados.
3. Ejecuta primero los checks locales del plan, o usa `desktop_readiness_collect.py --execute-safe-checks` para capturar esos checks offline en la plataforma actual.
4. Solo con aprobación/objetivo explícito, ejecuta build o smoke manual desde el runbook específico:
   - Linux: `docs/runbooks/desktop-linux.md`
   - Windows: `docs/runbooks/desktop-windows.md`
   - macOS: `docs/runbooks/desktop-macos.md`
5. Registra evidencia compacta en `BITACORA.md` y deja `PENDIENTES.md` solo para cambios de estado/prioridad/bloqueo.

## Validación del helper

```bash
.venv/bin/python -m py_compile desktop_readiness_plan.py tests/test_desktop_readiness_plan.py
.venv/bin/python -m unittest tests.test_desktop_readiness_plan
.venv/bin/python -m py_compile desktop_readiness_collect.py tests/test_desktop_readiness_collect.py
.venv/bin/python -m unittest tests.test_desktop_readiness_collect
git diff --check
```
