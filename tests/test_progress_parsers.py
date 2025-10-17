import unittest

import build
import progress


class GitProgressParserTests(unittest.TestCase):
    def test_receiving_objects_line(self) -> None:
        parser = progress.GitProgressParser()
        line = "Receiving objects:  42% (123/456), 12.34 MiB | 1.23 MiB/s"
        updates = parser.parse(line)
        self.assertEqual(1, len(updates))
        update = updates[0]
        self.assertEqual("Receiving objects", update.label)
        self.assertEqual(42.0, update.percent)
        self.assertEqual(123, update.current)
        self.assertEqual(456, update.total)
        self.assertAlmostEqual(12.34 * 1024**2, update.size_bytes or 0, delta=1)
        self.assertAlmostEqual(1.23 * 1024**2, update.speed_bytes_per_sec or 0, delta=1)

    def test_prepare_adds_progress_flag(self) -> None:
        parser, prepared = progress.get_progress_parser(["git", "clone", "repo", "dest"])
        self.assertIsInstance(parser, progress.GitProgressParser)
        self.assertIn("--progress", prepared)


class DebootstrapProgressParserTests(unittest.TestCase):
    def test_progress_line(self) -> None:
        parser = progress.DebootstrapProgressParser()
        updates = parser.parse("Progress: 47% (Configuring system)")
        self.assertEqual(1, len(updates))
        update = updates[0]
        self.assertEqual("Configuring system", update.label)
        self.assertEqual(47.0, update.percent)


class ArchiveProgressParserTests(unittest.TestCase):
    def test_archive_progress_line(self) -> None:
        parser = progress.ArchiveProgressParser()
        updates = parser.parse("Extracting: 55% (22/40), 120.0 MiB @ 10.0 MiB/s")
        self.assertEqual(1, len(updates))
        update = updates[0]
        self.assertEqual("Extracting", update.label)
        self.assertEqual(55.0, update.percent)
        self.assertEqual(22, update.current)
        self.assertEqual(40, update.total)
        self.assertAlmostEqual(120.0 * 1024**2, update.size_bytes or 0, delta=1)
        self.assertAlmostEqual(10.0 * 1024**2, update.speed_bytes_per_sec or 0, delta=1)


class ProgressFormattingTests(unittest.TestCase):
    def test_format_progress_message(self) -> None:
        update = progress.ProgressUpdate(
            label="Receiving objects",
            percent=42.0,
            current=123,
            total=456,
            size_bytes=12.34 * 1024**2,
            speed_bytes_per_sec=1.23 * 1024**2,
        )
        message = progress.format_progress_message(update)
        self.assertIn("Receiving objects", message)
        self.assertIn("42%", message)
        self.assertIn("(123/456)", message)
        self.assertIn("MiB", message)
        self.assertIn("/s", message)


class DownloadParsingTests(unittest.TestCase):
    def test_parse_curl_command(self) -> None:
        parsed = build._parse_download_command(
            ["curl", "-L", "https://example.com/file.bin", "-o", "output.bin"]
        )
        self.assertEqual(("https://example.com/file.bin", "output.bin"), parsed)

    def test_parse_wget_command(self) -> None:
        parsed = build._parse_download_command(
            ["wget", "https://example.com/archive.tar.gz", "-O", "archive.tar.gz"]
        )
        self.assertEqual(("https://example.com/archive.tar.gz", "archive.tar.gz"), parsed)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
