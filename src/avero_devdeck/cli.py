from __future__ import annotations

import argparse
import base64
import fnmatch
import os
import shutil
import subprocess
from pathlib import Path
import sys
import webbrowser
from urllib.parse import quote

import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from . import __version__
from .auth import clear_token, github_request, load_token, login as do_login
from .sync import is_content_changed, parse_selection

console = Console()
API = "https://api.github.com"


def repo_slug(value: str) -> tuple[str, str]:
    parts = value.strip().strip("/").removesuffix(".git").split("/")
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError("Use OWNER/REPO format, e.g. python/cpython")
    return parts[0], parts[1]


def api_json(endpoint: str, params: dict | None = None):
    response = github_request("GET", endpoint, params=params)
    return response.json()


def _list_user_repositories(limit: int = 0) -> list[dict]:
    """List all owned repositories, following GitHub pagination unless capped."""
    repos = []
    page = 1
    while True:
        remaining = max(limit - len(repos), 0) if limit > 0 else 100
        per_page = min(remaining, 100) if limit > 0 else 100
        page_repos = api_json("/user/repos", {
            "sort": "updated", "per_page": per_page, "type": "owner", "page": page,
        })
        repos.extend(page_repos)
        if len(page_repos) < per_page or (limit > 0 and len(repos) >= limit):
            break
        page += 1
    return repos[:limit] if limit > 0 else repos


def cmd_login(_args):
    client_id = os.environ.get("DEVDECK_GITHUB_CLIENT_ID", "").strip()
    do_login(client_id)
    user = api_json("/user")
    console.print(f"[green]Logged in as[/green] [bold]@{user.get('login', 'unknown')}[/bold]")


def cmd_logout(_args):
    if clear_token():
        console.print("[green]Saved GitHub authentication removed.[/green]")
    else:
        console.print("No saved login was found.")


def cmd_whoami(_args):
    if not load_token():
        console.print("[yellow]Not logged in. Run `devdeck login`.[/yellow]")
        return
    user = api_json("/user")
    console.print(Panel(
        f"[bold]@{user.get('login')}[/bold]\n{user.get('name') or 'Name not set'}\n"
        f"{user.get('html_url', '')}\nPublic repos: {user.get('public_repos', 0)}",
        title="GitHub account"
    ))


def cmd_repos(args):
    if load_token():
        endpoint = "/user/repos"
        params = {"sort": "updated", "per_page": min(max(args.limit, 1), 100), "type": "owner"}
    else:
        console.print("[dim]Showing popular public repositories. Run `devdeck login` for your own repos.[/dim]")
        endpoint = "/repositories"
        params = {"per_page": min(max(args.limit, 1), 100), "since": 1}
    repos = api_json(endpoint, params)
    table = Table(title="GitHub repositories")
    table.add_column("Repository", style="cyan")
    table.add_column("Stars", justify="right")
    table.add_column("Updated")
    table.add_column("Description")
    for r in repos:
        table.add_row(
            r.get("full_name", "?"),
            str(r.get("stargazers_count", 0)),
            (r.get("updated_at") or "")[:10],
            (r.get("description") or "").replace("\n", " ")[:70],
        )
    console.print(table)


def cmd_releases(args):
    owner, repo = repo_slug(args.repository)
    releases = api_json(f"/repos/{quote(owner)}/{quote(repo)}/releases", {"per_page": min(max(args.limit, 1), 100)})
    if not releases:
        console.print("[yellow]No published releases found.[/yellow]")
        return
    table = Table(title=f"Releases - {owner}/{repo}")
    table.add_column("Tag", style="cyan")
    table.add_column("Release")
    table.add_column("Published")
    table.add_column("Draft / Pre")
    for r in releases:
        table.add_row(
            r.get("tag_name", "?"),
            r.get("name") or "(untitled)",
            (r.get("published_at") or "")[:10],
            ("draft " if r.get("draft") else "") + ("pre-release" if r.get("prerelease") else "stable"),
        )
    console.print(table)
    console.print(f"\nLatest release page: https://github.com/{owner}/{repo}/releases")


