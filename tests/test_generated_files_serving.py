from __future__ import annotations

import io
import unittest
import urllib.parse
from pathlib import Path
from tempfile import TemporaryDirectory

import steam_deals_web as web
from steam_deals_web import (
    DEFAULT_OUTPUT_DIR,
    Handler,
    build_command,
    build_pd2_command,
    generated_file_error_page,
    generated_file_content_disposition,
    generated_file_content_type,
    is_safe_generated_file_name,
    open_output_folder,
    resolve_output_dir,
)


class _FakeFileHandler:
    def __init__(self) -> None:
        self.status = None
        self.headers = []
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.headers.append((name, value))

    def end_headers(self):
        pass

    def header(self, name: str) -> str | None:
        for header_name, value in self.headers:
            if header_name.lower() == name.lower():
                return value
        return None

    def body_text(self) -> str:
        return self.wfile.getvalue().decode("utf-8")


class _FakeJsonHandler:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.status = None
        self.json = None

    def _read_json_body(self):
        return self.body

    def _send_json(self, data, status=200):
        self.status = status
        self.json = data


class GeneratedFilesServingTests(unittest.TestCase):
    def test_empty_output_resolves_to_project_output_folder(self) -> None:
        self.assertEqual(resolve_output_dir(None), DEFAULT_OUTPUT_DIR)
        self.assertEqual(resolve_output_dir(""), DEFAULT_OUTPUT_DIR)
        self.assertEqual(resolve_output_dir("custom-reports"), web.PROJECT_DIR / "custom-reports")

    def test_build_commands_always_pass_resolved_output_dir(self) -> None:
        deals_cmd = build_command({"vanity": "gaben"}, {})
        pd2_cmd = build_pd2_command({"vanity": "gaben"}, {})

        self.assertEqual(Path(deals_cmd[deals_cmd.index("--output") + 1]), DEFAULT_OUTPUT_DIR)
        self.assertEqual(Path(pd2_cmd[pd2_cmd.index("--output") + 1]), DEFAULT_OUTPUT_DIR)

    def test_open_output_folder_creates_directory_and_uses_platform_opener(self) -> None:
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "reports"
            commands = []

            opened = open_output_folder(
                target,
                platform="linux",
                popen_fn=lambda command: commands.append(command),
            )

            self.assertEqual(opened, target)
            self.assertTrue(target.is_dir())
            self.assertEqual(commands, [["xdg-open", str(target)]])

    def test_open_output_folder_endpoint_uses_resolved_output_and_returns_json(self) -> None:
        original_open_output_folder = web.open_output_folder
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "reports"
            opened_paths = []

            def fake_open_output_folder(path):
                opened_paths.append(path)
                path.mkdir(parents=True, exist_ok=True)
                return path

            web.open_output_folder = fake_open_output_folder
            handler = _FakeJsonHandler({"config": {"output": str(target)}})
            try:
                Handler._serve_open_output_folder(handler)
            finally:
                web.open_output_folder = original_open_output_folder
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.json["status"], "opened")
        self.assertEqual(Path(handler.json["path"]), target)
        self.assertEqual(opened_paths, [target])

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

    def test_generated_file_name_validation_blocks_path_traversal(self) -> None:
        self.assertTrue(is_safe_generated_file_name("Steam Deals 2026-04-24.html"))
        self.assertFalse(is_safe_generated_file_name("../secrets.json"))
        self.assertFalse(is_safe_generated_file_name("nested/report.html"))
        self.assertFalse(is_safe_generated_file_name("nested\\report.html"))
        self.assertFalse(is_safe_generated_file_name(""))

    def test_generated_file_error_page_is_clear_and_escapes_content(self) -> None:
        page = generated_file_error_page(404, "Archivo <faltante>", "No usar <path>")

        self.assertIn("Error 404", page)
        self.assertIn("Archivo &lt;faltante&gt;", page)
        self.assertIn("No usar &lt;path&gt;", page)
        self.assertIn("Volver a Steam Tools", page)

    def test_serve_file_returns_clear_403_for_invalid_names(self) -> None:
        handler = _FakeFileHandler()

        Handler._serve_file(handler, urllib.parse.quote("../secrets.json", safe=""))

        self.assertEqual(handler.status, 403)
        self.assertEqual(handler.header("Content-Type"), "text/html; charset=utf-8")
        self.assertEqual(handler.header("X-Content-Type-Options"), "nosniff")
        self.assertIn("Archivo no disponible", handler.body_text())

    def test_serve_file_returns_clear_404_for_missing_files(self) -> None:
        handler = _FakeFileHandler()
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            Handler.output_dir = temp_dir
            try:
                Handler._serve_file(handler, urllib.parse.quote("missing.html", safe=""))
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 404)
        self.assertIn("Archivo no encontrado", handler.body_text())

    def test_serve_file_returns_clear_500_for_read_failures(self) -> None:
        handler = _FakeFileHandler()
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "folder.html").mkdir()
            Handler.output_dir = temp_dir
            try:
                Handler._serve_file(handler, urllib.parse.quote("folder.html", safe=""))
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 500)
        self.assertIn("No se pudo leer el archivo", handler.body_text())

    def test_serve_file_keeps_successful_html_inline(self) -> None:
        handler = _FakeFileHandler()
        original_output_dir = Handler.output_dir
        with TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "report.html").write_text("<h1>OK</h1>", encoding="utf-8")
            Handler.output_dir = temp_dir
            try:
                Handler._serve_file(handler, urllib.parse.quote("report.html", safe=""))
            finally:
                Handler.output_dir = original_output_dir

        self.assertEqual(handler.status, 200)
        self.assertIn("text/html", handler.header("Content-Type"))
        self.assertTrue(handler.header("Content-Disposition").startswith("inline;"))
        self.assertEqual(handler.body_text(), "<h1>OK</h1>")


if __name__ == "__main__":
    unittest.main()
