from __future__ import annotations

import io
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, call, patch

from avero_devdeck import auth


class GitHubCliLoginTests(unittest.TestCase):
    def test_delegates_browser_login_and_saves_token_without_printing_it(self):
        token = "gho-secret-test-token"
        gh_path = "/usr/bin/gh"
        completed = subprocess.CompletedProcess(args=[], returncode=0)
        token_result = subprocess.CompletedProcess(args=[], returncode=0, stdout=f"{token}\n", stderr="")
        output = io.StringIO()

        with (
            patch("avero_devdeck.auth.shutil.which", return_value=gh_path),
            patch("avero_devdeck.auth.subprocess.run", side_effect=[completed, token_result]) as run,
            patch("avero_devdeck.auth.save_token") as save_token,
            redirect_stdout(output),
            redirect_stderr(output),
        ):
            returned = auth.login("configured-client-id")

        self.assertEqual(returned, token)
        save_token.assert_called_once_with(token)
        self.assertEqual(
            run.call_args_list,
            [
                call(
                    [gh_path, "auth", "login", "--hostname", "github.com", "--web", "--git-protocol", "https"],
                    check=False,
                ),
                call(
                    [gh_path, "auth", "token", "--hostname", "github.com"],
                    capture_output=True,
                    text=True,
                    check=False,
                ),
            ],
        )
        self.assertNotIn(token, output.getvalue())

    def test_missing_gh_shows_installation_instructions(self):
        with patch("avero_devdeck.auth.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, r"Install it from https://cli\.github\.com/"):
                auth.login()

    def test_failed_browser_authorization_does_not_request_or_save_token(self):
        token = "must-not-appear-in-error"
        failure = subprocess.CompletedProcess(args=[], returncode=1, stdout=token, stderr=token)

        with (
            patch("avero_devdeck.auth.shutil.which", return_value="gh"),
            patch("avero_devdeck.auth.subprocess.run", return_value=failure) as run,
            patch("avero_devdeck.auth.save_token") as save_token,
        ):
            with self.assertRaises(RuntimeError) as raised:
                auth.login()

        self.assertEqual(run.call_count, 1)
        save_token.assert_not_called()
        self.assertNotIn(token, str(raised.exception))

    def test_failed_token_retrieval_does_not_expose_command_output(self):
        secret = "gho-never-log-this"
        completed = subprocess.CompletedProcess(args=[], returncode=0)
        failure = subprocess.CompletedProcess(args=[], returncode=1, stdout=secret, stderr=secret)

        with (
            patch("avero_devdeck.auth.shutil.which", return_value="gh"),
            patch("avero_devdeck.auth.subprocess.run", side_effect=[completed, failure]),
            patch("avero_devdeck.auth.save_token") as save_token,
        ):
            with self.assertRaises(RuntimeError) as raised:
                auth.login()

        save_token.assert_not_called()
        self.assertNotIn(secret, str(raised.exception))

    def test_configured_oauth_device_flow_remains_available_without_gh(self):
        token = "oauth-secret-test-token"
        device_response = Mock()
        device_response.json.return_value = {
            "device_code": "device-code",
            "user_code": "USER-CODE",
            "verification_uri": "https://github.com/login/device",
            "interval": 1,
            "expires_in": 60,
        }
        token_response = Mock()
        token_response.json.return_value = {"access_token": token}

        with (
            patch("avero_devdeck.auth.shutil.which", return_value=None),
            patch("avero_devdeck.auth.requests.post", side_effect=[device_response, token_response]) as post,
            patch("avero_devdeck.auth.webbrowser.open"),
            patch("avero_devdeck.auth.time.sleep"),
            patch("avero_devdeck.auth.time.time", return_value=0),
            patch("avero_devdeck.auth.save_token") as save_token,
        ):
            self.assertEqual(auth.login("configured-client-id"), token)

        save_token.assert_called_once_with(token)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].kwargs["data"]["client_id"], "configured-client-id")


class TokenStorageTests(unittest.TestCase):
    def test_saved_token_can_be_loaded_and_is_private_on_posix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            with patch("avero_devdeck.auth.token_path", return_value=path):
                auth.save_token("token-for-storage-test")
                self.assertEqual(auth.load_token(), "token-for-storage-test")
                if os.name == "posix":
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertTrue(auth.clear_token())
                self.assertIsNone(auth.load_token())


if __name__ == "__main__":
    unittest.main()
