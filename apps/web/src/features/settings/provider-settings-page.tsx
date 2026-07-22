import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listProviderConfigs,
  createProviderConfig,
  updateProviderConfig,
  deleteProviderConfig,
  testProviderConnection,
  listProviderModels,
  type ProviderConfig,
  type ProviderConfigCreate,
  type ProviderModelInfo,
} from "@/lib/api";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { ProviderBrandMark, type ProviderBrandId } from "./provider-brand-mark";
import { ProductElectricFrame, ProductGlareCard, ProductReveal, ProductShinyText } from "@/components/reactbits-product";
import {
  Plus,
  Search,
  Trash2,
  Wifi,
  Settings2,
  KeyRound,
  CheckCircle2,
  Circle,
  Pencil,
  Cpu,
  Star,
  ListTree,
} from "lucide-react";
import { cn } from "@/lib/utils";

type ProviderProtocol = "openai" | "anthropic";

const DEFAULT_MODELS: Record<string, string> = {
  openai: "gpt-4o",
  anthropic: "claude-sonnet-4-20250514",
};

const PROTOCOL_LABELS: Record<ProviderProtocol, string> = {
  openai: "OpenAI 兼容",
  anthropic: "Claude Messages",
};

type ProviderPreset = {
  id: string;
  label: string;
  providerType: ProviderProtocol;
  apiUrl: string;
  model: string;
  description: string;
  brand: ProviderBrandId;
  recommended?: boolean;
  modelHint?: string;
  docsUrl?: string;
};

const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    id: "custom-openai",
    label: "自定义配置",
    providerType: "openai",
    apiUrl: "",
    model: "gpt-4o",
    description: "接入任何 OpenAI 兼容服务、企业网关或你自己的代理地址。",
    brand: "custom-openai",
    modelHint: "按供应商模型名填写",
  },
  {
    id: "openai",
    label: "OpenAI Official",
    providerType: "openai",
    apiUrl: "https://api.openai.com/v1",
    model: "gpt-4o",
    description: "ChatGPT 背后的 OpenAI 官方 API，适合 GPT 系列模型。",
    brand: "openai",
    docsUrl: "https://platform.openai.com/docs/api-reference/chat/create",
    recommended: true,
  },
  {
    id: "deepseek",
    label: "DeepSeek",
    providerType: "openai",
    apiUrl: "https://api.deepseek.com",
    model: "deepseek-v4-flash",
    description: "DeepSeek 官方 OpenAI 兼容 API，支持 V4 Flash、V4 Pro 与推理模型。",
    brand: "deepseek",
    docsUrl: "https://api-docs.deepseek.com/",
    recommended: true,
  },
  {
    id: "deepseek-anthropic",
    label: "DeepSeek Claude 协议",
    providerType: "anthropic",
    apiUrl: "https://api.deepseek.com/anthropic",
    model: "deepseek-v4-flash",
    description: "DeepSeek 官方 Anthropic Messages 兼容端点，适合 Claude 协议客户端。",
    brand: "deepseek",
    docsUrl: "https://api-docs.deepseek.com/guides/anthropic_api",
    recommended: true,
  },
  {
    id: "dashscope",
    label: "阿里云百炼",
    providerType: "openai",
    apiUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-plus",
    description: "阿里云百炼 Model Studio，适合通义千问 Qwen 系列模型。",
    brand: "dashscope",
    docsUrl: "https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope",
    recommended: true,
  },
  {
    id: "doubao",
    label: "火山方舟 / 豆包",
    providerType: "openai",
    apiUrl: "https://ark.cn-beijing.volces.com/api/v3",
    model: "ep-xxxxxxxx",
    description: "火山方舟承载豆包模型，模型栏通常填写你的 Endpoint ID。",
    brand: "doubao",
    docsUrl: "https://www.volcengine.com/docs/82379",
    recommended: true,
  },
  {
    id: "anthropic",
    label: "Claude Official",
    providerType: "anthropic",
    apiUrl: "https://api.anthropic.com",
    model: "claude-sonnet-4-20250514",
    description: "Anthropic 官方 Claude API，适合 Claude Sonnet 与 Opus。",
    brand: "anthropic",
    docsUrl: "https://docs.anthropic.com/en/api/messages",
    recommended: true,
  },
  {
    id: "zhipu",
    label: "智谱 GLM",
    providerType: "openai",
    apiUrl: "https://open.bigmodel.cn/api/paas/v4",
    model: "glm-4-flash",
    description: "智谱 AI 开放平台，适合 GLM 系列模型。",
    brand: "zhipu",
    docsUrl: "https://docs.bigmodel.cn/",
  },
  {
    id: "minimax",
    label: "MiniMax",
    providerType: "openai",
    apiUrl: "https://api.minimax.io/v1",
    model: "MiniMax-M3",
    description: "MiniMax 官方模型接口，适合 M 系列长上下文与 Agent 任务。",
    brand: "minimax",
    docsUrl: "https://platform.minimaxi.com/document/",
  },
  {
    id: "siliconflow",
    label: "SiliconFlow",
    providerType: "openai",
    apiUrl: "https://api.siliconflow.cn/v1",
    model: "deepseek-ai/DeepSeek-V3",
    description: "硅基流动模型云，适合 DeepSeek、Qwen 等开源模型。",
    brand: "siliconflow",
    docsUrl: "https://docs.siliconflow.cn/api-reference/chat-completions/chat-completions",
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    providerType: "openai",
    apiUrl: "https://openrouter.ai/api/v1",
    model: "openai/gpt-4o-mini",
    description: "统一接入多家模型市场，适合快速切换模型。",
    brand: "openrouter",
    docsUrl: "https://openrouter.ai/docs/api-reference/overview",
  },
  {
    id: "mimo",
    label: "Xiaomi MiMo",
    providerType: "openai",
    apiUrl: "https://api.xiaomimimo.com/v1",
    model: "mimo-v2.5-pro",
    description: "小米 MiMo API 开放平台，支持 OpenAI 兼容格式。",
    brand: "mimo",
    docsUrl: "https://mimo.mi.com/",
  },
  {
    id: "custom-anthropic",
    label: "Claude 协议自定义",
    providerType: "anthropic",
    apiUrl: "",
    model: "claude-sonnet-4-20250514",
    description: "接入 Anthropic Messages 兼容网关，适合 Claude 代理或企业网关。",
    brand: "custom-anthropic",
  },
];

