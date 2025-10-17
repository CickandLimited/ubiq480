import unittest
from unittest import mock

import generate_boot_assets


class GenerateBootAssetsMainTests(unittest.TestCase):
    def test_interactive_selection_runs_actions(self) -> None:
        deps_mock = mock.Mock()
        boot_mock = mock.Mock()

        with mock.patch("generate_boot_assets.logging.basicConfig"), mock.patch(
            "generate_boot_assets.ensure_latest_checkout"
        ), mock.patch(
            "generate_boot_assets.set_bootstrap_enabled"
        ), mock.patch(
            "generate_boot_assets.prompt_for_menu_selection", return_value=["deps", "boot"]
        ), mock.patch.dict(
            generate_boot_assets.ACTION_EXECUTORS,
            {"deps": deps_mock, "boot": boot_mock},
            clear=False,
        ):
            exit_code = generate_boot_assets.main([])

        self.assertEqual(0, exit_code)
        deps_mock.assert_called_once()
        boot_mock.assert_called_once()

    def test_subcommand_runs_selected_action(self) -> None:
        deps_mock = mock.Mock()

        with mock.patch("generate_boot_assets.logging.basicConfig"), mock.patch(
            "generate_boot_assets.ensure_latest_checkout"
        ), mock.patch(
            "generate_boot_assets.set_bootstrap_enabled"
        ), mock.patch.dict(generate_boot_assets.ACTION_EXECUTORS, {"deps": deps_mock}, clear=False):
            exit_code = generate_boot_assets.main(["deps"])

        self.assertEqual(0, exit_code)
        deps_mock.assert_called_once()

    def test_interactive_cancel_returns_error(self) -> None:
        with mock.patch("generate_boot_assets.logging.basicConfig"), mock.patch(
            "generate_boot_assets.ensure_latest_checkout"
        ), mock.patch(
            "generate_boot_assets.set_bootstrap_enabled"
        ), mock.patch(
            "generate_boot_assets.prompt_for_menu_selection", side_effect=generate_boot_assets.MenuCancelled
        ):
            exit_code = generate_boot_assets.main([])

        self.assertEqual(1, exit_code)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
