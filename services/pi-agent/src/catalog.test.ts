import assert from "node:assert/strict";
import test from "node:test";

import { createPiModelCatalog } from "./catalog.js";

test("pi-ai catalog exposes public provider and model metadata without credentials", async () => {
  const catalog = await createPiModelCatalog();

  assert.equal(catalog.source, "pi-ai");
  assert.ok(catalog.providers.length > 10);
  assert.ok(catalog.models.length > 100);
  const deepseek = catalog.models.find((model) => model.provider === "deepseek");
  assert.ok(deepseek);
  assert.equal(typeof deepseek.contextWindow, "number");
  assert.equal("apiKey" in deepseek, false);
});