function maskApiKey(key: string): string {
  if (key.length <= 8) return "****";
  return key.slice(0, 3) + "****" + key.slice(-4);
}

function ProviderSettingsSkeleton() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-80 mt-2" />
      </div>
      <Separator />
      <div className="flex justify-between items-center">
        <Skeleton className="h-10 w-32" />
      </div>
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 18rem), 1fr))" }}
      >
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-32" />
            </CardHeader>
            <CardContent className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-36" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export function ProviderSettingsPage() {
  const { t } = useTranslation("settings");
  const qc = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ProviderConfig | null>(null);

  // Form state
  const [formProviderType, setFormProviderType] = useState<ProviderProtocol>("openai");
  const [formProviderId, setFormProviderId] = useState<string>("custom-openai");
  const [formLabel, setFormLabel] = useState("");
  const [formApiKey, setFormApiKey] = useState("");
  const [formApiUrl, setFormApiUrl] = useState("");
  const [formModel, setFormModel] = useState("");
  const [formIsActive, setFormIsActive] = useState(false);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [providerPresetQuery, setProviderPresetQuery] = useState("");
  const [availableModels, setAvailableModels] = useState<ProviderModelInfo[]>([]);

  // Test connection state
  const [testingId, setTestingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["provider-configs"],
    queryFn: () => listProviderConfigs(),
  });

  const createMut = useMutation({
    mutationFn: (payload: ProviderConfigCreate) => createProviderConfig(payload),
    onSuccess: () => {
      toast.success(t("toast.created"));
      qc.invalidateQueries({ queryKey: ["provider-configs"] });
      setIsDialogOpen(false);
      resetForm();
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<ProviderConfigCreate> }) =>
      updateProviderConfig(id, payload),
    onSuccess: () => {
      toast.success(t("toast.updated"));
      qc.invalidateQueries({ queryKey: ["provider-configs"] });
      setIsDialogOpen(false);
      resetForm();
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteProviderConfig(id),
    onSuccess: () => {
      toast.success(t("toast.deleted"));
      qc.invalidateQueries({ queryKey: ["provider-configs"] });
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const testMut = useMutation({
    mutationFn: (payload: Parameters<typeof testProviderConnection>[0]) =>
      testProviderConnection(payload),
    onSuccess: (result) => {
      if (result.data.success) {
        toast.success(t("toast.connectionSuccess", { message: result.data.message }));
      } else {
        toast.error(t("toast.connectionFailed", { message: result.data.message }));
      }
    },
    onError: (err: Error) => {
      toast.error(t("toast.testFailed", { message: err.message }));
    },
  });

  const listModelsMut = useMutation({
    mutationFn: (payload: Parameters<typeof listProviderModels>[0]) =>
      listProviderModels(payload),
    onSuccess: (result) => {
      const models = result.data.models;
      setAvailableModels(models);
      if (result.data.discovery_mode !== "supported" && result.data.message) {
        toast.message(result.data.message);
      } else if (models.length > 0) {
        toast.success(t("toast.modelsLoaded", { count: models.length }));
      } else {
        toast.message(t("toast.modelsEmpty"));
      }
    },
    onError: (err: Error) => {
      toast.error(t("toast.modelsFailed", { message: err.message }));
    },
  });

  const setActiveMut = useMutation({
    mutationFn: (id: string) => updateProviderConfig(id, { is_active: true }),
    onSuccess: () => {
      toast.success(t("toast.activeUpdated"));
      qc.invalidateQueries({ queryKey: ["provider-configs"] });
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const providers = data?.data ?? [];
  const isSaving = createMut.isPending || updateMut.isPending;
  const visibleProviderPresets = PROVIDER_PRESETS.filter((preset) => {
    const query = providerPresetQuery.trim().toLowerCase();
    if (!query) return true;

    return [
      preset.label,
      preset.description,
      preset.model,
      preset.apiUrl,
      preset.providerType,
    ].some((value) => value.toLowerCase().includes(query));
  });

  function resetForm() {
    setFormProviderType("openai");
    setFormProviderId("custom-openai");
    setFormLabel("");
    setFormApiKey("");
    setFormApiUrl("");
    setFormModel(DEFAULT_MODELS.openai);
    setFormIsActive(false);
    setSelectedPresetId(null);
    setProviderPresetQuery("");
    setAvailableModels([]);
  }

  function applyPreset(presetId: string) {
    const preset = PROVIDER_PRESETS.find((item) => item.id === presetId);
    if (!preset) return;

    setSelectedPresetId(preset.id);
    setFormProviderType(preset.providerType);
    setFormProviderId(preset.id);
    setFormApiUrl(preset.apiUrl);
    setFormModel(preset.model);
    setAvailableModels([]);
    if (!editingProvider || !formLabel.trim()) {
      setFormLabel(preset.label);
    }
  }

  function handleAddProvider() {
    setEditingProvider(null);
    resetForm();
    setIsDialogOpen(true);
  }

  function handleEditProvider(provider: ProviderConfig) {
    setEditingProvider(provider);
    setFormProviderType(provider.provider_type);
    setFormProviderId(provider.provider_id || (provider.provider_type === "anthropic" ? "custom-anthropic" : "custom-openai"));
    setFormLabel(provider.label);
    setFormApiKey("");
    setFormApiUrl(provider.api_url ?? "");
    setFormModel(provider.model);
    setFormIsActive(provider.is_active);
    setSelectedPresetId(null);
    setProviderPresetQuery("");
    setAvailableModels([]);
    setIsDialogOpen(true);
  }

  function handleDeleteProvider(provider: ProviderConfig) {
    if (window.confirm(t("confirmDelete", { label: provider.label }))) {
      deleteMut.mutate(provider.id);
    }
  }

  function handleTestConnection(provider: ProviderConfig) {
    setTestingId(provider.id);
    testMut.mutate(
      { config_id: provider.id },
      {
        onSettled: () => setTestingId(null),
      },
    );
  }

  function handleSave() {
    if (!formLabel.trim()) {
      toast.error(t("toast.labelRequired"));
      return;
    }
    if (!formApiKey.trim() && !editingProvider) {
      toast.error(t("toast.apiKeyRequired"));
      return;
    }
    if (!formModel.trim()) {
      toast.error(t("toast.modelRequired"));
      return;
    }

    const payload: ProviderConfigCreate = {
      provider_type: formProviderType,
      provider_id: formProviderId,
      label: formLabel.trim(),
      api_key: formApiKey.trim(),
      api_url: formApiUrl.trim() || undefined,
      model: formModel.trim(),
      is_active: formIsActive,
    };

    if (editingProvider) {
      const updatePayload: Partial<ProviderConfigCreate> = { ...payload };
      if (!updatePayload.api_key) {
        delete updatePayload.api_key;
      }
      updateMut.mutate({ id: editingProvider.id, payload: updatePayload });
    } else {
      createMut.mutate(payload);
    }
  }

  function handleFetchModels() {
    setAvailableModels([]);
    if (editingProvider && !formApiKey.trim()) {
      listModelsMut.mutate({ config_id: editingProvider.id });
      return;
    }
    if (!formApiKey.trim()) {
      toast.error(t("toast.apiKeyRequired"));
      return;
    }
    listModelsMut.mutate({
      provider_type: formProviderType,
      provider_id: formProviderId,
      api_key: formApiKey.trim(),
      api_url: formApiUrl.trim() || undefined,
    });
  }

  if (isLoading) return <ProviderSettingsSkeleton />;

  return (
    <div className="min-w-0 space-y-6">
      <ProductReveal blur={false} className="min-w-0">
        <h1 className="break-words text-2xl font-bold tracking-tight text-foreground">
          <ProductShinyText text={t("title")} />
        </h1>
        <p style={{ color: "var(--muted-foreground)" }}>
          {t("description")}
        </p>
      </ProductReveal>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <Settings2 className="size-5" style={{ color: "var(--muted-foreground)" }} />
          <span className="text-sm" style={{ color: "var(--muted-foreground)" }}>
            {t("providersCount", { count: providers.length })}
          </span>
        </div>
        <ProductElectricFrame radius={12}>
          <Button onClick={handleAddProvider} className="w-full bg-primary text-primary-foreground hover:bg-primary/90 sm:w-auto">
            <Plus className="size-4" />
            {t("addProvider")}
          </Button>
        </ProductElectricFrame>
      </div>

      {providers.length === 0 ? (
        <ProductGlareCard intense>
          <div className="w-full rounded-xl py-12 text-center" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
            <Settings2 className="mx-auto size-10 mb-3 opacity-40" style={{ color: "var(--text-tertiary)" }} />
            <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>{t("noProvidersTitle")}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
              {t("noProvidersDesc")}
            </p>
            <Button
              onClick={handleAddProvider}
              className="mt-4 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              <Plus className="size-4" />
              {t("addFirstProvider")}
            </Button>
          </div>
        </ProductGlareCard>
      ) : (
        <div
          className="grid min-w-0 gap-4"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 18rem), 1fr))" }}
        >
          {providers.map((provider) => (
            <ProductGlareCard key={provider.id}>
              <Card className="relative w-full">
                <CardHeader className="pb-3">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <Badge
                        variant="outline"
                        className="capitalize gap-1 px-2 py-1"
                      >
                        <Cpu className="size-3" />
                        {PROTOCOL_LABELS[provider.provider_type]}
                      </Badge>
                      {provider.is_active && (
                        <span className="text-xs px-2 py-0.5 rounded flex items-center gap-1" style={{ background: "rgba(132, 204, 22, 0.15)", color: "var(--primary)" }}>
                          <CheckCircle2 className="size-3" />
                          {t("activeBadge")}
                        </span>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1 self-end sm:self-auto">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => handleTestConnection(provider)}
                        disabled={testingId === provider.id}
                        title="Test Connection"
                      >
                        {testingId === provider.id ? (
                          <Spinner className="size-3.5" />
                        ) : (
                          <Wifi className="size-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => handleEditProvider(provider)}
                        title="Edit"
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => handleDeleteProvider(provider)}
                        title="Delete"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div>
                      <p className="truncate font-medium">{provider.label}</p>
                      <p className="text-sm text-muted-foreground">
                        {t("modelLabel")}{" "}
                        <code className="text-xs bg-muted px-1 py-0.5 rounded">
                          {provider.model}
                        </code>
                      </p>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <KeyRound className="size-3.5" />
                      <span className="font-mono text-xs">
                        {maskApiKey(provider.api_key)}
                      </span>
                    </div>
                    {provider.api_url && (
                      <p className="text-xs text-muted-foreground truncate">
                        URL: {provider.api_url}
                      </p>
                    )}
                  </div>
                  {!provider.is_active && (
                    <div className="mt-3 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setActiveMut.mutate(provider.id)}
                        disabled={setActiveMut.isPending}
                        className="gap-1.5 border-[rgba(132,204,22,0.3)] text-primary hover:bg-[rgba(132,204,22,0.1)]"
                      >
                        {setActiveMut.isPending ? (
                          <Spinner className="size-3.5" />
                        ) : (
                          <Circle className="size-3.5" />
                        )}
                        {t("setActive")}
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </ProductGlareCard>
          ))}
        </div>
      )}

      {/* Add/Edit Dialog */}
      <Dialog
        open={isDialogOpen}
        onOpenChange={(open: boolean) => {
          setIsDialogOpen(open);
          if (!open) {
            resetForm();
          }
        }}
      >
        <DialogContent className="flex h-[100dvh] max-h-[100dvh] w-full grid-rows-none flex-col gap-0 overflow-hidden rounded-none p-0 sm:h-auto sm:max-h-[88dvh] sm:w-[min(1120px,calc(100vw-2rem))] sm:rounded-xl sm:max-w-none">
          <DialogHeader className="shrink-0 border-b px-4 pb-4 pt-5 sm:px-6" style={{ borderColor: "var(--border)" }}>
            <DialogTitle>
              {editingProvider ? t("dialog.editTitle") : t("dialog.addTitle")}
            </DialogTitle>
            <DialogDescription>
              {editingProvider
                ? t("dialog.editDesc")
                : t("dialog.addDesc")}
            </DialogDescription>
          </DialogHeader>

          <div data-testid="provider-dialog-body" className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
            {/* Provider Presets */}
            <div className="space-y-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <Label className="text-sm font-semibold">{t("dialog.presets")}</Label>
                  <p className="mt-1 text-xs text-muted-foreground">
                    选择一个常见平台后，下面的 Base URL 和模型会自动带入，你仍然可以手动修改。
                  </p>
                </div>
                <div className="relative w-full sm:w-56">
                  <Search
                    className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <Input
                    value={providerPresetQuery}
                    onChange={(event) => setProviderPresetQuery(event.target.value)}
                    placeholder="搜索供应商"
                    className="h-9 rounded-full bg-muted/60 pl-9 text-xs"
                  />
                </div>
              </div>
              <div
                className="grid min-w-0 gap-3"
                style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 16rem), 1fr))" }}
              >
                {visibleProviderPresets.map((preset) => (
                  <ProductGlareCard key={preset.id} intense={preset.recommended}>
                    <button
                      type="button"
                      onClick={() => applyPreset(preset.id)}
                      className={cn(
                        "group relative min-h-[132px] w-full min-w-0 overflow-hidden rounded-2xl border bg-card p-4 text-left transition duration-200 hover:-translate-y-0.5 hover:border-primary/50 hover:bg-primary/5 hover:shadow-[0_18px_50px_rgba(15,23,42,0.10)]",
                        selectedPresetId === preset.id &&
                          "border-primary bg-primary/10 shadow-[0_18px_50px_rgba(132,204,22,0.12)] ring-1 ring-primary/30",
                      )}
                      aria-pressed={selectedPresetId === preset.id}
                    >
                      {preset.recommended && (
                        <span className="absolute right-3 top-3 inline-flex size-5 items-center justify-center rounded-full bg-amber-400 text-amber-950 shadow-sm">
                          <Star className="size-3 fill-current" aria-hidden="true" />
                        </span>
                      )}
                      <div className="flex items-start gap-3 pr-5">
                        <ProviderBrandMark brand={preset.brand} label={preset.label} />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-foreground">
                            {preset.label}
                          </div>
                          <div className="mt-1">
                            <Badge variant="outline" className="rounded-full px-2 py-0 text-[10px] font-medium">
                              {PROTOCOL_LABELS[preset.providerType]}
                            </Badge>
                          </div>
                        </div>
                      </div>
                      <p className="mt-3 line-clamp-2 text-xs leading-5 text-muted-foreground">
                        {preset.description}
                      </p>
                      <div className="mt-3 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                        <span className="truncate rounded-full bg-muted px-2 py-1 font-mono">
                          {preset.modelHint ?? preset.model}
                        </span>
                        {preset.apiUrl ? (
                          <span className="max-w-[42%] truncate text-right">
                            {new URL(preset.apiUrl).hostname}
                          </span>
                        ) : (
                          <span className="text-right">自定义地址</span>
                        )}
                      </div>
                    </button>
                  </ProductGlareCard>
                ))}
                {visibleProviderPresets.length === 0 && (
                  <div className="rounded-2xl border border-dashed p-5 text-sm text-muted-foreground sm:col-span-2 lg:col-span-3">
                    没有匹配的供应商。可以选择“自定义配置”，手动填写 Base URL 和模型名。
                  </div>
                )}
              </div>
            </div>

            {/* Provider Protocol */}
            <div className="space-y-2">
              <Label>{t("dialog.providerType")}</Label>
              <Select
                value={formProviderType}
                onValueChange={(v: string | null) => {
                  if (!v) return;
                  setFormProviderType(v as ProviderProtocol);
                  setFormProviderId(v === "anthropic" ? "custom-anthropic" : "custom-openai");
                  setSelectedPresetId(null);
                  if (!editingProvider) {
                    setFormModel(DEFAULT_MODELS[v as ProviderProtocol]);
                  }
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai">OpenAI 兼容接口 (/v1/chat/completions)</SelectItem>
                  <SelectItem value="anthropic">Claude Messages 接口 (/v1/messages)</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {t("dialog.providerTypeHelp")}
              </p>
            </div>

            {/* Label */}
            <div className="space-y-2">
              <Label htmlFor="label">{t("dialog.label")}</Label>
              <Input
                id="label"
                value={formLabel}
                onChange={(e) => setFormLabel(e.target.value)}
                placeholder="My OpenAI"
              />
            </div>

            {/* API Key */}
            <div className="space-y-2">
              <Label htmlFor="api-key">
                {t("dialog.apiKey")}{" "}
                {editingProvider && (
                  <span className="text-muted-foreground font-normal">
                    {t("dialog.apiKeyHint")}
                  </span>
                )}
              </Label>
              <Input
                id="api-key"
                type="password"
                value={formApiKey}
                onChange={(e) => setFormApiKey(e.target.value)}
                placeholder={
                  editingProvider
                    ? t("dialog.apiKeyPlaceholderEdit")
                    : t("dialog.apiKeyPlaceholderNew")
                }
              />
            </div>

            {/* API URL */}
            <div className="space-y-2">
              <Label htmlFor="api-url">{t("dialog.apiUrl")}</Label>
              <Input
                id="api-url"
                value={formApiUrl}
                onChange={(e) => setFormApiUrl(e.target.value)}
                placeholder={
                  formProviderType === "openai"
                    ? "https://api.deepseek.com"
                    : "https://api.anthropic.com"
                }
              />
              <p className="text-xs text-muted-foreground">
                {t("dialog.apiUrlHelp")}
              </p>
            </div>

            {/* Model */}
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="model">{t("dialog.model")}</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleFetchModels}
                  disabled={listModelsMut.isPending}
                  className="shrink-0 gap-1.5"
                >
                  {listModelsMut.isPending ? <Spinner className="size-3.5" /> : <ListTree className="size-3.5" />}
                  {t("dialog.fetchModels")}
                </Button>
              </div>
              <Input
                id="model"
                value={formModel}
                onChange={(e) => setFormModel(e.target.value)}
                placeholder={DEFAULT_MODELS[formProviderType]}
              />
              <p className="text-xs text-muted-foreground">
                e.g.,{" "}
                {formProviderType === "openai"
                  ? "deepseek-v4-flash, gpt-4o, qwen-plus, glm-4-flash"
                  : "claude-sonnet-4-20250514, claude-3-5-sonnet-20241022"}
              </p>
              {availableModels.length > 0 && (
                <div className="rounded-xl border bg-muted/30 p-2" style={{ borderColor: "var(--border)" }}>
                  <div className="mb-2 flex items-center justify-between px-1 text-xs text-muted-foreground">
                    <span>{t("dialog.modelsFound", { count: availableModels.length })}</span>
                    <span>{t("dialog.clickToFill")}</span>
                  </div>
                  <div className="flex max-h-36 flex-wrap gap-1.5 overflow-y-auto">
                    {availableModels.map((model) => (
                      <button
                        key={model.id}
                        type="button"
                        onClick={() => setFormModel(model.id)}
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-xs transition hover:border-primary hover:bg-primary/10",
                          formModel === model.id ? "border-primary bg-primary/10 text-foreground" : "border-border bg-background text-muted-foreground",
                        )}
                      >
                        {model.id}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Active Switch */}
            <div className="flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="is-active">{t("dialog.setActive")}</Label>
                <p className="text-xs text-muted-foreground">
                  {t("dialog.setActiveDesc")}
                </p>
              </div>
              <Switch
                id="is-active"
                checked={formIsActive}
                onCheckedChange={setFormIsActive}
              />
            </div>
          </div>

          <DialogFooter className="mx-0 mb-0 shrink-0 rounded-none border-t bg-muted/40 px-4 py-4 sm:px-6">
            <Button
              variant="outline"
              onClick={() => {
                setIsDialogOpen(false);
                resetForm();
              }}
            >
              {t("dialog.cancel")}
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving && <Spinner />}
              {editingProvider ? t("dialog.update") : t("dialog.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
