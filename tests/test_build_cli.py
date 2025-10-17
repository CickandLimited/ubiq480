import argparse
import unittest
from unittest import mock

import build


class BuildMainTests(unittest.TestCase):
    def test_interactive_selection_runs_each_stage(self) -> None:
        stage_mocks = {"deps": mock.Mock(), "kernel": mock.Mock()}

        with mock.patch("build.setup_logging"), mock.patch("build.ensure_latest_checkout"), mock.patch(
            "build.set_bootstrap_enabled"
        ), mock.patch(
            "build._interactive_stage_selection", return_value=["deps", "kernel"]
        ), mock.patch("build.confirm_execution", side_effect=[True, True]) as confirm_mock, mock.patch.dict(
            build.STAGE_EXECUTORS, stage_mocks, clear=False
        ):
            exit_code = build.main([])

        self.assertEqual(0, exit_code)
        stage_mocks["deps"].assert_called_once()
        stage_mocks["kernel"].assert_called_once()
        self.assertEqual([mock.call("deps", assume_yes=False), mock.call("kernel", assume_yes=False)], confirm_mock.mock_calls)

    def test_subcommand_invocation_respects_headless_mode(self) -> None:
        stage_mock = mock.Mock()

        with mock.patch("build.setup_logging"), mock.patch("build.ensure_latest_checkout"), mock.patch(
            "build.set_bootstrap_enabled"
        ), mock.patch(
            "build.confirm_execution", return_value=True
        ) as confirm_mock, mock.patch.dict(build.STAGE_EXECUTORS, {"deps": stage_mock}, clear=False):
            exit_code = build.main(["deps"])

        self.assertEqual(0, exit_code)
        stage_mock.assert_called_once()
        confirm_mock.assert_called_once_with("deps", assume_yes=False)

    def test_interactive_cancellation_aborts(self) -> None:
        with mock.patch("build.setup_logging"), mock.patch("build.ensure_latest_checkout"), mock.patch(
            "build.set_bootstrap_enabled"
        ), mock.patch(
            "build._interactive_stage_selection", side_effect=build.MenuCancelled
        ):
            exit_code = build.main([])

        self.assertEqual(1, exit_code)

    def test_repository_tree_logged_after_successful_run(self) -> None:
        stage_mock = mock.Mock()

        with mock.patch("build.setup_logging"), mock.patch("build.ensure_latest_checkout"), mock.patch(
            "build.set_bootstrap_enabled"
        ), mock.patch("build.confirm_execution", return_value=True), mock.patch.dict(
            build.STAGE_EXECUTORS, {"deps": stage_mock}, clear=False
        ), mock.patch("build.log_repository_tree") as tree_mock:
            exit_code = build.main(["deps"])

        self.assertEqual(0, exit_code)
        tree_mock.assert_called_once_with(build.REPO_ROOT, build.LOG)

    def test_repository_tree_logged_after_failed_run(self) -> None:
        def _fail(_: argparse.Namespace) -> None:
            raise RuntimeError("boom")

        with mock.patch("build.setup_logging"), mock.patch("build.ensure_latest_checkout"), mock.patch(
            "build.set_bootstrap_enabled"
        ), mock.patch("build.confirm_execution", return_value=True), mock.patch.dict(
            build.STAGE_EXECUTORS, {"deps": _fail}, clear=False
        ), mock.patch("build.log_repository_tree") as tree_mock:
            exit_code = build.main(["deps"])

        self.assertEqual(1, exit_code)
        tree_mock.assert_called_once_with(build.REPO_ROOT, build.LOG)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
