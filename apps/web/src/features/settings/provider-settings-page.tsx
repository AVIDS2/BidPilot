import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listProviderConfigs,
  createProviderConfig,
  updateProviderConfig,
  deleteProviderConfig,
  testProviderConnection,
  type ProviderConfig,
  type ProviderConfigCreate,
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
import {
  Plus,
  Trash2,
  Wifi,
  Settings2,
  KeyRound,
  CheckCircle2,
  Circle,
  Pencil,
  Cpu,
} from "lucide-react";

type ProviderProtocol = "openai" | "anthropic";

const DEFAULT_MODELS: Record<string, string> = {
  openai: "gpt-4o",
  anthropic: "claude-sonnet-4-20250514",
};

const PROTOCOL_LABELS: Record<ProviderProtocol, string> = {
  openai: "OpenAI-compatible",
  anthropic: "Anthropic Messages",
};

const PROVIDER_PRESETS: Array<{
  id: string;
  label: string;
  providerType: ProviderProtocol;
  apiUrl: string;
  model: string;
  description: string;
}> = [
  {
    id: "custom-openai",
    label: "Custom OpenAI",
    providerType: "openai",
    apiUrl: "",
    model: "gpt-4o",
    description: "/v1/chat/completions",
  },
  {
    id: "deepseek",
    label: "DeepSeek",
    providerType: "openai",
    apiUrl: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
    description: "DeepSeek official OpenAI-compatible API",
  },
  {
    id: "dashscope",
    label: "Alibaba Bailian",
    providerType: "openai",
    apiUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-plus",
    description: "DashScope compatible-mode",
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    providerType: "openai",
    apiUrl: "https://openrouter.ai/api/v1",
    model: "openai/gpt-4o-mini",
    description: "OpenRouter OpenAI-compatible API",
  },
  {
    id: "siliconflow",
    label: "SiliconFlow",
    providerType: "openai",
    apiUrl: "https://api.siliconflow.cn/v1",
    model: "deepseek-ai/DeepSeek-V3",
    description: "SiliconFlow OpenAI-compatible API",
  },
  {
    id: "custom-anthropic",
    label: "Custom Claude",
    providerType: "anthropic",
    apiUrl: "",
    model: "claude-sonnet-4-20250514",
    description: "/v1/messages",
  },
  {
    id: "anthropic",
    label: "Anthropic",
    providerType: "anthropic",
    apiUrl: "https://api.anthropic.com",
    model: "claude-sonnet-4-20250514",
    description: "Official Anthropic Messages API",
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
      <div className="grid gap-4 md:grid-cols-2">
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
  const [formLabel, setFormLabel] = useState("");
  const [formApiKey, setFormApiKey] = useState("");
  const [formApiUrl, setFormApiUrl] = useState("");
  const [formModel, setFormModel] = useState("");
  const [formIsActive, setFormIsActive] = useState(false);

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

  function resetForm() {
    setFormProviderType("openai");
    setFormLabel("");
    setFormApiKey("");
    setFormApiUrl("");
    setFormModel(DEFAULT_MODELS.openai);
    setFormIsActive(false);
  }

  function applyPreset(presetId: string) {
    const preset = PROVIDER_PRESETS.find((item) => item.id === presetId);
    if (!preset) return;

    setFormProviderType(preset.providerType);
    setFormApiUrl(preset.apiUrl);
    setFormModel(preset.model);
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
    setFormLabel(provider.label);
    setFormApiKey("");
    setFormApiUrl(provider.api_url ?? "");
    setFormModel(provider.model);
    setFormIsActive(provider.is_active);
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

  if (isLoading) return <ProviderSettingsSkeleton />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{t("title")}</h1>
        <p style={{ color: "var(--muted-foreground)" }}>
          {t("description")}
        </p>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings2 className="size-5" style={{ color: "var(--muted-foreground)" }} />
          <span className="text-sm" style={{ color: "var(--muted-foreground)" }}>
            {t("providersCount", { count: providers.length })}
          </span>
        </div>
        <Button onClick={handleAddProvider} className="bg-primary text-primary-foreground hover:bg-primary/90">
          <Plus className="size-4" />
          {t("addProvider")}
        </Button>
      </div>

      {providers.length === 0 ? (
        <div className="rounded-xl py-12 text-center" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
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
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {providers.map((provider) => (
            <Card key={provider.id} className="relative">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
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
                  <div className="flex items-center gap-1">
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
                    <p className="font-medium">{provider.label}</p>
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
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingProvider ? t("dialog.editTitle") : t("dialog.addTitle")}
            </DialogTitle>
            <DialogDescription>
              {editingProvider
                ? t("dialog.editDesc")
                : t("dialog.addDesc")}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Provider Presets */}
            <div className="space-y-2">
              <Label>{t("dialog.presets")}</Label>
              <div className="grid gap-2 sm:grid-cols-2">
                {PROVIDER_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => applyPreset(preset.id)}
                    className="rounded-lg border bg-card p-3 text-left transition hover:border-primary/60 hover:bg-primary/5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{preset.label}</span>
                      <Badge variant="outline" className="text-[10px]">
                        {PROTOCOL_LABELS[preset.providerType]}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{preset.description}</p>
                  </button>
                ))}
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
                  if (!editingProvider) {
                    setFormModel(DEFAULT_MODELS[v as ProviderProtocol]);
                  }
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai">OpenAI-compatible (/v1/chat/completions)</SelectItem>
                  <SelectItem value="anthropic">Anthropic Messages (/v1/messages)</SelectItem>
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
                    ? "https://api.deepseek.com/v1"
                    : "https://api.anthropic.com"
                }
              />
              <p className="text-xs text-muted-foreground">
                {t("dialog.apiUrlHelp")}
              </p>
            </div>

            {/* Model */}
            <div className="space-y-2">
              <Label htmlFor="model">{t("dialog.model")}</Label>
              <Input
                id="model"
                value={formModel}
                onChange={(e) => setFormModel(e.target.value)}
                placeholder={DEFAULT_MODELS[formProviderType]}
              />
              <p className="text-xs text-muted-foreground">
                e.g.,{" "}
                {formProviderType === "openai"
                  ? "deepseek-chat, gpt-4o, qwen-plus"
                  : "claude-sonnet-4-20250514, claude-3-5-sonnet-20241022"}
              </p>
            </div>

            {/* Active Switch */}
            <div className="flex items-center justify-between rounded-lg border p-3">
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

          <DialogFooter>
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
