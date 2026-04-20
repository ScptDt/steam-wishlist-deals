from __future__ import annotations

import base64
import json
import unittest
import urllib.parse

from steam_tools_desktop import decode_share_payload


class DecodeSharePayloadTests(unittest.TestCase):
    def test_accepts_legacy_original_price_alias(self) -> None:
        raw = base64.b64encode(
            json.dumps(
                {
                    "name": "Alpha",
                    "appid": "10",
                    "price": "$10",
                    "original_price": "$20",
                    "discount": 50,
                }
            ).encode("utf-8")
        ).decode("ascii")

        payload = decode_share_payload(raw)

        self.assertEqual(payload["price_original"], "$20")

    def test_accepts_url_encoded_share_payload(self) -> None:
        raw = base64.b64encode(
            json.dumps(
                {
                    "name": "Bravo",
                    "appid": "20",
                    "price": "$15",
                    "price_original": "$30",
                    "discount": 50,
                }
            ).encode("utf-8")
        ).decode("ascii")
        encoded = urllib.parse.quote(raw)

        payload = decode_share_payload(encoded)

        self.assertEqual(payload["name"], "Bravo")
        self.assertEqual(payload["price_original"], "$30")
