# Publish `avero-devdeck` to PyPI

This repository is configured to publish through GitHub Actions and PyPI Trusted Publishing. No PyPI API token needs to be stored in GitHub.

## One-time setup

1. Create/sign in to your PyPI account: https://pypi.org/account/register/
2. Push this repository to GitHub as a public repository.
3. On PyPI, open **Publishing** / **Add a new pending publisher** for the project name `avero-devdeck`.
4. Enter the exact GitHub owner, repository name, and workflow filename `.github/workflows/publish.yml`, and choose the GitHub environment only if you configure one. Do not guess the owner/repository fields.
5. If PyPI says the project name is already taken, choose another unused distribution name and update `project.name` in `pyproject.toml`.

## Release

After the pending publisher is configured:

1. Ensure `project.version` in `pyproject.toml` is a version that has never been uploaded before.
2. Commit and push all files to GitHub.
3. Create a GitHub Release with a tag matching the version, e.g. `v0.1.0`, then publish the release.
4. Open the repository's **Actions** tab and confirm the `Publish to PyPI` workflow succeeds.
5. Install from PyPI:

```bash
py -m pip install --upgrade avero-devdeck
devdeck --help
devdeck doctor
```

The first release is not automatic until the GitHub repository exists and the PyPI Trusted Publisher has been configured. This workflow only publishes a package when you publish a GitHub Release (or manually run the workflow).
