from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import webbrowser
from urllib.parse import quote

import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from . import __version__
from .auth import clear_token, github_request, load_token, login as do_login

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
    table = Table(title=f"Releases — {owner}/{repo}")
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
        lines.append(f"Latest release: {latest.get('tag_name')} — {latest.get('name') or '(untitled)'} ({(latest.get('published_at') or '')[:10]})")
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
        ("Git", shutil.which("git") or "Not found — clone command unavailable"),
        ("GitHub OAuth client ID", "Configured" if os.environ.get("DEVDECK_GITHUB_CLIENT_ID") else "Not set — required only for login"),
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
        description="Avero DevDeck — your GitHub project command center",
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
