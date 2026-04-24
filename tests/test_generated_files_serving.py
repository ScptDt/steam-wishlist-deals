from __future__ import annotations

import unittest

from steam_deals_web import (
    generated_file_content_disposition,
    generated_file_content_type,
)


class GeneratedFilesServingTests(unittest.TestCase):
    def test_generated_file_content_type_matches_report_extensions(self) -> None:
        self.assertEqual(generated_file_content_type(".html"), "text/html")
        self.assertEqual(generated_file_content_type(".md"), "text/plain")
        self.assertEqual(generated_file_content_type(".csv"), "text/csv")
        self.assertEqual(generated_file_content_type(".json"), "application/json")
        self.assertEqual(generated_file_content_type(".bin"), "application/octet-stream")

    def test_generated_file_content_disposition_opens_html_and_downloads_data_files(self) -> None:
        html = generated_file_content_disposition("Steam Deals 2026-04-24.html", ".html")
        csv = generated_file_content_disposition("Steam Deals 2026-04-24.csv", ".csv")
        json = generated_file_content_disposition("Steam Deals 2026-04-24.json", ".json")

        self.assertTrue(html.startswith("inline;"))
        self.assertTrue(csv.startswith("attachment;"))
        self.assertTrue(json.startswith("attachment;"))
        self.assertIn("filename*=UTF-8''Steam%20Deals%202026-04-24.csv", csv)

    def test_generated_file_content_disposition_sanitizes_header_filename(self) -> None:
        disposition = generated_file_content_disposition('Steam Deals "sale".json', ".json")

        self.assertIn('filename="Steam Deals _sale_.json"', disposition)
        self.assertNotIn('filename="Steam Deals "sale".json"', disposition)


if __name__ == "__main__":
    unittest.main()
