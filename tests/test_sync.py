from __future__ import annotations

import base64
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

from unittest.mock import patch

from avero_devdeck.cli import _list_user_repositories, _walk_local_files, cmd_update, repo_slug
from avero_devdeck.sync import decode_remote_content, is_content_changed, parse_selection


class SelectionTests(unittest.TestCase):
    def test_all_none_numbers_and_ranges(self):
        self.assertEqual(parse_selection("a", 4), [0, 1, 2, 3])
        self.assertEqual(parse_selection("n", 4), [])
        self.assertEqual(parse_selection(" 1, 3-4,3 ", 4), [0, 2, 3])

    def test_invalid_selection_is_rejected(self):
        for value in ("0", "5", "3-2", "1,,2", "1-5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_selection(value, 4)


class RemoteComparisonTests(unittest.TestCase):
    def test_decodes_github_base64_content_with_wrapping(self):
        content = base64.b64encode(b"same bytes").decode("ascii")
        wrapped = content[:4] + "\n" + content[4:]
        self.assertEqual(decode_remote_content({"encoding": "base64", "content": wrapped}), b"same bytes")

    def test_refuses_uncomparable_remote_content(self):
        for response in ({"encoding": "none", "content": ""}, {"encoding": "base64", "content": "%%%"}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                decode_remote_content(response)

    def test_exact_duplicates_are_unchanged_and_different_bytes_need_update(self):
        remote = {"encoding": "base64", "content": base64.b64encode(b"same").decode("ascii")}
        self.assertFalse(is_content_changed(b"same", remote))
        self.assertTrue(is_content_changed(b"changed", remote))


class LocalProjectTests(unittest.TestCase):
    def test_walk_excludes_secrets_build_artifacts_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("print('hello')", encoding="utf-8")
            (root / ".env").write_text("TOKEN=secret", encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("internal", encoding="utf-8")
            (root / "dist").mkdir()
            (root / "dist" / "bundle.js").write_text("bundle", encoding="utf-8")
            result = _walk_local_files(root)
            self.assertEqual([relative for relative, _ in result], ["app.py"])

    def test_repo_slug_parses_owner_and_repository(self):
        self.assertEqual(repo_slug("/owner/repo.git/"), ("owner", "repo"))

    def test_repository_listing_follows_pages_and_respects_limit(self):
        first_page = [{"id": index} for index in range(100)]
        second_page = [{"id": 100}, {"id": 101}]
        with patch("avero_devdeck.cli.api_json", side_effect=[first_page, second_page]) as api:
            repos = _list_user_repositories(101)
        self.assertEqual(len(repos), 101)
        self.assertEqual(api.call_count, 2)
        self.assertEqual(api.call_args_list[1].args[1]["page"], 2)

    def test_update_requires_exact_confirmation_before_put(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "app.py").write_text("print('new')", encoding="utf-8")
            args = SimpleNamespace(repository="owner/repo", path=directory, branch=None)
            with (
                patch("avero_devdeck.cli.load_token", return_value="token"),
                patch("avero_devdeck.cli.api_json", side_effect=[
                    {"default_branch": "main", "permissions": {"push": True}},
                    {"truncated": False, "tree": []},
                ]),
                patch("avero_devdeck.cli.github_request") as github_request,
                patch("builtins.input", side_effect=["1", "no"]),
            ):
                cmd_update(args)
            self.assertFalse(any(call.args[0] == "PUT" for call in github_request.call_args_list))


if __name__ == "__main__":
    unittest.main()
