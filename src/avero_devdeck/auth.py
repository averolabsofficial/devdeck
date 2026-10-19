from __future__ import annotations

import json
import os
import stat
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
    path.write_text(json.dumps({"access_token": token}, indent=2), encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


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


def login(client_id: str) -> str:
    if not client_id or client_id == "YOUR_OAUTH_APP_CLIENT_ID":
        raise RuntimeError(
            "Set DEVDECK_GITHUB_CLIENT_ID to the Client ID of your GitHub OAuth App. "
            "Enable Device Flow in that app's settings."
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
