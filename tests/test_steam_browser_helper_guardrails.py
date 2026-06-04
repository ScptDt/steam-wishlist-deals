from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER_DIR = ROOT / "extension" / "steam-access-export"


def _read_helper_text(relative_path: str) -> str:
    return (HELPER_DIR / relative_path).read_text(encoding="utf-8")


def _strip_safe_guardrail_copy(source: str) -> str:
    """Remove user-facing warnings so static scans target behavior paths only."""
    source = re.sub(r"<li>.*?</li>", "", source, flags=re.IGNORECASE | re.DOTALL)
    source = re.sub(r"set_status\((['\"]).*?\1(?:,\s*['\"]\w+['\"])?\);", "", source, flags=re.DOTALL)
    source = re.sub(r"const\s+SENSITIVE_KEY_PATTERN\s*=\s*/.*?/i;", "", source)
    return source


def _extension_source(*, include_guardrail_copy: bool = False) -> str:
    paths = (
        "manifest.json",
        "service_worker.js",
        "popup.html",
        "popup.js",
        "src/export-schema.js",
        "src/sanitize.js",
    )
    source = "\n".join(_read_helper_text(path) for path in paths)
    return source if include_guardrail_copy else _strip_safe_guardrail_copy(source)


class SteamBrowserHelperGuardrailTests(unittest.TestCase):
    def test_manifest_allows_only_manual_active_tab_permissions(self) -> None:
        # Arrange
        manifest = json.loads(_read_helper_text("manifest.json"))

        # Act
        permissions = set(manifest.get("permissions", []))
        serialized = json.dumps(manifest, sort_keys=True)

        # Assert: positive manual-helper contract and negative capability checks.
        self.assertEqual(manifest.get("manifest_version"), 3)
        self.assertEqual(permissions, {"activeTab", "scripting"})
        self.assertNotIn("host_permissions", manifest)
        self.assertNotIn("optional_host_permissions", manifest)
        for forbidden in (
            "cookies",
            "webRequest",
            "nativeMessaging",
            "<all_urls>",
            "http://*/*",
            "https://*/*",
            "http://localhost/*",
            "http://127.0.0.1/*",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_extension_sources_do_not_use_forbidden_browser_or_send_paths(self) -> None:
        # Arrange
        source = _extension_source()

        # Act
        forbidden_patterns = {
            "cookie API": r"\bchrome\.cookies\b|\bcookies\b",
            "webRequest API": r"\bchrome\.webRequest\b|\bwebRequest\b",
            "native messaging": r"\bnativeMessaging\b|\bconnectNative\s*\(|\bsendNativeMessage\s*\(",
            "network fetch": r"\bfetch\s*\(|\bXMLHttpRequest\b",
            "local endpoint direct send": r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?|\bsendBeacon\s*\(",
            "broad host access": r"<all_urls>|https?://\*/\*|\*://\*/\*",
        }

        # Assert: positive local/manual implementation and negative forbidden paths.
        self.assertIn("chrome.scripting.executeScript", source)
        self.assertIn("URL.createObjectURL", source)
        for name, pattern in forbidden_patterns.items():
            with self.subTest(name=name):
                self.assertIsNone(re.search(pattern, source, flags=re.IGNORECASE))

    def test_extension_sources_do_not_declare_steam_mutation_verbs(self) -> None:
        # Arrange
        source = _extension_source()

        # Act
        mutation_patterns = {
            "wishlist mutation": r"\b(?:add|remove|update|edit)[_-]?(?:to)?[_-]?wishlist\b|\bfollow_app\b|\bignore_app\b",
            "cart or purchase mutation": r"\b(?:add|remove)[_-]?to[_-]?cart\b|\bpurchase\b|\bcheckout\b",
            "account settings mutation": r"\b(?:update|edit|change)[_-]?(?:settings|profile|account|family)\b",
            "unsafe HTTP mutation verb": r"\bmethod\s*:\s*['\"](?:POST|PUT|PATCH|DELETE)['\"]",
        }

        # Assert: positive read-only extraction and negative mutation vocabulary.
        self.assertIn("Extract sanitized JSON", _read_helper_text("popup.html"))
        for name, pattern in mutation_patterns.items():
            with self.subTest(name=name):
                self.assertIsNone(re.search(pattern, source, flags=re.IGNORECASE))

    def test_export_schema_and_code_remain_appid_only_without_sensitive_data_paths(self) -> None:
        # Arrange
        source = _extension_source()
        schema_source = _read_helper_text("src/export-schema.js")

        # Act
        safe_collection_keys = {"owned_appids", "family_shared_appids", "wishlist_appids"}
        declared_collection_keys = set(re.findall(r'"([a-z_]+_appids)"', schema_source))
        forbidden_patterns = {
            "password or passcode": r"\bpass(?:word|code)\b",
            "cookie or token": r"\b(?:cookie|token|steamLoginSecure|loginSecure)\b",
            "session identifiers": r"\bsession(?:id|_id)?\b",
            "request headers": r"\brequest[_-]?headers?\b|\bheaders?\s*[:=]|\bauthorization\b",
            "raw responses or HTML": r"\braw[_-]?(?:response|html)?\b|\bouterHTML\b|\binnerHTML\b",
            "profile/member/friend/email data paths": r"\bprofiles?\b|\bmembers?\b|\bfriends?\b|\bemails?\b",
        }

        # Assert: positive AppID-only export keys and negative sensitive paths.
        self.assertEqual(declared_collection_keys, safe_collection_keys)
        self.assertIn('schema: STEAM_ACCESS_SCHEMA', schema_source)
        self.assertIn('ranking_impact: RANKING_IMPACT', schema_source)
        for name, pattern in forbidden_patterns.items():
            with self.subTest(name=name):
                self.assertIsNone(re.search(pattern, source, flags=re.IGNORECASE))

    def test_guardrail_checks_are_static_and_do_not_touch_runtime_paths(self) -> None:
        # Arrange
        test_source = Path(__file__).read_text(encoding="utf-8")
        extension_source = _extension_source(include_guardrail_copy=True)

        # Act
        imported_modules = set(re.findall(r"^(?:import|from)\s+([a-zA-Z0-9_\.]+)", test_source, flags=re.MULTILINE))

        # Assert: positive static reads only and negative runtime dependency use.
        self.assertIn("read_text", test_source)
        self.assertLessEqual(imported_modules, {"__future__", "json", "re", "unittest", "pathlib"})
        self.assertIn("ranking impact none", extension_source)


if __name__ == "__main__":
    unittest.main()
