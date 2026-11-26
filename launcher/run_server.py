"""Starts the GM interface for the Windows launcher (``Avvia_GM_Interface.bat``).

Unlike ``python -m ak_engine.webapp`` this runs without Flask's debug mode (no auto-reloader, no stack traces in the
browser) and writes everything the server prints to ``~/ak_games/logs/server.log``, so a tester can send that file
along with a bug report. Usage: ``python run_server.py [port]``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from ak_engine.webapp.app import DEFAULT_GAMES_ROOT, create_app

HOST = "127.0.0.1"


def main(argv: list[str]) -> int:
    port = int(argv[1]) if len(argv) > 1 else 5055
    log_dir = Path(DEFAULT_GAMES_ROOT) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "server.log"
    logging.basicConfig(
        filename=log_path, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", encoding="utf-8"
    )
    # Werkzeug logs requests through the logging module; the console keeps a short note too.
    print(f"GM Interface: http://{HOST}:{port}/   (log: {log_path})", flush=True)
    logging.getLogger(__name__).info("starting on %s:%s", HOST, port)
    try:
        create_app().run(host=HOST, port=port, debug=False)
    except OSError as error:
        logging.getLogger(__name__).error("cannot listen on port %s: %s", port, error)
        print(f"ERRORE: la porta {port} non e' disponibile ({error}).", flush=True)
        return 1
    except Exception:
        logging.getLogger(__name__).exception("the server stopped")
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