def cmd_project(args):
    owner, repo = repo_slug(args.repository)
    info = api_json(f"/repos/{quote(owner)}/{quote(repo)}")
    try:
        releases = api_json(f"/repos/{quote(owner)}/{quote(repo)}/releases", {"per_page": 1})
    except requests.HTTPError:
        releases = []
    latest = releases[0] if releases else None
    lines = [
        f"[bold]{info.get('full_name')}[/bold]",
        info.get("description") or "No description",
        f"Stars: {info.get('stargazers_count', 0)}   Forks: {info.get('forks_count', 0)}   Open issues: {info.get('open_issues_count', 0)}",
        f"Default branch: {info.get('default_branch', 'unknown')}",
        f"Updated: {(info.get('updated_at') or '')[:10]}",
        f"URL: {info.get('html_url')}",
    ]
    if latest:
        lines.append(f"Latest release: {latest.get('tag_name')} - {latest.get('name') or '(untitled)'} ({(latest.get('published_at') or '')[:10]})")
        lines.append(f"Release URL: {latest.get('html_url')}")
    else:
        lines.append("Latest release: none published")
    console.print(Panel("\n".join(lines), title="Project overview", expand=False))


def cmd_open(args):
    owner, repo = repo_slug(args.repository)
    url = f"https://github.com/{owner}/{repo}"
    webbrowser.open(url)
    console.print(f"Opened {url}")


def cmd_clone(args):
    owner, repo = repo_slug(args.repository)
    if not shutil.which("git"):
        raise RuntimeError("Git was not found on PATH. Install Git, then rerun `devdeck clone OWNER/REPO`.")
    url = f"https://github.com/{owner}/{repo}.git"
    result = subprocess.run(["git", "clone", url], check=False)
    if result.returncode:
        raise RuntimeError(f"git clone failed with exit code {result.returncode}")



def _walk_local_files(base: Path):
    """Return safe project files, excluding VCS, virtualenvs, caches and secrets."""
    ignored_dirs = {
        ".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build",
        ".idea", ".vscode", ".pytest_cache", ".mypy_cache"
    }
    ignored_names = {
        ".env", ".env.local", ".env.production", "auth.json",
        "id_rsa", "id_ed25519", "credentials.json"
    }
    result = []
    for path in base.rglob("*"):
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if any(part in ignored_dirs for part in rel.parts):
            continue
        if (path.name in ignored_names or path.name == ".env" or path.name.startswith(".env.")
                or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}):
            continue
        if path.name.endswith(".pyc"):
            continue
        result.append((rel.as_posix(), path))
    return sorted(result)


def _remote_tree(owner: str, repo: str, branch: str):
    data = api_json(f"/repos/{quote(owner)}/{quote(repo)}/git/trees/{quote(branch, safe='')}", {"recursive": "1"})
    if data.get("truncated"):
        raise RuntimeError("GitHub tree response was truncated; refusing to make an unsafe partial sync.")
    return {
        item["path"]: item for item in data.get("tree", [])
        if item.get("type") == "blob"
    }


def _choose_sync_items(items):
    """Simple multi-select terminal picker; number ranges and all/none supported."""
    if not items:
        return []
    console.print("\n[bold]Select files to upload/update[/bold]")
    console.print("[dim]Enter numbers (e.g. 1,3,5-7), 'a' for all, 'n' for none.[/dim]\n")
    table = Table()
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Action", style="yellow")
    table.add_column("File")
    table.add_column("Local size", justify="right")
    for i, item in enumerate(items, 1):
        table.add_row(str(i), item["action"], item["path"], f'{item["size"]:,} B')
    console.print(table)
    while True:
        raw = input("Select files [a/n/numbers]: ").strip().lower()
        try:
            indexes = parse_selection(raw, len(items))
            return [items[index] for index in indexes]
        except ValueError:
            console.print("[red]Invalid selection. Use e.g. 1,3,5-7, a, or n.[/red]")



def cmd_fetch(args):
    """List the authenticated user's repositories and clone a selected one."""
    if not load_token():
        raise RuntimeError("Log in first with `devdeck login`.")
    repos = _list_user_repositories(args.limit)
    if not repos:
        console.print("No repositories found on this account.")
        return
    table = Table(title="Your GitHub repositories - choose one to fetch")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Repository", style="bold")
    table.add_column("Visibility")
    table.add_column("Updated")
    for i, repo in enumerate(repos, 1):
        table.add_row(
            str(i), repo.get("full_name", "?"),
            "Private" if repo.get("private") else "Public",
            (repo.get("updated_at") or "")[:10],
        )
    console.print(table)
    raw = input("Repository number (or q to cancel): ").strip().lower()
    if raw == "q":
        console.print("Cancelled.")
        return
    try:
        idx = int(raw)
        if idx < 1 or idx > len(repos):
            raise ValueError
    except ValueError:
        raise RuntimeError("Invalid repository selection.")
    selected = repos[idx - 1]
    if not shutil.which("git"):
        raise RuntimeError("Git was not found on PATH. Install Git, then retry.")
    destination = Path(args.path).expanduser().resolve() if args.path else Path.cwd() / selected["name"]
    if destination.exists():
        raise RuntimeError(f"Destination already exists: {destination}. Choose another path with --path.")
    url = selected.get("clone_url")
    console.print(f"Fetching [cyan]{selected['full_name']}[/cyan] into {destination}")
    result = subprocess.run(["git", "clone", url, str(destination)], check=False)
    if result.returncode:
        raise RuntimeError(f"git clone failed with exit code {result.returncode}")
    console.print(f"[green]Fetched successfully:[/green] {destination}")
    console.print("To update files back to GitHub later, run:")
    console.print(f'  devdeck update {selected["full_name"]} --path "{destination}"')


