import unittest

from cli_prompts import MenuCancelled, MenuOption, prompt_for_menu_selection


class PromptForMenuSelectionTests(unittest.TestCase):
    def test_single_selection_returns_expected_key(self) -> None:
        responses = iter(["2"])
        captured: list[str] = []

        result = prompt_for_menu_selection(
            "Pick an option:",
            [MenuOption("one", "One"), MenuOption("two", "Two")],
            input_func=lambda prompt: next(responses),
            print_func=captured.append,
        )

        self.assertEqual(["two"], result)
        self.assertIn("Pick an option:", captured[0])

    def test_multiple_selection_handles_invalid_then_valid_input(self) -> None:
        responses = iter(["", "4", "1, 2 2"])
        captured: list[str] = []

        result = prompt_for_menu_selection(
            "Choose stages:",
            [MenuOption("a", "Stage A"), MenuOption("b", "Stage B"), MenuOption("c", "Stage C")],
            allow_multiple=True,
            input_func=lambda prompt: next(responses),
            print_func=captured.append,
        )

        self.assertEqual(["a", "b"], result)
        self.assertIn("Please choose at least one option.", captured)
        self.assertIn("Selection out of range. Try again.", captured)

    def test_cancel_request_raises(self) -> None:
        with self.assertRaises(MenuCancelled):
            prompt_for_menu_selection(
                "Pick:",
                [MenuOption("x", "X")],
                input_func=lambda prompt: "q",
            )

    def test_keyboard_interrupt_is_translated(self) -> None:
        def raise_keyboard_interrupt(_: str) -> str:
            raise KeyboardInterrupt

        with self.assertRaises(MenuCancelled):
            prompt_for_menu_selection(
                "Pick:",
                [MenuOption("x", "X")],
                input_func=raise_keyboard_interrupt,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
