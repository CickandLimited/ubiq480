import subprocess
import unittest
from pathlib import Path
from unittest import mock

import build


class PushLogFileTests(unittest.TestCase):
    def test_push_log_file_runs_git_commands(self) -> None:
        with mock.patch("build.subprocess.run") as run_mock:
            run_mock.return_value = subprocess.CompletedProcess(["git"], 0)

            build.push_log_file(build.BUILD_LOG_PATH)

        expected_calls = [
            mock.call(
                ["git", "add", str(build.BUILD_LOG_PATH.relative_to(build.REPO_ROOT))],
                check=True,
                cwd=build.REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ),
            mock.call(
                ["git", "commit", "-m", "chore: update build log"],
                check=True,
                cwd=build.REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ),
            mock.call(
                ["git", "push"],
                check=True,
                cwd=build.REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ),
        ]
        run_mock.assert_has_calls(expected_calls)
        self.assertEqual(3, run_mock.call_count)

    def test_push_log_file_logs_warning_on_failure(self) -> None:
        error = subprocess.CalledProcessError(1, ["git", "add", "build.log"], "", "")
        with mock.patch("build.subprocess.run", side_effect=error) as run_mock:
            with self.assertLogs(build.LOG, level="WARNING") as logs:
                build.push_log_file(Path("/tmp/build.log"))

        self.assertIn("Failed to stage build log", "\n".join(logs.output))
        run_mock.assert_called_once()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
