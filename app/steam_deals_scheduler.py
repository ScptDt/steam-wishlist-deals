from __future__ import annotations

from datetime import datetime
import time


def parse_schedule_hours(argv: list[str]) -> float | None:
    for index, arg in enumerate(argv):
        if arg != "--schedule" or index + 1 >= len(argv):
            continue
        try:
            return float(argv[index + 1])
        except ValueError:
            return None
    return None


def run_scheduled(
    main_fn,
    *,
    argv: list[str],
    now_fn=datetime.now,
    fromtimestamp_fn=datetime.fromtimestamp,
    sleep_fn=time.sleep,
    emit=print,
    style_bold=lambda text: text,
    style_dim=lambda text: text,
    style_warn=lambda text: text,
    style_err=lambda text: text,
) -> None:
    """Run main() in a loop if --schedule is set."""
    schedule_hours = parse_schedule_hours(argv)
    if not schedule_hours:
        main_fn()
        return

    emit(style_bold(f"=== Modo programado: cada {schedule_hours:.1f} horas ==="))
    emit(f"  {style_dim('Ctrl+C para detener')}\n")
    run_count = 0
    while True:
        run_count += 1
        emit(f"\n{'═' * 42}")
        emit(f"  Run #{run_count} — {now_fn().strftime('%Y-%m-%d %H:%M')}")
        emit(f"{'═' * 42}\n")
        try:
            main_fn()
        except KeyboardInterrupt:
            emit(f"\n  {style_warn('Scheduler detenido.')}")
            break
        except Exception as exc:
            emit(f"\n  {style_err(f'Error en run #{run_count}: {exc}')}")

        wait_secs = schedule_hours * 3600
        next_time = now_fn().timestamp() + wait_secs
        next_str = fromtimestamp_fn(next_time).strftime('%H:%M')
        emit(f"\n  {style_dim(f'Próximo run a las {next_str} (en {schedule_hours:.1f}h). Ctrl+C para salir.')}")
        try:
            sleep_fn(wait_secs)
        except KeyboardInterrupt:
            emit(f"\n  {style_warn('Scheduler detenido.')}")
            break
