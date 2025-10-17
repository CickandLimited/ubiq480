import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import self_check


class EnsureLatestCheckoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(self_check.__file__).resolve().parent

    def test_skip_when_environment_flag_set(self) -> None:
        with mock.patch.dict(os.environ, {self_check.SKIP_ENVIRONMENT_FLAG: "1"}, clear=False), mock.patch(
            "self_check._resolve_local_head"
        ) as local_mock, mock.patch("self_check._resolve_remote_head") as remote_mock:
            self_check.ensure_latest_checkout(self.repo_root)

        local_mock.assert_not_called()
        remote_mock.assert_not_called()

    def test_mismatched_commits_raise(self) -> None:
        fake_repo = Path("/tmp/fake-repo")
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch(
            "self_check._resolve_local_head", return_value="abc"
        ), mock.patch("self_check._resolve_remote_head", return_value="def"), mock.patch(
            "pathlib.Path.exists", return_value=True
        ), self.assertRaises(SystemExit) as exc:
            self_check.ensure_latest_checkout(fake_repo)

        self.assertIn("out-of-date", str(exc.exception))

    def test_remote_failure_surfaces_message(self) -> None:
        fake_repo = Path("/tmp/fake-repo")
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch(
            "self_check._resolve_local_head", return_value="abc"
        ), mock.patch(
            "self_check._resolve_remote_head", side_effect=subprocess.CalledProcessError(1, ["git"])
        ), mock.patch("pathlib.Path.exists", return_value=True), self.assertRaises(SystemExit) as exc:
            self_check.ensure_latest_checkout(fake_repo)

        self.assertIn("Unable to contact the canonical repository", str(exc.exception))

    def test_matching_commits_pass(self) -> None:
        fake_repo = Path("/tmp/fake-repo")
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch(
            "self_check._resolve_local_head", return_value="abc"
        ), mock.patch("self_check._resolve_remote_head", return_value="abc"), mock.patch(
            "pathlib.Path.exists", return_value=True
        ):
            self_check.ensure_latest_checkout(fake_repo)

    def test_missing_git_metadata_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir)
            with self.assertRaises(SystemExit) as exc:
                self_check.ensure_latest_checkout(repo_path)

        self.assertIn("missing its .git metadata", str(exc.exception))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

