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
