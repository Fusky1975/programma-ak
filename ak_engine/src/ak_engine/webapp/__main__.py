"""``python -m ak_engine.webapp`` -- runs the GM interface's local dev server."""

from __future__ import annotations

from ak_engine.webapp.app import create_app

if __name__ == "__main__":
    create_app().run(debug=True)
