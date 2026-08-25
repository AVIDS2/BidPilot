import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckIcon,
  ChevronRightIcon,
  CircleDotIcon,
  ExternalLinkIcon,
  KeyRoundIcon,
  ListRestartIcon,
  NetworkIcon,
  PlusIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  Trash2Icon,
  WifiIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  createProviderConfig,
  deleteProviderConfig,
  getPiModelCatalog,
  getPiRuntimeContract,
  listProviderConfigs,
  listProviderModels,
  testProviderConnection,
  updateProviderConfig,
  type ProviderConfig,
  type ProviderConfigCreate,
  type ProviderModelInfo,
  type PiCatalogModel,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { ProviderBrandMark, type ProviderBrandId } from "@/features/settings/provider-brand-mark";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

import { SettingsNavigation } from "./settings-navigation";

type ProviderProtocol = "openai" | "anthropic";

type ProviderPreset = {
  id: string;
  label: string;
  providerType: ProviderProtocol;
  apiUrl: string;
  model: string;
  brand: ProviderBrandId;
};

const PROVIDER_PRESETS: ProviderPreset[] = [
  { id: "custom-openai", label: "Custom OpenAI-compatible", providerType: "openai", apiUrl: "", model: "gpt-4o", brand: "custom-openai" },
  { id: "openai", label: "OpenAI", providerType: "openai", apiUrl: "https://api.openai.com/v1", model: "gpt-4o", brand: "openai" },
  { id: "deepseek", label: "DeepSeek", providerType: "openai", apiUrl: "https://api.deepseek.com", model: "deepseek-v4-flash", brand: "deepseek" },
  { id: "deepseek-anthropic", label: "DeepSeek Claude protocol", providerType: "anthropic", apiUrl: "https://api.deepseek.com/anthropic", model: "deepseek-v4-flash", brand: "deepseek" },
  { id: "dashscope", label: "Alibaba Cloud Model Studio", providerType: "openai", apiUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus", brand: "dashscope" },
  { id: "doubao", label: "Volcengine Ark / Doubao", providerType: "openai", apiUrl: "https://ark.cn-beijing.volces.com/api/v3", model: "ep-xxxxxxxx", brand: "doubao" },
  { id: "anthropic", label: "Anthropic", providerType: "anthropic", apiUrl: "https://api.anthropic.com", model: "claude-sonnet-4-20250514", brand: "anthropic" },
  { id: "zhipu", label: "Zhipu GLM", providerType: "openai", apiUrl: "https://open.bigmodel.cn/api/paas/v4", model: "glm-4-flash", brand: "zhipu" },
  { id: "minimax", label: "MiniMax", providerType: "openai", apiUrl: "https://api.minimax.io/v1", model: "MiniMax-M3", brand: "minimax" },
  { id: "siliconflow", label: "SiliconFlow", providerType: "openai", apiUrl: "https://api.siliconflow.cn/v1", model: "deepseek-ai/DeepSeek-V3", brand: "siliconflow" },
  { id: "openrouter", label: "OpenRouter", providerType: "openai", apiUrl: "https://openrouter.ai/api/v1", model: "openai/gpt-4o-mini", brand: "openrouter" },
  { id: "opencode-go", label: "OpenCode Go", providerType: "openai", apiUrl: "https://opencode.ai/zen/go/v1", model: "deepseek-v4-flash", brand: "custom-openai" },
  { id: "mimo", label: "Xiaomi MiMo", providerType: "openai", apiUrl: "https://api.xiaomimimo.com/v1", model: "mimo-v2.5-pro", brand: "mimo" },
  { id: "custom-anthropic", label: "Custom Claude Messages", providerType: "anthropic", apiUrl: "", model: "claude-sonnet-4-20250514", brand: "custom-anthropic" },
];

const EMPTY_PROVIDERS: ProviderConfig[] = [];

type ProviderForm = {
  providerType: ProviderProtocol;
  providerId: string;
  label: string;
  apiKey: string;
  apiUrl: string;
  model: string;
  isActive: boolean;
};

function defaultForm(): ProviderForm {
  const preset = PROVIDER_PRESETS[0];
  return {
    providerType: preset.providerType,
    providerId: preset.id,
    label: "",
    apiKey: "",
    apiUrl: preset.apiUrl,
    model: preset.model,
    isActive: false,
  };
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function findPreset(providerId: string, providerType: ProviderProtocol): ProviderPreset {
  return PROVIDER_PRESETS.find((preset) => preset.id === providerId)
    ?? PROVIDER_PRESETS.find((preset) => preset.providerType === providerType && preset.id.startsWith("custom"))
    ?? PROVIDER_PRESETS[0];
}

function protocolLabel(value: ProviderProtocol) {
  return value === "anthropic" ? "Claude Messages" : "OpenAI-compatible";
}

export function ProviderSettingsPage() {
  const queryClient = useQueryClient();
  const providersQuery = useQuery({ queryKey: ["provider-configs"], queryFn: listProviderConfigs });
  const piCatalogQuery = useQuery({ queryKey: ["pi-model-catalog"], queryFn: getPiModelCatalog, staleTime: 60 * 60 * 1000 });
  const piRuntimeQuery = useQuery({ queryKey: ["pi-runtime-contract"], queryFn: getPiRuntimeContract, staleTime: 5 * 60 * 1000 });
  const providers = providersQuery.data?.data ?? EMPTY_PROVIDERS;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<ProviderForm>(defaultForm);
  const [availableModels, setAvailableModels] = useState<ProviderModelInfo[]>([]);
  const [resultMessage, setResultMessage] = useState<string | null>(null);

  const selectedProvider = providers.find((provider) => provider.id === selectedId) ?? null;
  const selectedPreset = useMemo(
    () => findPreset(form.providerId, form.providerType),
    [form.providerId, form.providerType],
  );
  const piModels = useMemo(() => {
    const catalog = piCatalogQuery.data?.data;
    if (!catalog) return [];
    const providerAliases: Record<string, string[]> = {
      mimo: ["mimo", "xiaomi"],
      "custom-openai": [],
      "custom-anthropic": [],
    };
    const providerIds = providerAliases[form.providerId] ?? [form.providerId];
    return catalog.models.filter((model) => providerIds.includes(model.provider));
  }, [form.providerId, piCatalogQuery.data]);

  const replaceForm = (provider: ProviderConfig | null) => {
    if (!provider) {
      setForm(defaultForm());
      setAvailableModels([]);
      setResultMessage(null);
      return;
    }

    setForm({
      providerType: provider.provider_type,
      providerId: provider.provider_id || findPreset("", provider.provider_type).id,
      label: provider.label,
      apiKey: "",
      apiUrl: provider.api_url ?? "",
      model: provider.model,
      isActive: provider.is_active,
    });
    setAvailableModels([]);
    setResultMessage(null);
  };

  useEffect(() => {
    if (selectedId && providers.some((provider) => provider.id === selectedId)) return;
    const next = providers[0] ?? null;
    setSelectedId(next?.id ?? null);
    replaceForm(next);
  }, [providers, selectedId]);

  const createMutation = useMutation({
    mutationFn: (payload: ProviderConfigCreate) => createProviderConfig(payload),
    onSuccess: (response) => {
      queryClient.setQueryData<{ data: ProviderConfig[] }>(["provider-configs"], (current) => ({
        data: [response.data, ...(current?.data ?? []).filter((provider) => provider.id !== response.data.id)],
      }));
      queryClient.invalidateQueries({ queryKey: ["provider-configs"] });
      setSelectedId(response.data.id);
      replaceForm(response.data);
      toast.success("提供商配置已保存。");
    },
    onError: (error) => toast.error(errorMessage(error, "无法保存提供商配置。")),
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<ProviderConfigCreate> }) => updateProviderConfig(id, payload),
    onSuccess: (response) => {
      queryClient.setQueryData<{ data: ProviderConfig[] }>(["provider-configs"], (current) => ({
        data: (current?.data ?? []).map((provider) => provider.id === response.data.id ? response.data : provider),
      }));
      queryClient.invalidateQueries({ queryKey: ["provider-configs"] });
      setSelectedId(response.data.id);
      replaceForm(response.data);
      toast.success("提供商配置已更新。");
    },
    onError: (error) => toast.error(errorMessage(error, "无法更新提供商配置。")),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteProviderConfig,
    onSuccess: (_, deletedId) => {
      queryClient.setQueryData<{ data: ProviderConfig[] }>(["provider-configs"], (current) => ({
        data: (current?.data ?? []).filter((provider) => provider.id !== deletedId),
      }));
      queryClient.invalidateQueries({ queryKey: ["provider-configs"] });
      setSelectedId(null);
      replaceForm(null);
      toast.success("提供商配置已删除。");
    },
    onError: (error) => toast.error(errorMessage(error, "无法删除提供商配置。")),
  });
  const testMutation = useMutation({
    mutationFn: () => {
      if (selectedProvider && !form.apiKey.trim()) {
        return testProviderConnection({ config_id: selectedProvider.id });
      }
      return testProviderConnection({
        provider_type: form.providerType,
        provider_id: form.providerId,
        api_key: form.apiKey.trim(),
        api_url: form.apiUrl.trim() || undefined,
        model: form.model.trim(),
      });
    },
    onSuccess: (response) => {
      const result = response.data;
      setResultMessage(result.message);
      if (result.success) toast.success("连接测试通过。");
      else toast.error(result.message || "连接测试未通过。");
    },
    onError: (error) => {
      const message = errorMessage(error, "连接测试未能完成。");
      setResultMessage(message);
      toast.error(message);
    },
  });
  const modelsMutation = useMutation({
    mutationFn: () => {
      if (selectedProvider && !form.apiKey.trim()) return listProviderModels({ config_id: selectedProvider.id });
      return listProviderModels({
        provider_type: form.providerType,
        provider_id: form.providerId,
        api_key: form.apiKey.trim(),
        api_url: form.apiUrl.trim() || undefined,
      });
    },
    onSuccess: (response) => {
      const result = response.data;
      setAvailableModels(result.models);
      setResultMessage(result.message ?? (result.models.length ? `发现 ${result.models.length} 个可用模型。` : "未返回可发现的模型。"));
      if (result.models.length) toast.success(`已发现 ${result.models.length} 个模型。`);
    },
    onError: (error) => {
      const message = errorMessage(error, "模型发现未能完成。");
      setResultMessage(message);
      toast.error(message);
    },
  });

  const isSaving = createMutation.isPending || updateMutation.isPending;

  const chooseProvider = (provider: ProviderConfig) => {
    setSelectedId(provider.id);
    replaceForm(provider);
  };

  const createNew = () => {
    setSelectedId(null);
    replaceForm(null);
  };

  const applyPreset = (providerId: string) => {
    const preset = findPreset(providerId, form.providerType);
    setForm((current) => ({
      ...current,
      providerType: preset.providerType,
      providerId: preset.id,
      apiUrl: preset.apiUrl,
      model: preset.model,
      label: current.label || preset.label,
    }));
    setAvailableModels([]);
    setResultMessage(null);
  };

  const save = () => {
    if (!form.label.trim()) {
      toast.error("请填写配置名称。");
      return;
    }
    if (!form.model.trim()) {
      toast.error("请填写模型名称或 Endpoint ID。");
      return;
    }
    if (!selectedProvider && !form.apiKey.trim()) {
      toast.error("创建配置需要 API Key。");
      return;
    }

    const payload: ProviderConfigCreate = {
      provider_type: form.providerType,
      provider_id: form.providerId,
      label: form.label.trim(),
      api_key: form.apiKey.trim(),
      api_url: form.apiUrl.trim() || undefined,
      model: form.model.trim(),
      is_active: form.isActive,
    };

    if (selectedProvider) {
      const updatePayload: Partial<ProviderConfigCreate> = { ...payload };
      if (!updatePayload.api_key) delete updatePayload.api_key;
      updateMutation.mutate({ id: selectedProvider.id, payload: updatePayload });
      return;
    }
    createMutation.mutate(payload);
  };

  const canCallProvider = Boolean(selectedProvider || form.apiKey.trim());

  return (
    <section className="wb-settings-page" aria-labelledby="providers-title">
      <SettingsNavigation />

      <main className="wb-settings-main">
      <div className="wb-settings-content">
        <header className="wb-settings-content-head">
          <div>
            <p className="wb-settings-eyebrow">工作区设置</p>
            <h1 id="providers-title">集成与模型</h1>
            <p>为 Agent 与响应工作流保存可测试的模型连接。密钥只会加密保存，之后不会在浏览器中回显。</p>
          </div>
          <Button onClick={createNew} size="sm" type="button"><PlusIcon data-icon="inline-start" />新建配置</Button>
        </header>

        <section className="wb-provider-configurations" aria-label="已保存配置">
          <div className="wb-provider-configurations-head"><span>已保存配置</span><small>{providers.length}</small></div>
          {providersQuery.isLoading ? <p className="wb-list-loading">正在读取配置…</p> : null}
          {!providersQuery.isLoading && providers.length === 0 ? <p className="wb-provider-empty">还没有保存的模型提供商。新建一条配置后，可在 Agent 中选择并测试它。</p> : null}
          <div className="wb-provider-configurations-list">
            {providers.map((provider) => {
              const preset = findPreset(provider.provider_id, provider.provider_type);
              return (
                <Button
                  className={cn("wb-provider-configuration", selectedProvider?.id === provider.id && "is-selected")}
                  key={provider.id}
                  onClick={() => chooseProvider(provider)}
                  size="sm"
                  type="button"
                  variant="ghost"
                >
                  <ProviderBrandMark brand={preset.brand} className="size-5 rounded-[4px] shadow-none" label={provider.label} />
                  <span><strong>{provider.label}</strong><small>{provider.model}</small></span>
                  {provider.is_active ? <CheckIcon aria-label="当前启用" /> : null}
                </Button>
              );
            })}
          </div>
        </section>

        {piRuntimeQuery.data?.data ? (
          <PiRuntimeSummary contract={piRuntimeQuery.data.data} />
        ) : null}

        <article className="wb-provider-editor">
          <header className="wb-provider-editor-head">
            <div className="wb-provider-editor-title">
              <ProviderBrandMark brand={selectedPreset.brand} className="size-9 rounded-[6px] shadow-none" label={selectedPreset.label} />
              <div>
                <h3>{selectedProvider ? selectedProvider.label : "新建提供商配置"}</h3>
                <p>{selectedProvider ? `${protocolLabel(selectedProvider.provider_type)} · ${selectedProvider.model}` : "选择接入方式，再填写该服务端要求的连接信息。"}</p>
              </div>
            </div>
            {selectedProvider ? (
              <Button
                disabled={deleteMutation.isPending}
                onClick={() => { if (window.confirm(`删除「${selectedProvider.label}」吗？此操作无法恢复。`)) deleteMutation.mutate(selectedProvider.id); }}
                size="sm"
                type="button"
                variant="ghost"
              ><Trash2Icon data-icon="inline-start" />删除</Button>
            ) : null}
          </header>

          <FieldGroup className="wb-provider-fields">
            <div className="wb-provider-fields-row">
              <Field><FieldLabel>提供商预设</FieldLabel><Select onValueChange={(value) => { if (value) applyPreset(value); }} value={form.providerId}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectLabel>可用预设</SelectLabel>{PROVIDER_PRESETS.map((preset) => <SelectItem key={preset.id} value={preset.id}>{preset.label}</SelectItem>)}</SelectGroup></SelectContent></Select></Field>
              <Field><FieldLabel>接口协议</FieldLabel><Select onValueChange={(value) => { if (value) setForm((current) => ({ ...current, providerType: value as ProviderProtocol })); }} value={form.providerType}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="openai">OpenAI-compatible</SelectItem><SelectItem value="anthropic">Claude Messages</SelectItem></SelectGroup></SelectContent></Select></Field>
            </div>
            <div className="wb-provider-fields-row">
              <Field><FieldLabel htmlFor="provider-label">配置名称</FieldLabel><Input id="provider-label" onChange={(event) => setForm((current) => ({ ...current, label: event.target.value }))} placeholder="例如：团队 DeepSeek" value={form.label} /></Field>
              <Field><FieldLabel htmlFor="provider-model">模型名称 / Endpoint ID</FieldLabel><Input id="provider-model" list="wb-provider-models" onChange={(event) => setForm((current) => ({ ...current, model: event.target.value }))} value={form.model} /><datalist id="wb-provider-models">{availableModels.map((model) => <option key={model.id} value={model.id}>{model.name ?? model.owned_by ?? model.id}</option>)}</datalist></Field>
            </div>
            <PiCatalogPicker
              loading={piCatalogQuery.isLoading}
              models={piModels}
              onSelect={(model) => setForm((current) => ({ ...current, model: model.id, apiUrl: current.apiUrl || model.base_url || "" }))}
              providerId={form.providerId}
              version={piCatalogQuery.data?.data.version}
            />
            <Field><FieldLabel htmlFor="provider-url">Base URL / endpoint</FieldLabel><Input id="provider-url" onChange={(event) => setForm((current) => ({ ...current, apiUrl: event.target.value }))} placeholder="由预设带入，也可填写自定义网关地址" value={form.apiUrl} /></Field>
            <Field><FieldLabel htmlFor="provider-api-key">{selectedProvider ? "替换 API Key" : "API Key"}</FieldLabel><Input autoComplete="off" id="provider-api-key" onChange={(event) => setForm((current) => ({ ...current, apiKey: event.target.value }))} placeholder={selectedProvider ? "已加密保存；仅在需要更换时填写" : "仅用于本次保存，不会显示或写入浏览器存储"} type="password" value={form.apiKey} /><FieldDescription>{selectedProvider ? "留空会保留现有密钥。" : "新建配置时需要提供密钥。"}</FieldDescription></Field>
          </FieldGroup>

          <div className="wb-provider-active-setting">
            <div><CircleDotIcon aria-hidden="true" /><span><strong>作为当前启用配置</strong><small>同一协议下，只会使用一条启用配置。</small></span></div>
            <Switch checked={form.isActive} onCheckedChange={(checked) => setForm((current) => ({ ...current, isActive: checked }))} />
          </div>

          <div className="wb-provider-actions">
            <Button disabled={isSaving} onClick={save} type="button">{isSaving ? <RefreshCwIcon className="wb-spin-icon" data-icon="inline-start" /> : <CheckIcon data-icon="inline-start" />}{isSaving ? "保存中…" : "保存配置"}</Button>
            <Button disabled={!canCallProvider || testMutation.isPending || !form.model.trim()} onClick={() => testMutation.mutate()} type="button" variant="outline">{testMutation.isPending ? <RefreshCwIcon className="wb-spin-icon" data-icon="inline-start" /> : <WifiIcon data-icon="inline-start" />}测试连接</Button>
            <Button disabled={!canCallProvider || modelsMutation.isPending} onClick={() => modelsMutation.mutate()} type="button" variant="ghost">{modelsMutation.isPending ? <RefreshCwIcon className="wb-spin-icon" data-icon="inline-start" /> : <ListRestartIcon data-icon="inline-start" />}获取模型列表</Button>
          </div>

          {resultMessage ? <p className="wb-provider-result"><ChevronRightIcon aria-hidden="true" /> {resultMessage}</p> : null}
          {availableModels.length > 0 ? (
            <section className="wb-provider-model-results" aria-label="发现的模型">
              <div className="wb-section-heading-row"><h3 className="wb-section-heading">可用模型</h3><span>{availableModels.length}</span></div>
              {availableModels.slice(0, 50).map((model) => <Button key={model.id} onClick={() => setForm((current) => ({ ...current, model: model.id }))} type="button" variant="ghost"><KeyRoundIcon data-icon="inline-start" /><span>{model.name ?? model.id}</span><small>{model.id}</small></Button>)}
            </section>
          ) : null}
          <a className="wb-provider-doc-link" href="https://platform.openai.com/docs/api-reference" rel="noreferrer" target="_blank">查看 OpenAI-compatible 接口说明 <ExternalLinkIcon aria-hidden="true" /></a>
        </article>
      </div>
      </main>
    </section>
  );
}

