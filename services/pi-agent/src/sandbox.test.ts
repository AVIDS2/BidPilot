import assert from "node:assert/strict";
import { test } from "node:test";
import { buildSkillCatalogBlock } from "./sandbox.js";

test("skill catalog is progressive metadata and escapes untrusted descriptions", () => {
  const block = buildSkillCatalogBlock([
    { name: "tender-research", description: "Research <public> opportunities & cite sources." },
  ]);

  assert.match(block, /<name>tender-research<\/name>/);
  assert.match(block, /&lt;public&gt;/);
  assert.match(block, /call read_skill/);
  assert.equal(block.includes("Research <public>"), false);
});

test("invalid skill names cannot enter the Pi system prompt", () => {
  assert.throws(
    () => buildSkillCatalogBlock([{ name: "../escape", description: "invalid" }]),
    /Invalid skill name/,
  );
});
