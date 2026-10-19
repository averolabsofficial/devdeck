from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any

import requests
from platformdirs import user_config_dir

from . import __version__

API = "https://api.github.com"
DEVICE_URL = "https://github.com/login/device"
TOKEN_URL = "https://github.com/login/oauth/access_token"
APP_NAME = "avero-devdeck"


def config_dir() -> Path:
    path = Path(user_config_dir(APP_NAME, "AveroLabs"))
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(stat.S_IRWXU)
    except OSError:
        pass
    return path


def token_path() -> Path:
    return config_dir() / "auth.json"


def load_token() -> str | None:
    try:
        data = json.loads(token_path().read_text(encoding="utf-8"))
        token = data.get("access_token")
        return token if isinstance(token, str) and token else None
    except (OSError, ValueError, AttributeError):
        return None


def save_token(token: str) -> None:
    path = token_path()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    with os.fdopen(descriptor, "w", encoding="utf-8") as token_file:
        json.dump({"access_token": token}, token_file, indent=2)


def clear_token() -> bool:
    try:
        token_path().unlink()
        return True
    except FileNotFoundError:
        return False


def github_request(method: str, endpoint: str, **kwargs: Any) -> requests.Response:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"Avero-DevDeck/{__version__}",
    }
    token = load_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    custom_headers = kwargs.pop("headers", {})
    headers.update(custom_headers)
    response = requests.request(
        method, f"{API}{endpoint}", headers=headers, timeout=20, **kwargs
    )
    if response.status_code == 401:
        raise RuntimeError("GitHub rejected the saved token. Run `devdeck logout`, then `devdeck login`.")
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise RuntimeError("GitHub API rate limit reached. Try again later or run `devdeck login`.")
    response.raise_for_status()
    return response


def _login_with_github_cli(gh_path: str) -> str:
    # Let gh own the interactive browser flow and its terminal prompts.
    login_result = subprocess.run(
        [gh_path, "auth", "login", "--hostname", "github.com", "--web", "--git-protocol", "https"],
        check=False,
    )
    if login_result.returncode != 0:
        raise RuntimeError(
            "GitHub browser authorization did not complete. Run `devdeck login` and finish the `gh` prompt."
        )

    # Capture the token only in memory. Never include command output in errors or logs.
    token_result = subprocess.run(
        [gh_path, "auth", "token", "--hostname", "github.com"],
        capture_output=True,
        text=True,
        check=False,
    )
    token = token_result.stdout.strip()
    if token_result.returncode != 0 or not token:
        raise RuntimeError(
            "GitHub CLI did not return an authenticated token. Complete browser authorization, then retry."
        )
    save_token(token)
    return token


def login(client_id: str = "") -> str:
    client_id = client_id.strip()
    gh_path = shutil.which("gh")
    if gh_path:
        return _login_with_github_cli(gh_path)

    if client_id and client_id != "YOUR_OAUTH_APP_CLIENT_ID":
        return _login_with_device_flow(client_id)

    raise RuntimeError(
        "GitHub CLI (`gh`) is required for browser login. Install it from https://cli.github.com/ "
        "and run `devdeck login` again. Alternatively, configure DEVDECK_GITHUB_CLIENT_ID "
        "to use GitHub OAuth Device Flow."
    )


def _login_with_device_flow(client_id: str) -> str:
    """Optional OAuth Device Flow for users who configured their own GitHub OAuth App."""
    if not client_id or client_id == "YOUR_OAUTH_APP_CLIENT_ID":
        raise RuntimeError(
            "A configured DEVDECK_GITHUB_CLIENT_ID is required for OAuth Device Flow."
        )
    response = requests.post(
        "https://github.com/login/device/code",
        data={"client_id": client_id, "scope": "read:user repo"},
        headers={"Accept": "application/json", "User-Agent": f"Avero-DevDeck/{__version__}"},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    device_code = data.get("device_code")
    user_code = data.get("user_code")
    verify_url = data.get("verification_uri", DEVICE_URL)
    interval = max(int(data.get("interval", 5)), 1)
    expires_in = int(data.get("expires_in", 900))
    if not device_code or not user_code:
        raise RuntimeError(f"GitHub did not return a device code: {data}")
    print(f"\nOpen: {verify_url}\nEnter this one-time code: {user_code}\n")
    webbrowser.open(verify_url)
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        token_response = requests.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json", "User-Agent": f"Avero-DevDeck/{__version__}"},
            timeout=20,
        )
        token_response.raise_for_status()
        result = token_response.json()
        if result.get("access_token"):
            save_token(result["access_token"])
            return result["access_token"]
        error = result.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error in ("expired_token", "access_denied", "incorrect_device_code", "unsupported_grant_type"):
            raise RuntimeError(f"GitHub login did not complete: {error}")
        if error:
            raise RuntimeError(f"GitHub login failed: {error}")
    raise RuntimeError("GitHub device code expired. Run `devdeck login` again.")
