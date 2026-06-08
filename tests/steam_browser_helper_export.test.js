"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const {
  ADVISORY_ONLY,
  RANKING_IMPACT,
  STEAM_ACCESS_SCHEMA,
  STEAM_ACCESS_SOURCE,
} = require("../extension/steam-access-export/src/export-schema.js");
const {
  build_sanitized_steam_access_export,
  has_sensitive_key,
  sanitize_steam_access_input,
} = require("../extension/steam-access-export/src/sanitize.js");
const collector = require("../extension/steam-access-export/src/collector.js");
const service_worker = require("../extension/steam-access-export/service_worker.js");

const FIXTURE_DIR = path.join(__dirname, "fixtures", "steam_browser_helper_export");
const GENERATED_AT = "2026-06-04T12:00:00Z";
const FORBIDDEN_OUTPUT_PATTERNS = [
  /cookie/i,
  /steamLoginSecure/i,
  /session/i,
  /token/i,
  /header/i,
  /raw[_-]?(?:response|html)?/i,
  /<html/i,
  /email/i,
  /friend/i,
  /family_members?/i,
  /family_member_name/i,
  /profile/i,
  /persona/i,
  /name/i,
  /title/i,
  /notes/i,
  /url/i,
];

const read_fixture_json = (name) => {
  const fixture_path = path.join(FIXTURE_DIR, name);
  return JSON.parse(fs.readFileSync(fixture_path, "utf8"));
};

const read_fixture_text = (name) => {
  const fixture_path = path.join(FIXTURE_DIR, name);
  return fs.readFileSync(fixture_path, "utf8");
};

const read_helper_text = (name) => fs.readFileSync(
  path.join(__dirname, "..", "extension", "steam-access-export", name),
  "utf8",
);

const assert_export_contract = (export_json) => {
  assert.equal(export_json.schema, STEAM_ACCESS_SCHEMA);
  assert.equal(export_json.source, STEAM_ACCESS_SOURCE);
  assert.equal(export_json.advisory_only, ADVISORY_ONLY);
  assert.equal(export_json.ranking_impact, RANKING_IMPACT);
  assert.equal(export_json.summary.advisory_only, ADVISORY_ONLY);
  assert.equal(export_json.summary.ranking_impact, RANKING_IMPACT);
};

const assert_no_forbidden_data = (export_json) => {
  const serialized = JSON.stringify(export_json);
  for (const pattern of FORBIDDEN_OUTPUT_PATTERNS) {
    assert.doesNotMatch(serialized, pattern);
  }
};

const fake_storage = (initial_state = {}) => ({
  state: { ...initial_state },
  calls: [],
  async get(key) {
    return { [key]: this.state[key] };
  },
  async set(record) {
    this.calls.push(record);
    Object.assign(this.state, record);
  },
});

test("valid fixture builds an advisory-only AppID export with deterministic filtering and deduplication", () => {
  // Arrange
  const fixture = read_fixture_json("valid.json");

  // Act
  const export_json = build_sanitized_steam_access_export(fixture, {
    generated_at: fixture.generated_at,
  });

  // Assert
  assert_export_contract(export_json);
  assert.equal(export_json.generated_at, GENERATED_AT);
  assert.deepEqual(export_json.owned_appids, ["10", "20", "30", "40", "50", "60"]);
  assert.deepEqual(export_json.family_shared_appids, ["70", "80", "100", "90"]);
  assert.deepEqual(export_json.wishlist_appids, ["110", "120"]);
  assert.deepEqual(export_json.summary, {
    owned_count: 6,
    family_shared_count: 4,
    wishlist_count: 2,
    advisory_only: true,
    ranking_impact: "none",
  });
});

test("empty fixture builds an empty advisory-only export without introducing noise", () => {
  // Arrange
  const fixture = read_fixture_json("empty.json");

  // Act
  const export_json = build_sanitized_steam_access_export(fixture, {
    generated_at: GENERATED_AT,
  });

  // Assert
  assert_export_contract(export_json);
  assert.deepEqual(export_json.owned_appids, []);
  assert.deepEqual(export_json.family_shared_appids, []);
  assert.deepEqual(export_json.wishlist_appids, []);
  assert.deepEqual(export_json.summary, {
    owned_count: 0,
    family_shared_count: 0,
    wishlist_count: 0,
    advisory_only: true,
    ranking_impact: "none",
  });
});

test("malformed fixture fails JSON parsing before sanitizer code can consume it", () => {
  // Arrange
  const fixture_text = read_fixture_text("malformed.json");

  // Act / Assert
  assert.throws(() => JSON.parse(fixture_text), SyntaxError);
});

test("non-object payloads are treated as empty input rather than exporting malformed data", () => {
  // Arrange
  const malformed_payload = ["10", { appid: "20" }];

  // Act
  const collections = sanitize_steam_access_input(malformed_payload);

  // Assert
  assert.deepEqual(collections, {
    owned_appids: [],
    family_shared_appids: [],
    wishlist_appids: [],
  });
});

