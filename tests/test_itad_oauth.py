import unittest
import urllib.parse

from steam_deals_itad_oauth import (
    ITAD_OAUTH_AUTHORIZE_URL,
    ITAD_OAUTH_TOKEN_URL,
    build_itad_oauth_code_challenge,
    build_itad_oauth_pkce_start,
    build_itad_oauth_refresh_request,
    build_itad_oauth_token_request,
    exchange_itad_oauth_code,
    itad_oauth_bearer_headers,
    itad_oauth_endpoint_support,
    normalize_itad_oauth_token_payload,
    parse_itad_oauth_callback,
    redact_itad_oauth_secrets,
)


class ItadOAuthTests(unittest.TestCase):
    def test_code_challenge_matches_pkce_s256_vector(self) -> None:
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

        challenge = build_itad_oauth_code_challenge(verifier)

        self.assertEqual(challenge, "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    def test_pkce_start_builds_authorization_url_without_client_secret(self) -> None:
        session = build_itad_oauth_pkce_start(
            client_id="CLIENT-ID",
            redirect_uri="http://127.0.0.1:8765/itad/oauth/callback",
            scopes=["user_info", "wait_read"],
            state="STATE-123",
            code_verifier="dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
        )

        parsed = urllib.parse.urlparse(session["authorization_url"])
        params = urllib.parse.parse_qs(parsed.query)

        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}{parsed.path}", ITAD_OAUTH_AUTHORIZE_URL)
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["client_id"], ["CLIENT-ID"])
        self.assertEqual(params["scope"], ["user_info wait_read"])
        self.assertEqual(params["state"], ["STATE-123"])
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertNotIn("client_secret", params)
        self.assertEqual(session["scopes"], ("user_info", "wait_read"))

    def test_pkce_start_rejects_unknown_scope(self) -> None:
        with self.assertRaises(ValueError) as context:
            build_itad_oauth_pkce_start(
                client_id="CLIENT-ID",
                redirect_uri="http://127.0.0.1/callback",
                scopes=["prices_write"],
                state="STATE",
                code_verifier="dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
            )

        self.assertIn("scope no soportado", str(context.exception))

    def test_callback_parser_requires_matching_state_and_code(self) -> None:
        callback = parse_itad_oauth_callback("?code=AUTH-CODE&state=STATE", expected_state="STATE")

        self.assertEqual(callback, {"code": "AUTH-CODE", "state": "STATE"})
        with self.assertRaises(ValueError):
            parse_itad_oauth_callback("?code=AUTH-CODE&state=OTHER", expected_state="STATE")
        with self.assertRaises(ValueError):
            parse_itad_oauth_callback("?error=access_denied&state=STATE", expected_state="STATE")

    def test_token_request_uses_pkce_fields_without_secret_by_default(self) -> None:
        request = build_itad_oauth_token_request(
            client_id="CLIENT-ID",
            redirect_uri="http://127.0.0.1/callback",
            code="AUTH-CODE",
            code_verifier="VERIFIER-123",
        )

        self.assertEqual(request["url"], ITAD_OAUTH_TOKEN_URL)
        self.assertEqual(request["headers"], {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(request["body"]["grant_type"], "authorization_code")
        self.assertEqual(request["body"]["client_id"], "CLIENT-ID")
        self.assertEqual(request["body"]["code"], "AUTH-CODE")
        self.assertEqual(request["body"]["code_verifier"], "VERIFIER-123")
        self.assertNotIn("client_secret", request["body"])

    def test_token_request_can_include_secret_for_confidential_apps_only_if_supplied(self) -> None:
        request = build_itad_oauth_token_request(
            client_id="CLIENT-ID",
            redirect_uri="http://127.0.0.1/callback",
            code="AUTH-CODE",
            code_verifier="VERIFIER-123",
            client_secret="CLIENT-SECRET",
        )

        self.assertEqual(request["body"]["client_secret"], "CLIENT-SECRET")

    def test_exchange_code_uses_injected_post_form_and_normalizes_token_payload(self) -> None:
        calls = []

        def fake_post_form(url, body, headers=None):
            calls.append((url, body, headers))
            return {
                "access_token": "ACCESS-TOKEN",
                "refresh_token": "REFRESH-TOKEN",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "user_info wait_read",
            }

        token = exchange_itad_oauth_code(
            client_id="CLIENT-ID",
            redirect_uri="http://127.0.0.1/callback",
            code="AUTH-CODE",
            code_verifier="VERIFIER-123",
            post_form=fake_post_form,
        )

        self.assertEqual(calls[0][0], ITAD_OAUTH_TOKEN_URL)
        self.assertEqual(calls[0][1]["grant_type"], "authorization_code")
        self.assertEqual(calls[0][2], {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(token["access_token"], "ACCESS-TOKEN")
        self.assertEqual(token["refresh_token"], "REFRESH-TOKEN")
        self.assertEqual(token["token_type"], "Bearer")

    def test_refresh_request_uses_refresh_token_grant(self) -> None:
        request = build_itad_oauth_refresh_request(
            client_id="CLIENT-ID",
            refresh_token="REFRESH-TOKEN",
        )

        self.assertEqual(request["body"]["grant_type"], "refresh_token")
        self.assertEqual(request["body"]["refresh_token"], "REFRESH-TOKEN")
        self.assertNotIn("client_secret", request["body"])

    def test_bearer_headers_and_token_payload_validation(self) -> None:
        self.assertEqual(
            itad_oauth_bearer_headers("ACCESS-TOKEN"),
            {"Authorization": "Bearer ACCESS-TOKEN"},
        )
        with self.assertRaises(ValueError):
            normalize_itad_oauth_token_payload({"access_token": "ACCESS", "token_type": "MAC"})

    def test_redacts_oauth_secrets_from_nested_payloads(self) -> None:
        payload = {
            "client_id": "PUBLIC-CLIENT-ID",
            "client_secret": "CLIENT-SECRET",
            "nested": {"access_token": "ACCESS-TOKEN", "code_verifier": "VERIFIER"},
        }

        redacted = redact_itad_oauth_secrets(payload)

        self.assertEqual(redacted["client_id"], "PUBLIC-CLIENT-ID")
        self.assertEqual(redacted["client_secret"], "[redactado]")
        self.assertEqual(redacted["nested"]["access_token"], "[redactado]")
        self.assertEqual(redacted["nested"]["code_verifier"], "[redactado]")

    def test_endpoint_support_documents_prices_v3_gap_for_full_migration(self) -> None:
        self.assertTrue(itad_oauth_endpoint_support("user_info_v2")["oauth"])
        self.assertTrue(itad_oauth_endpoint_support("deals_v2")["oauth"])
        self.assertFalse(itad_oauth_endpoint_support("games_prices_v3")["oauth"])
        self.assertIn("API-key", itad_oauth_endpoint_support("games_prices_v3")["note"])


if __name__ == "__main__":
    unittest.main()
