import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build


class EnsureRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.workdir = Path(self._tempdir.name)
        self.remote = self.workdir / "remote.git"
        self.source = self.workdir / "source"
        self.clone = self.workdir / "clone"

        self._create_remote_repository()

    def tearDown(self) -> None:
        self._tempdir.cleanup()

    def _git(self, *args: str, cwd: Path | None = None) -> None:
        subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def _create_remote_repository(self) -> None:
        self._git("init", "--bare", str(self.remote))
        self._git("init", "-b", "main", str(self.source))
        self._git("config", "user.email", "tests@example.com", cwd=self.source)
        self._git("config", "user.name", "Repo Tests", cwd=self.source)
        (self.source / "README.md").write_text("initial\n")
        self._git("add", "README.md", cwd=self.source)
        self._git("commit", "-m", "initial", cwd=self.source)
        self._git("tag", "v1.0", cwd=self.source)
        self._git("remote", "add", "origin", str(self.remote), cwd=self.source)
        self._git("push", "origin", "main", cwd=self.source)
        self._git("push", "origin", "v1.0", cwd=self.source)

    def _push_new_tag(self, tag: str, content: str) -> None:
        (self.source / "README.md").write_text(content)
        self._git("add", "README.md", cwd=self.source)
        self._git("commit", "-m", f"update {tag}", cwd=self.source)
        self._git("tag", tag, cwd=self.source)
        self._git("push", "origin", "main", cwd=self.source)
        self._git("push", "origin", tag, cwd=self.source)

    def test_reuse_existing_ref_skips_fetch(self) -> None:
        with self.assertLogs(build.LOG, level="INFO"):
            build.ensure_repo(str(self.remote), self.clone, "v1.0")

        with self.assertLogs(build.LOG, level="INFO") as logs:
            build.ensure_repo(str(self.remote), self.clone, "v1.0")

        log_text = "\n".join(logs.output)
        self.assertIn("Reusing cached repository", log_text)
        self.assertNotIn("git fetch", log_text)

    def test_shallow_fetch_when_ref_missing(self) -> None:
        with self.assertLogs(build.LOG, level="INFO"):
            build.ensure_repo(str(self.remote), self.clone, "v1.0")

        self._push_new_tag("v2.0", "second\n")

        with self.assertLogs(build.LOG, level="INFO") as logs:
            build.ensure_repo(str(self.remote), self.clone, "v2.0")

        log_text = "\n".join(logs.output)
        self.assertIn("shallow fetch", log_text)
        self.assertIn("--depth", log_text)

        subprocess.run(["git", "rev-parse", "v2.0"], cwd=self.clone, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_clone_aborts_when_disk_space_low(self) -> None:
        disk_usage_type = type(shutil.disk_usage(Path.cwd()))
        low_space = disk_usage_type(total=10, used=9, free=1)

        with mock.patch("build.shutil.disk_usage", return_value=low_space):
            with self.assertRaises(RuntimeError) as ctx:
                build.ensure_repo(str(self.remote), self.clone, "v1.0")

        self.assertIn("Insufficient disk space", str(ctx.exception))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