def cmd_update(args):
    """Friendly alias for the interactive local-to-GitHub sync workflow."""
    cmd_sync(args)

def cmd_sync(args):
    """Compare local project files with a GitHub repo, then upload selected changes."""
    if not load_token():
        raise RuntimeError("This command requires GitHub login. Configure OAuth Device Flow, then run `devdeck login`.")
    owner, repo = repo_slug(args.repository)
    base = Path(args.path).resolve()
    if not base.is_dir():
        raise RuntimeError(f"Local path is not a directory: {base}")
    info = api_json(f"/repos/{quote(owner)}/{quote(repo)}")
    if info.get("permissions") and not info["permissions"].get("push", False):
        raise RuntimeError("Your GitHub account does not have push access to this repository.")
    branch = args.branch or info.get("default_branch") or "main"
    remote = _remote_tree(owner, repo, branch)
    local = _walk_local_files(base)

    candidates = []
    for rel, path in local:
        # Avoid uploading this tool's own local auth/config or accidental nested archives.
        if path.suffix.lower() in {".zip", ".exe", ".dll"}:
            continue
        remote_item = remote.get(rel)
        if remote_item and remote_item.get("type") != "blob":
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            console.print(f"[yellow]Skipping unreadable file {rel}: {exc}[/yellow]")
            continue
        # Fetch existing remote contents only when needed to compare exact bytes.
        changed = True
        if remote_item:
            try:
                response = github_request("GET", f"/repos/{quote(owner)}/{quote(repo)}/contents/{quote(rel, safe='/')}", params={"ref": branch})
                remote_data = response.json()
                changed = is_content_changed(raw, remote_data)
            except (requests.RequestException, ValueError) as exc:
                raise RuntimeError(
                    f"Could not safely compare {rel} with GitHub; no files were uploaded."
                ) from exc
        if changed:
            candidates.append({
                "path": rel,
                "local": path,
                "bytes": raw,
                "size": len(raw),
                "action": "UPDATE" if remote_item else "NEW",
                "sha": remote_item.get("sha") if remote_item else None,
            })

    if not candidates:
        console.print("[green]Everything matches. No new or changed files found.[/green]")
        return
    console.print(f"Found {len(candidates)} new/changed file(s) in [cyan]{base}[/cyan].")
    selected = _choose_sync_items(candidates)
    if not selected:
        console.print("No files selected; nothing changed.")
        return
    preview = Table(title="Selected updates")
    preview.add_column("Action", style="yellow")
    preview.add_column("File")
    preview.add_column("Size", justify="right")
    for item in selected:
        preview.add_row(item["action"], item["path"], f'{item["size"]:,} B')
    console.print(preview)
    console.print(Panel(
        f"Repository: {owner}/{repo}\nBranch: {branch}\nSelected files: {len(selected)}\n"
        "Each selected file will be committed individually. No remote files will be deleted.",
        title="Review before upload"
    ))
    confirm = input("Type YES to upload these selected files: ").strip()
    if confirm != "YES":
        console.print("Cancelled; nothing uploaded.")
        return
    for item in selected:
        endpoint = f"/repos/{quote(owner)}/{quote(repo)}/contents/{quote(item['path'], safe='/')}"
        payload = {
            "message": f"DevDeck: {'update' if item['action'] == 'UPDATE' else 'add'} {item['path']}",
            "content": base64.b64encode(item["bytes"]).decode("ascii"),
            "branch": branch,
        }
        if item["sha"]:
            payload["sha"] = item["sha"]
        try:
            github_request("PUT", endpoint, json=payload)
            console.print(f"[green][OK][/green] {item['action']} {item['path']}")
        except requests.RequestException as exc:
            console.print(f"[red][FAILED] {item['path']} - {exc}[/red]")
            console.print("[yellow]Stopped at first failure. Already completed files remain committed.[/yellow]")
            raise RuntimeError("Sync stopped; check GitHub before retrying.") from exc
    console.print(f"\n[green]Sync complete: {len(selected)} file(s) uploaded to {owner}/{repo}@{branch}.[/green]")

