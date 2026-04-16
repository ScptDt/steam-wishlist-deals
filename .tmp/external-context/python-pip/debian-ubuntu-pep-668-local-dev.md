---
source: Context7 API + official docs
library: Python packaging / pip / pipx
package: python-pip
topic: debian-ubuntu-pep-668-local-development
fetched: 2026-04-16T00:00:00Z
official_docs:
  - https://packaging.python.org/en/latest/specifications/externally-managed-environments/
  - https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/
  - https://packaging.python.org/en/latest/guides/installing-stand-alone-command-line-tools/
  - https://pip.pypa.io/en/stable/cli/pip_install/
---

# Debian/Ubuntu + PEP 668: safe local development installs

- Debian/Ubuntu may mark the system Python as `EXTERNALLY-MANAGED`. In that case, `pip` should refuse to install into the base interpreter outside a virtual environment and point you to safer options.
- The recommended default for project dependencies is a per-repo virtual environment created with `python3 -m venv .venv`.
- Inside that virtual environment, install repo dependencies with `python -m pip install -r requirements-desktop.txt`.
- Use `python -m pip ...` instead of bare `pip` so you target the exact interpreter for the repo environment.
- `pipx` is recommended for standalone Python CLI tools, because it installs each app in its own isolated virtual environment and exposes its commands on `PATH`.
- `pipx` is **not** the normal way to install a repo's library/app dependencies from `requirements-desktop.txt`; use a project virtualenv for that.
- `--break-system-packages` exists only as an override to allow pip to modify an `EXTERNALLY-MANAGED` Python installation. It is intentionally named as risky and should not be the default for local development.
- Avoid `--break-system-packages` because mixing PyPI installs into distro-managed Python can shadow or conflict with packages owned by `apt`, and can break OS-provided Python tools.
- The externally-managed spec also says Python package managers should avoid deleting files outside their target install scheme, but that still does **not** make modifying the system interpreter a good repo setup strategy.

## Repo-ready commands

```bash
sudo apt install python3-full python3-venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-desktop.txt
```

## When to use pipx

- Use `pipx install <tool>` for developer tools you want globally available but isolated, such as linters, formatters, or packaging CLIs.
- If Debian/Ubuntu packages `pipx`, prefer installing pipx via `apt` rather than bootstrapping it with a global pip install on the system interpreter.

## Practical guidance for this repo

- For building the desktop app, create/activate `.venv` in the repo and install `requirements-desktop.txt` there.
- If build prerequisites are OS libraries, install those with `apt`; install Python dependencies with pip **inside `.venv`**.
- Reach for `--break-system-packages` only in exceptional disposable environments where you knowingly accept modifying the base interpreter; not for normal workstation repo setup.

## Source highlights

- PyPA virtualenv guide: recommends virtual environments for third-party packages and shows `python3 -m venv .venv` + `python3 -m pip install -r requirements.txt`.
- Externally Managed Environments spec / PEP 668: says tools like pip should refuse base-environment installs when `EXTERNALLY-MANAGED` is present and guide users to virtualenvs; also suggests pipx for Python applications.
- pip docs: `pip install --break-system-packages` means "Allow pip to modify an EXTERNALLY-MANAGED Python installation".
- pipx docs / PyPA guide: pipx installs standalone applications in isolated environments and is meant for apps/tools, not normal per-project dependency installs.