function PiRuntimeSummary({
  contract,
}: {
  contract: Awaited<ReturnType<typeof getPiRuntimeContract>>["data"];
}) {
  const sandbox = contract.sandbox;
  const mcpServers = contract.mcp_servers ?? [];
  return (
    <section className="wb-pi-runtime" aria-label="Pi Agent 运行边界">
      <div className="wb-pi-runtime-heading">
        <ShieldCheckIcon aria-hidden="true" />
        <span><strong>Pi Agent 运行边界</strong><small>由服务端托管，浏览器无法扩大权限</small></span>
      </div>
      <dl>
        <div><dt>沙箱</dt><dd>{sandbox.profile === "governed_cloud" ? "受治理云环境" : sandbox.profile}</dd></div>
        <div><dt>主机工具</dt><dd>{sandbox.hostTools === "disabled" ? "关闭" : sandbox.hostTools}</dd></div>
        <div><dt>网络</dt><dd><NetworkIcon aria-hidden="true" />{sandbox.network === "bridge_only" ? "仅业务桥接" : sandbox.network}</dd></div>
        <div><dt>能力</dt><dd>{contract.tool_count} 个工具 · {contract.skills.length} 个技能 · {contract.parallel_tool_count} 个可并行</dd></div>
      </dl>
      <p>{contract.extensions.join(" · ")}</p>
      <details className="wb-pi-runtime-details">
        <summary>查看已注册资源</summary>
        <div className="wb-pi-runtime-resource-list">
          <strong>Skills · {contract.skills.length}</strong>
          {contract.skills.map((skill) => (
            <span key={skill.name}>{skill.name}{skill.version ? ` · v${skill.version}` : ""}{skill.resources?.length ? ` · ${skill.resources.length} 个资源` : ""}</span>
          ))}
          <strong>MCP · {mcpServers.length}</strong>
          {mcpServers.length === 0 ? <span>未配置 MCP server</span> : mcpServers.map((server) => <span key={server.name}>{server.name} · {server.transport}</span>)}
        </div>
      </details>
    </section>
  );
}

