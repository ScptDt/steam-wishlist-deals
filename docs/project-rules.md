# Reglas del proyecto

Guía mínima para darle rumbo al repo sin convertirlo en burocracia.

## Fuente de verdad

- `PENDIENTES.md` es la fuente única de verdad para backlog, prioridades, deuda técnica, estado actual y siguientes pasos.
- `BITACORA.md` concentra la bitácora operativa detallada, evidencia cronológica y workarounds históricos; no reemplaza a `PENDIENTES.md`.
- `README.md` documenta uso real, entrypoints y flujos para usuarios o contribuidores.
- `docs/runbooks/README.md` es el índice de checklists manuales y validaciones operativas reproducibles.

## Superficies del producto

- **Web UI**: experiencia principal para la mayoría de usuarios.
- **Desktop**: reutiliza la misma UI web con `pywebview`; no debe divergir sin una razón fuerte.
- **CLI**: superficie operativa para automatización, scripting, warm-cache y flags avanzados.

## Reglas de arquitectura

- Preferir stdlib y helpers pequeños antes de agregar dependencias o capas nuevas.
- No duplicar lógica entre `steam_deals_web.py`, `steam_tools_desktop.py` y `steam_deals_generator.py` si puede extraerse a helpers compartidos.
- Mantener compatibilidad entre web y desktop en cualquier cambio visible para usuario.
- Hacer cambios pequeños, validables y fáciles de revertir.

## Higiene del repo

- Se versiona: código fuente, tests, docs permanentes, runbooks y configuración útil del proyecto.
- No se versiona: `.tmp/`, `.pytest_cache/`, `logs/` y reportes generados `Steam Deals*.md/.html/.json/.csv`.
- El caché local en `.cache/steam_deals` sí se conserva localmente; no debe borrarse por limpieza rutinaria si ayuda a corridas grandes.
- Si un archivo generado merece conservarse como ejemplo, debe moverse a una ubicación intencional (`docs/` o `tests/fixtures/`) con nombre estable y contexto claro.

## Cómo meter trabajo nuevo sin perder rumbo

- Antes de implementar, ubica el cambio en una de estas categorías: producto, UX, infraestructura o documentación.
- Si el cambio afecta comportamiento visible, valida al menos el slice tocado.
- Si el cambio altera roadmap, deuda o decisiones operativas, refleja el contexto en `PENDIENTES.md`.
- Si el cambio deja evidencia cronológica detallada, validaciones largas o workarounds históricos, regístralo en `BITACORA.md` y deja en `PENDIENTES.md` solo el resumen que afecte estado/prioridad.
- Si el cambio modifica uso, setup o flujo de trabajo, actualiza `README.md` o el runbook correspondiente.

## Regla práctica de decisión

Cuando haya duda, priorizar esto:

1. Mantener usable la Web UI.
2. No romper desktop si reutiliza el mismo flujo.
3. No degradar el tiempo real de corridas grandes innecesariamente.
4. Reducir ruido en git y dejar evidencia clara en docs permanentes.
