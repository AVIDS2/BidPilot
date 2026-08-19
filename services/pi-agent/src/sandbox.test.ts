import assert from "node:assert/strict";
import { test } from "node:test";
import { TRUSTED_PI_EXTENSIONS, trustedCloudExtension } from "./extensions/registry.js";
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

test("cloud extension admission is first-party and build-time only", () => {
  assert.deepEqual(Object.keys(TRUSTED_PI_EXTENSIONS).sort(), [
    "bidpilot-governance",
    "bidpilot-skills",
    "bidpilot-subagents",
  ]);
  for (const descriptor of Object.values(TRUSTED_PI_EXTENSIONS)) {
    assert.equal(descriptor.source, "first_party");
    assert.equal(descriptor.deployment, "governed_cloud");
    assert.equal(Number.isInteger(descriptor.version), true);
  }
  assert.equal(trustedCloudExtension("npm:@tintinweb/pi-subagents"), undefined);
  assert.equal(trustedCloudExtension("../../tenant-extension.ts"), undefined);
});
