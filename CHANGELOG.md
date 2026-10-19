# Changelog

## 0.1.4 — 2026-10-19
- Make wheel package inclusion explicit and strip the `src` prefix so the installed `devdeck` entry point can import `avero_devdeck`.
- Add a clean virtual environment wheel-install smoke test for `devdeck --help`.

## 0.1.3 — 2026-10-19
- Added a working root-level Python package and `devdeck` entry point.
- Added repository fetch and interactive selected-file update workflows.
- Added fail-closed remote comparison and core workflow tests.

## 0.1.2 — 2026-10-19
- Added interactive `devdeck fetch` to list account repositories and clone a selected repository.
- Added `devdeck update OWNER/REPO --path PATH` as a user-friendly selected-file update command.


## 0.1.1 — 2026-10-19
- Added interactive `devdeck sync` to compare local files and select multiple changes before uploading to GitHub.
- Improved duplicate-file workflow; unchanged files are not uploaded.


## 0.1.0 — 2026-10-19
- Initial CLI release.
- GitHub Device Flow browser authorization.
- Repository listing, project overview, releases, open, clone, doctor, and command guide.