test("sensitive-key fixture exports only AppIDs and excludes raw/session/profile/member data", () => {
  // Arrange
  const fixture = read_fixture_json("sensitive_keys.json");

  // Act
  const export_json = build_sanitized_steam_access_export(fixture, {
    generated_at: fixture.generated_at,
  });

  // Assert
  assert_export_contract(export_json);
  assert.deepEqual(export_json.owned_appids, ["10", "20"]);
  assert.deepEqual(export_json.family_shared_appids, ["30", "40"]);
  assert.deepEqual(export_json.wishlist_appids, ["50", "60"]);
  assert_no_forbidden_data(export_json);
  assert.deepEqual(Object.keys(export_json).sort(), [
    "advisory_only",
    "family_shared_appids",
    "generated_at",
    "owned_appids",
    "provenance",
    "ranking_impact",
    "schema",
    "source",
    "summary",
    "wishlist_appids",
  ]);
});

test("sensitive-key detection rejects prohibited names while allowing family_shared_appids", () => {
  // Arrange
  const prohibited_keys = [
    "cookies",
    "steamLoginSecure",
    "sessionid",
    "token",
    "request_headers",
    "raw_response",
    "raw_html",
    "email",
    "friends",
    "family_members",
    "profile",
    "member_name",
  ];

  // Act
  const decisions = prohibited_keys.map((key) => has_sensitive_key(key));

  // Assert
  assert.deepEqual(decisions, prohibited_keys.map(() => true));
  assert.equal(has_sensitive_key("family_shared_appids"), false);
  assert.equal(has_sensitive_key("owned_appids"), false);
  assert.equal(has_sensitive_key("wishlist_appids"), false);
});

test("collector adds and merges AppIDs deterministically across buckets", () => {
  // Arrange / Act
  const first = collector.add_appids_to_collector(
    {},
    "owned_appids",
    ["10", "20", "10", { appid: "30" }, "not-an-appid"],
    { updated_at: "2026-06-08T12:00:00Z" },
  );
  const second = collector.add_appids_to_collector(
    first,
    "family_shared_appids",
    [{ steam_appid: "40" }, { app_id: "50" }, "40"],
    { updated_at: "2026-06-08T12:01:00Z" },
  );
  const third = collector.add_appids_to_collector(
    second,
    "wishlist_appids",
    ["60", "70", "60"],
    { updated_at: "2026-06-08T12:02:00Z" },
  );

  // Assert
  assert.equal(third.schema, collector.COLLECTOR_SCHEMA);
  assert.deepEqual(third.owned_appids, ["10", "20", "30"]);
  assert.deepEqual(third.family_shared_appids, ["40", "50"]);
  assert.deepEqual(third.wishlist_appids, ["60", "70"]);
  assert.deepEqual(collector.collector_counts(third), {
    total_count: 7,
    owned_count: 3,
    family_shared_count: 2,
    wishlist_count: 2,
  });
  assert.equal(third.metadata.capture_count, 3);
  assert.equal(third.metadata.updated_at, "2026-06-08T12:02:00Z");
});

test("collector export preserves Steam Access contract and excludes sensitive data", () => {
  // Arrange
  const state = collector.normalize_collector_state({
    owned_appids: ["10", "10", "20"],
    family_shared_appids: ["30"],
    wishlist_appids: ["40"],
    session_token: "SECRET-LOCAL-SESSION",
    cookies: "SECRET-COOKIE",
    raw_html: "<html>secret</html>",
    profile_url: "https://steamcommunity.com/id/private",
    metadata: { capture_count: 2, updated_at: "2026-06-08T12:00:00Z" },
  });

  // Act
  const export_json = collector.build_collector_export(state, {
    generated_at: "2026-06-08T12:03:00Z",
  });

  // Assert
  assert_export_contract(export_json);
  assert.equal(export_json.generated_at, "2026-06-08T12:03:00Z");
  assert.deepEqual(export_json.owned_appids, ["10", "20"]);
  assert.deepEqual(export_json.family_shared_appids, ["30"]);
  assert.deepEqual(export_json.wishlist_appids, ["40"]);
  assert.deepEqual(export_json.summary, {
    owned_count: 2,
    family_shared_count: 1,
    wishlist_count: 1,
    advisory_only: true,
    ranking_impact: "none",
  });
  assert_no_forbidden_data(export_json);
});

test("collector handles empty and invalid input as empty AppID-only state", () => {
  // Arrange / Act
  const empty = collector.normalize_collector_state(["10", { appid: "20" }]);
  const invalid_bucket = collector.add_appids_to_collector(
    empty,
    "invalid_bucket",
    ["not-an-appid", 0, -1, null, undefined],
    { updated_at: "2026-06-08T12:04:00Z" },
  );
  const export_json = collector.build_collector_export(invalid_bucket, {
    generated_at: "2026-06-08T12:05:00Z",
  });

  // Assert
  assert.deepEqual(empty.owned_appids, []);
  assert.deepEqual(empty.family_shared_appids, []);
  assert.deepEqual(empty.wishlist_appids, []);
  assert.deepEqual(invalid_bucket.owned_appids, []);
  assert.deepEqual(collector.collector_counts(invalid_bucket), {
    total_count: 0,
    owned_count: 0,
    family_shared_count: 0,
    wishlist_count: 0,
  });
  assert_export_contract(export_json);
  assert.deepEqual(export_json.owned_appids, []);
  assert.deepEqual(export_json.family_shared_appids, []);
  assert.deepEqual(export_json.wishlist_appids, []);
});

