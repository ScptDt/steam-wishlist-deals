from pathlib import Path
import unittest

from steam_deals_config import get_config
from steam_deals_generator import (
    refresh_itad_external_offers_cache,
    resolve_itad_external_offers_cache,
)
from steam_deals_itad import build_itad_external_offers_cache


class FakeStdin:
    def isatty(self):
        return False


class ItadExternalOffersGeneratorTests(unittest.TestCase):
    def test_get_config_exposes_local_itad_external_offers_cache_flag(self) -> None:
        result = get_config(
            script_path=Path("/tmp/fake_script.py"),
            load_user_config_fn=lambda: {},
            save_user_config_fn=lambda _cfg: None,
            handle_watchlist_command_fn=lambda _args: None,
            input_fn=lambda _prompt: "",
            stdin=FakeStdin(),
            exit_fn=lambda _code: None,
            argv=[
                "--vanity",
                "gaben",
                "--itad-external-offers-cache",
                "./itad-external-offers.json",
                "--itad-refresh-external-offers-cache",
            ],
        )

        self.assertEqual(
            result[11]["itad_external_offers_cache"],
            Path("itad-external-offers.json"),
        )
        self.assertTrue(result[11]["itad_refresh_external_offers_cache"])

    def test_get_config_does_not_enable_live_refresh_from_saved_config(self) -> None:
        result = get_config(
            script_path=Path("/tmp/fake_script.py"),
            load_user_config_fn=lambda: {"itad_refresh_external_offers_cache": True},
            save_user_config_fn=lambda _cfg: None,
            handle_watchlist_command_fn=lambda _args: None,
            input_fn=lambda _prompt: "",
            stdin=FakeStdin(),
            exit_fn=lambda _code: None,
            argv=["--vanity", "gaben"],
        )

        self.assertFalse(result[11]["itad_refresh_external_offers_cache"])

    def test_resolve_itad_external_offers_cache_loads_local_cache_without_network(self) -> None:
        cache_payload = build_itad_external_offers_cache(
            [
                {
                    "id": "itad-hades",
                    "title": "Hades",
                    "deals": [
                        {
                            "shop": {"id": 35, "name": "Fanatical"},
                            "price": {"amount": 8.99, "currency": "USD"},
                            "regular": {"amount": 24.99, "currency": "USD"},
                            "cut": 64,
                            "drm": [{"name": "Steam"}],
                            "url": "https://next.isthereanydeal.com/link/hades",
                        }
                    ],
                }
            ],
            {"1145360": "itad-hades"},
            country="MX",
        )
        emitted: list[str] = []

        external_offers = resolve_itad_external_offers_cache(
            Path("itad-cache.json"),
            ["1145360"],
            load_cache_fn=lambda _path: cache_payload,
            emit_fn=emitted.append,
        )

        self.assertIsNotNone(external_offers)
        self.assertEqual(external_offers["items"][0]["store_id"], "fanatical")
        self.assertEqual(external_offers["summary"]["ranking_impact"], "none")
        self.assertIn("Ofertas externas ITAD desde caché local: 1", emitted[0])

    def test_resolve_itad_external_offers_cache_degrades_on_cache_error(self) -> None:
        emitted: list[str] = []

        def broken_loader(_path):
            raise ValueError("JSON inválido")

        external_offers = resolve_itad_external_offers_cache(
            Path("itad-cache.json"),
            ["10"],
            load_cache_fn=broken_loader,
            emit_fn=emitted.append,
        )

        self.assertIsNone(external_offers)
        self.assertIn("No se pudo cargar caché ITAD external_offers", emitted[0])

    def test_refresh_itad_external_offers_cache_writes_cache_only_when_explicit(self) -> None:
        emitted: list[str] = []
        saved = {}

        def fake_prices(itad_ids, _key, country="MX"):
            self.assertEqual(itad_ids, {"1145360": "itad-hades"})
            self.assertEqual(country, "MX")
            return [{"id": "itad-hades", "deals": []}]

        payload = refresh_itad_external_offers_cache(
            Path("itad-cache.json"),
            ["1145360"],
            "SECRET-ITAD",
            appid_to_itad_id={"1145360": "itad-hades"},
            lookup_games_fn=lambda _missing, _key: self.fail("lookup should not run"),
            get_prices_payload_fn=fake_prices,
            save_cache_fn=lambda path, cache: saved.update({"path": path, "cache": cache}),
            now_fn=lambda: "2026-05-22T00:00:00Z",
            emit_fn=emitted.append,
        )

        self.assertIsNotNone(payload)
        self.assertEqual(saved["path"], Path("itad-cache.json"))
        self.assertEqual(saved["cache"]["appid_to_itad_id"], {"1145360": "itad-hades"})
        self.assertEqual(saved["cache"]["fetched_at"], "2026-05-22T00:00:00Z")
        self.assertIn("Caché ITAD external_offers actualizada", emitted[0])

    def test_refresh_itad_external_offers_cache_requires_key_and_cache_path(self) -> None:
        emitted: list[str] = []
        save_calls: list[dict] = []

        self.assertIsNone(
            refresh_itad_external_offers_cache(
                None,
                ["10"],
                "SECRET-ITAD",
                save_cache_fn=lambda _path, cache: save_calls.append(cache),
                emit_fn=emitted.append,
            )
        )
        self.assertIsNone(
            refresh_itad_external_offers_cache(
                Path("itad-cache.json"),
                ["10"],
                None,
                save_cache_fn=lambda _path, cache: save_calls.append(cache),
                emit_fn=emitted.append,
            )
        )

        self.assertEqual(save_calls, [])
        self.assertIn("requiere --itad-external-offers-cache", emitted[0])
        self.assertIn("requiere --itad-key", emitted[1])

    def test_refresh_itad_external_offers_cache_preserves_existing_cache_on_failure(self) -> None:
        emitted: list[str] = []
        save_calls: list[dict] = []

        payload = refresh_itad_external_offers_cache(
            Path("itad-cache.json"),
            ["10"],
            "SECRET-ITAD",
            appid_to_itad_id={"10": "itad-10"},
            get_prices_payload_fn=lambda _ids, _key, country="MX": (_ for _ in ()).throw(
                RuntimeError("429 Too Many Requests")
            ),
            save_cache_fn=lambda _path, cache: save_calls.append(cache),
            emit_fn=emitted.append,
        )

        self.assertIsNone(payload)
        self.assertEqual(save_calls, [])
        self.assertIn("No se pudo refrescar caché ITAD external_offers", emitted[0])


if __name__ == "__main__":
    unittest.main()
