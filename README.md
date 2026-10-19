# Avero DevDeck

**Your GitHub project command center — from the terminal.**

DevDeck is a Python CLI for browsing your GitHub repositories, checking releases, opening project pages, cloning repositories, and keeping common developer commands in one place.

## Install

Python 3.10+ and Git are required. Install the published package with:

```bash
python -m pip install avero-devdeck
devdeck --help
devdeck doctor
```

For local development from the repository root:

```bash
python -m pip install -e ".[test]"
devdeck --help
devdeck doctor
```

The package is built from the repository root using the `src/avero_devdeck` package and the `devdeck` console script entry point. Installing from PyPI requires a published release.

## GitHub login

By default, `devdeck login` uses the GitHub CLI (`gh`) to open GitHub's browser authorization flow. After authorization, DevDeck reads the token with `gh auth token` and saves it in DevDeck's user config directory with restrictive permissions. Install GitHub CLI from [cli.github.com](https://cli.github.com/) if it is not already installed.

If GitHub CLI is unavailable, you can use the optional OAuth Device Flow by creating a GitHub OAuth App, enabling **Device Flow**, and setting its client ID in `DEVDECK_GITHUB_CLIENT_ID`.

**Windows PowerShell**
```powershell
$env:DEVDECK_GITHUB_CLIENT_ID="YOUR_OAUTH_APP_CLIENT_ID"
devdeck login
```

**Linux/macOS**
```bash
export DEVDECK_GITHUB_CLIENT_ID="YOUR_OAUTH_APP_CLIENT_ID"
devdeck login
```

Without GitHub CLI or a configured OAuth Client ID, public repository browsing still works, but authenticated account/repository features are unavailable. Never put a client secret or personal access token in source code.

## Commands

```text
devdeck login                 Browser-based GitHub authorization
devdeck logout                Remove saved local authentication
devdeck whoami                Show the authenticated GitHub account
devdeck repos                 List repositories (add --limit N)
devdeck releases OWNER/REPO   List recent releases
devdeck project OWNER/REPO    Show repository details and latest release
devdeck open OWNER/REPO       Open repository in browser
devdeck clone OWNER/REPO      Clone a repository with Git
devdeck fetch                 Choose one of your repositories and clone it
devdeck update OWNER/REPO      Compare local files and upload selected changes
devdeck commands              Show the command guide
devdeck doctor                Check Python, Git, config, and auth setup
```

Examples:
```bash
devdeck project mamba-official/drake-os
devdeck releases python/cpython
devdeck repos --limit 15
devdeck clone OWNER/REPO
```

## Safety and scope

- Uses GitHub's official API over HTTPS.
- Login is opt-in; public repository/release lookups do not require login.
- Tokens are stored in the OS user config directory with restrictive permissions where supported.
- `fetch` only clones the repository you select and refuses to overwrite an existing destination.
- `update` compares exact file contents, shows the selected changes, and requires typing `YES` before upload.
- Updates never delete remote files; unreadable or uncomparable remote content stops the update before upload.


## Publish to PyPI

See [`PUBLISHING.md`](PUBLISHING.md) for the one-time PyPI Trusted Publishing setup. After the first successful release, users can install it with `py -m pip install avero-devdeck`.


## Fetch a repository, then update from any project folder

```bash
devdeck login
devdeck fetch
```

`devdeck fetch` lists your GitHub repositories in the terminal. Choose a number to clone that repository. You can also choose a destination:

```bash
devdeck fetch --path "C:\Projects\my-repo"
```

To compare any local project root with a GitHub repository and select changed files for upload:

```bash
devdeck update averolabsofficial/devdeck --path "C:\Projects\my-repo"
```

You can run the command while inside the project root and use `--path .`:

```bash
cd "C:\Projects\my-repo"
devdeck update averolabsofficial/devdeck --path .
```

The tool displays new/changed files, supports multi-selection (`1,3,5-7`, `a`, `n`), and requires typing `YES` before upload. It does not delete remote files automatically.