test("collector storage writes only normalized AppID state and clear resets counts", async () => {
  // Arrange
  const storage = fake_storage();
  const dirty_state = {
    owned_appids: ["10", "10", { appid: "20" }],
    family_shared_appids: ["30"],
    wishlist_appids: ["40"],
    pairing_token: "SECRET-PAIRING",
    session_token: "SECRET-SESSION",
    headers: { Authorization: "Bearer SECRET" },
    metadata: { capture_count: 4, updated_at: "2026-06-08T12:06:00Z" },
  };

  // Act
  const saved = await collector.write_collector_state(dirty_state, storage);
  const read_back = await collector.read_collector_state(storage);
  const cleared = await collector.clear_collector_storage(storage, {
    updated_at: "2026-06-08T12:07:00Z",
  });

  // Assert
  assert.deepEqual(saved.owned_appids, ["10", "20"]);
  assert.deepEqual(read_back, saved);
  assert.equal(storage.calls.length, 2);
  assert.deepEqual(Object.keys(storage.calls[0]), [collector.COLLECTOR_STORAGE_KEY]);
  assert_no_forbidden_data(storage.calls[0][collector.COLLECTOR_STORAGE_KEY]);
  assert.deepEqual(cleared.owned_appids, []);
  assert.deepEqual(cleared.family_shared_appids, []);
  assert.deepEqual(cleared.wishlist_appids, []);
  assert.equal(collector.collector_counts(cleared).total_count, 0);
});

test("direct-send request builder is loopback-only with JSON and explicit token headers", () => {
  // Arrange / Act
  const pairing_request = service_worker.build_local_json_request(
    { pairing_token: "PAIR" },
    "PAIR",
    { pairing: true },
  );
  const import_request = service_worker.build_local_json_request(
    { schema: STEAM_ACCESS_SCHEMA },
    "SESSION",
  );

  // Assert
  assert.equal(service_worker.local_endpoint_url("/api/steam-access/import"), "http://127.0.0.1:8080/api/steam-access/import");
  assert.throws(() => service_worker.normalize_local_base_url("http://localhost:8080"), /127\.0\.0\.1/);
  assert.throws(() => service_worker.normalize_local_base_url("http://0.0.0.0:8080"), /127\.0\.0\.1/);
  assert.throws(() => service_worker.normalize_local_base_url("https://127.0.0.1:8080"), /127\.0\.0\.1/);
  assert.equal(pairing_request.method, "POST");
  assert.equal(pairing_request.credentials, "omit");
  assert.equal(pairing_request.headers["Content-Type"], "application/json");
  assert.equal(pairing_request.headers["X-Pairing-Token"], "PAIR");
  assert.equal(import_request.headers.Authorization, "Bearer SESSION");
});

test("service worker sends sanitized AppID-only body to import endpoint", async () => {
  // Arrange
  const fixture = read_fixture_json("sensitive_keys.json");
  const export_json = build_sanitized_steam_access_export(fixture, {
    generated_at: fixture.generated_at,
  });
  const calls = [];
  const original_fetch = global.fetch;
  global.fetch = async (url, request) => {
    calls.push({ url, request });
    return { ok: true, json: async () => ({ ok: true }) };
  };

  try {
    // Act
    await service_worker.send_steam_access_import(export_json, "SESSION", { base_url: "http://127.0.0.1:9876" });
  } finally {
    global.fetch = original_fetch;
  }

  // Assert
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://127.0.0.1:9876/api/steam-access/import");
  assert.equal(calls[0].request.headers.Authorization, "Bearer SESSION");
  const body = JSON.parse(calls[0].request.body);
  assert_export_contract(body);
  assert.deepEqual(body.owned_appids, ["10", "20"]);
  assert_no_forbidden_data(body);
});

test("popup direct-send remains explicit and copy/save fallback stays available", () => {
  // Arrange
  const popup_source = read_helper_text("popup.js");
  const popup_html = read_helper_text("popup.html");

  // Assert
  assert.match(popup_source, /pair_button\.addEventListener\("click", pair_local_app\)/);
  assert.match(popup_source, /send_button\.addEventListener\("click", send_direct_import\)/);
  assert.match(popup_source, /current_export_source !== "collector"/);
  assert.match(popup_source, /Export combined collector JSON before direct send/);
  assert.match(popup_source, /copy_button\.addEventListener\("click", copy_export\)/);
  assert.match(popup_source, /save_button\.addEventListener\("click", save_export\)/);
  assert.match(popup_source, /Copy\/Save remains available/);
  assert.match(popup_source, /URL\.createObjectURL/);
  assert.match(popup_source, /chrome\.runtime\.sendMessage/);
  assert.doesNotMatch(popup_source, /\bfetch\s*\(/);
  assert.match(popup_html, /Optional local direct send/);
  assert.match(popup_html, /Copy JSON/);
  assert.match(popup_html, /Save JSON/);
});