function PiCatalogPicker({
  loading,
  models,
  onSelect,
  providerId,
  version,
}: {
  loading: boolean;
  models: PiCatalogModel[];
  onSelect: (model: PiCatalogModel) => void;
  providerId: string;
  version?: string;
}) {
  if (loading) return <p className="wb-provider-catalog-note">正在读取 Pi 原生模型目录…</p>;
  if (models.length === 0) {
    return (
      <p className="wb-provider-catalog-note">
        {providerId.startsWith("custom-") ? "自定义网关使用手动模型名称。" : "Pi 目录未列出该提供商的模型，仍可手动填写。"}
      </p>
    );
  }
  return (
    <section className="wb-provider-catalog" aria-label="Pi 原生模型目录">
      <div><strong>Pi 原生模型目录</strong><small>pi-ai {version} · {models.length} 个模型</small></div>
      <div className="wb-provider-catalog-list">
        {models.slice(0, 12).map((model) => (
          <Button
            key={`${model.provider}:${model.id}`}
            onClick={() => onSelect(model)}
            title={`${model.name} · ${model.context_window.toLocaleString()} context${model.reasoning ? " · reasoning" : ""}`}
            type="button"
            variant="ghost"
          >
            <span>{model.name}</span>
            <small>{model.reasoning ? "推理" : model.api}</small>
          </Button>
        ))}
      </div>
    </section>
  );
}
