## Cursor Cloud specific instructions

This is a Poetry-managed Python 3.12 project (PTR-MS scientific instrumentation library).

### Quick reference

- **Install deps:** `poetry install`
- **Run tests:** `poetry run pytest` (runs unit tests, doctests from `README.md`, and module doctests — see `tox.ini` `[pytest]` for config)
- **Run tests via tox:** `tox` (targets `py312`)
- **CLI entry point:** `poetry run ionimock` (mock instrument server)

### Notes

- No linter/formatter is configured in the repo. There are no flake8, ruff, mypy, or black configs.
- The `testdata` git submodule points to an internal Ionicon server (`git.ionicon.local`) and will not resolve from outside their network. This does not affect the test suite.
- Poetry installs to `~/.cache/pypoetry/virtualenvs/`. Use `poetry run` to execute commands in the virtualenv, or `poetry env info --path` to find it.
- Ensure `~/.local/bin` is on `PATH` so the `poetry` command is available (the update script handles this).
