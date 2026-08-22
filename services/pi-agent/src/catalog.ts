import {
  ModelRuntime,
} from "@earendil-works/pi-coding-agent";
import { InMemoryCredentialStore, type Model } from "@earendil-works/pi-ai";

export type PiCatalogProvider = {
  id: string;
  name: string;
  baseUrl?: string;
};

export type PiCatalogModel = {
  id: string;
  name: string;
  provider: string;
  api: string;
  baseUrl?: string;
  reasoning: boolean;
  input: string[];
  contextWindow: number;
  maxTokens: number;
  cost: {
    input: number;
    output: number;
    cacheRead: number;
    cacheWrite: number;
  };
};

export type PiModelCatalog = {
  source: "pi-ai";
  version: "0.84.2";
  providers: PiCatalogProvider[];
  models: PiCatalogModel[];
};

function numeric(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function publicModel(model: Model<any>): PiCatalogModel {
  return {
    id: model.id,
    name: model.name,
    provider: model.provider,
    api: String(model.api),
    baseUrl: model.baseUrl,
    reasoning: Boolean(model.reasoning),
    input: [...model.input],
    contextWindow: numeric(model.contextWindow),
    maxTokens: numeric(model.maxTokens),
    cost: {
      input: numeric(model.cost?.input),
      output: numeric(model.cost?.output),
      cacheRead: numeric(model.cost?.cacheRead),
      cacheWrite: numeric(model.cost?.cacheWrite),
    },
  };
}

export async function createPiModelCatalog(): Promise<PiModelCatalog> {
  // Catalog discovery must never need a provider key. Credentials are only
  // used by a later, user-scoped run after the API resolves its encrypted
  // provider configuration.
  const runtime = await ModelRuntime.create({
    credentials: new InMemoryCredentialStore(),
    modelsPath: null,
    refreshOnCreate: false,
  });
  return {
    source: "pi-ai",
    version: "0.84.2",
    providers: runtime.getProviders().map((provider) => ({
      id: provider.id,
      name: provider.name,
      baseUrl: provider.baseUrl,
    })),
    models: runtime.getModels().map((model) => publicModel(model as Model<any>)),
  };
}