def cmd_commands(_args):
    table = Table(title="DevDeck command guide")
    table.add_column("Command", style="cyan")
    table.add_column("Purpose")
    rows = [
        ("devdeck login", "Authorize GitHub in your browser"),
        ("devdeck logout", "Remove saved login"),
        ("devdeck whoami", "Show the current GitHub account"),
        ("devdeck repos --limit 20", "List your repositories or public repositories"),
        ("devdeck project OWNER/REPO", "Project details and latest release"),
        ("devdeck releases OWNER/REPO", "List release tags and dates"),
        ("devdeck open OWNER/REPO", "Open a project page"),
        ("devdeck clone OWNER/REPO", "Clone a repository with Git"),
        ("devdeck fetch", "List your GitHub repos and choose one to clone"),
        ("devdeck update OWNER/REPO --path .", "Select local project changes to upload to GitHub"),
        ("devdeck sync OWNER/REPO --path .", "Alias for interactive selected-file sync"),
        ("devdeck doctor", "Check local setup"),
        ("devdeck --help", "Show all commands"),
    ]
    for cmd, desc in rows:
        table.add_row(cmd, desc)
    console.print(table)


def cmd_doctor(_args):
    import platform
    from .auth import config_dir
    checks = [
        ("Python", sys.version.split()[0] + (" (OK)" if sys.version_info >= (3, 10) else " (need 3.10+)")),
        ("Git", shutil.which("git") or "Not found - clone command unavailable"),
        ("GitHub OAuth client ID", "Configured" if os.environ.get("DEVDECK_GITHUB_CLIENT_ID") else "Not set - required only for login"),
        ("Saved GitHub login", "Found" if load_token() else "Not logged in"),
        ("Config directory", str(config_dir())),
        ("Platform", platform.platform()),
    ]
    table = Table(title=f"DevDeck doctor v{__version__}")
    table.add_column("Check", style="cyan")
    table.add_column("Result")
    for k, v in checks:
        table.add_row(k, v)
    console.print(table)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="devdeck",
        description="Avero DevDeck - your GitHub project command center",
        epilog="Start here: devdeck doctor | devdeck commands | devdeck project OWNER/REPO",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("login", help="Log in to GitHub through your browser")
    p.set_defaults(func=cmd_login)
    p = sub.add_parser("logout", help="Remove saved GitHub login")
    p.set_defaults(func=cmd_logout)
    p = sub.add_parser("whoami", help="Show authenticated GitHub account")
    p.set_defaults(func=cmd_whoami)
    p = sub.add_parser("repos", help="List repositories")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_repos)
    p = sub.add_parser("releases", help="List releases for OWNER/REPO")
    p.add_argument("repository")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_releases)
    p = sub.add_parser("project", help="Show repository details and latest release")
    p.add_argument("repository")
    p.set_defaults(func=cmd_project)
    p = sub.add_parser("open", help="Open a repository in your browser")
    p.add_argument("repository")
    p.set_defaults(func=cmd_open)
    p = sub.add_parser("clone", help="Clone a repository using Git")
    p.add_argument("repository")
    p.set_defaults(func=cmd_clone)
    p = sub.add_parser("fetch", help="List your GitHub repositories and interactively clone one")
    p.add_argument("--limit", type=int, default=0, help="Maximum repositories to display (0 lists all)")
    p.add_argument("--path", default=None, help="Destination path for the selected repository")
    p.set_defaults(func=cmd_fetch)
    p = sub.add_parser("update", help="Compare a local project folder and interactively upload selected changes")
    p.add_argument("repository", help="GitHub repository in OWNER/REPO format")
    p.add_argument("--path", default=".", help="Local project root or folder path")
    p.add_argument("--branch", default=None, help="Target branch (default: repository default branch)")
    p.set_defaults(func=cmd_update)
    p = sub.add_parser("sync", help="Compare local files and interactively upload selected changes to GitHub")
    p.add_argument("repository", help="GitHub repository in OWNER/REPO format")
    p.add_argument("--path", default=".", help="Local project folder (default: current directory)")
    p.add_argument("--branch", default=None, help="Target branch (default: repository default branch)")
    p.set_defaults(func=cmd_sync)
    p = sub.add_parser("commands", help="Show developer command guide")
    p.set_defaults(func=cmd_commands)
    p = sub.add_parser("doctor", help="Check local setup")
    p.set_defaults(func=cmd_doctor)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    try:
        args.func(args)
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
