# Avero DevDeck

**Your GitHub project command center — from the terminal.**

DevDeck is a Python CLI for browsing your GitHub repositories, checking releases, opening project pages, cloning repositories, and keeping common developer commands in one place.

## Install from GitHub (after uploading this folder)

Python 3.10+ and Git are required. After you create your GitHub repository and push these files, install directly from it (replace `YOUR_GITHUB_USERNAME` with your username):

```powershell
py -m pip install "git+https://github.com/YOUR_GITHUB_USERNAME/avero-devdeck.git"
devdeck --help
devdeck doctor
```

For local development from the extracted project folder:

```powershell
py -m pip install -e .
devdeck --help
devdeck doctor
```

This Git-based install does not depend on the package being published to PyPI or on the PyPI package name being available. `pip install avero-devdeck` will only work after publication to PyPI.

## GitHub login

DevDeck uses GitHub's OAuth **Device Flow**: it opens the official GitHub device authorization page in your browser and asks you to enter a short one-time code. It does not ask for your GitHub password and stores the returned token in your user config directory.

For OAuth login, create a GitHub OAuth App and enable **Device Flow** in its settings. Set its client ID:

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

Without a client ID, public repository browsing still works, but authenticated account/repository features are unavailable. Never put a client secret or personal access token in source code.

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
- `clone` invokes Git only for the repository you name.
- This first version does not create, delete, or modify GitHub repositories/releases.


## Publish to PyPI

See [`PUBLISHING.md`](PUBLISHING.md) for the one-time PyPI Trusted Publishing setup. After the first successful release, users can install it with `py -m pip install avero-devdeck`.
