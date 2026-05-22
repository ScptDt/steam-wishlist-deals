from pathlib import Path
import unittest

from steam_deals_config import get_config
from steam_deals_generator import resolve_itad_external_offers_cache
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
            ],
        )

        self.assertEqual(
            result[11]["itad_external_offers_cache"],
            Path("itad-external-offers.json"),
        )

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


if __name__ == "__main__":
    unittest.main()
