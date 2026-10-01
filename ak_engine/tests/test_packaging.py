"""Guards the webapp's non-editable-install packaging (pyproject.toml).

A real, user-caught bug: a non-editable ``pip install .`` (the only kind
a standalone end-user launcher script can reasonably do -- it has no
source checkout to point ``-e`` back at) silently excluded every
``webapp/templates/*.html``/``webapp/static/*.css`` file, since
setuptools only packages ``.py`` files by default with no
``[tool.setuptools.package-data]`` declaration. Invisible throughout
development because every workflow here (pytest, the dev server, every
manual browser check) ran against the source tree directly or via an
editable install, both of which just point back at those same files on
disk. Caught only by actually building a non-editable install and
running the server from it -- confirmed with a real ``TemplateNotFound:
games_list.html`` error -- while preparing a one-click Windows launcher
for the user.
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - this project requires Python >= 3.11 (pyproject.toml)
    import tomli as tomllib  # type: ignore[no-redef]

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _load_pyproject() -> dict:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def test_webapp_templates_and_static_are_declared_as_package_data():
    package_data = _load_pyproject()["tool"]["setuptools"]["package-data"]

    assert "ak_engine.webapp" in package_data
    patterns = package_data["ak_engine.webapp"]
    assert "templates/*.html" in patterns
    assert "static/*.css" in patterns


def test_package_data_patterns_actually_match_every_real_template_and_static_file():
    # Not just that the glob strings look right -- that they actually
    # cover every real file this package ships today, so a new template
    # added under a different extension wouldn't silently fall outside
    # both curated patterns.
    webapp_src = PYPROJECT_PATH.parent / "src" / "ak_engine" / "webapp"
    real_template_files = {p.name for p in (webapp_src / "templates").glob("*")}
    real_static_files = {p.name for p in (webapp_src / "static").glob("*")}

    assert real_template_files, "expected at least one real template file to guard"
    assert real_static_files, "expected at least one real static file to guard"
    assert all(name.endswith(".html") for name in real_template_files)
    assert all(name.endswith(".css") for name in real_static_files)
