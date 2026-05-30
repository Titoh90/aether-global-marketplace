# IMPERIO_ROOT — Sistema Canónico

[![Tests](https://github.com/Titoh90/aether-global-marketplace/actions/workflows/tests.yml/badge.svg)](https://github.com/Titoh90/aether-global-marketplace/actions/workflows/tests.yml)

## Establecido: 2026-05-13

Este directorio es el único source of truth del Imperio.

| Directorio | Contenido |
|-----------|-----------|
| runtime/ | startup, stop, status scripts |
| automation/ | watchdog.py |
| interfaces/ | configs Telegram plugin |
| configs/ | .env (sin secretos en logs) |
| dashboards/ | dashboard.py + HTML |
| archive/ | sistemas legacy (no borrar) |
| models/ | symlinks a modelos (no blobs) |
| logs/ | logs centralizados |
| data/ | cache y output de ejecución |

## Arranque del sistema

```bash
bash /Volumes/OPENCLAW_STORAG\ 1/IMPERIO_ROOT/runtime/imperio_start.sh
```

## Regla absoluta

SI UN SISTEMA NO ESTÁ EN IMPERIO_ROOT → NO EXISTE.
