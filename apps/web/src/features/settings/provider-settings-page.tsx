import { useState } from "react";
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

const DEFAULT_MODELS: Record<string, string> = {
  openai: "gpt-4o",
  anthropic: "claude-sonnet-4-20250514",
};

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
  const qc = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ProviderConfig | null>(null);

  // Form state
  const [formProviderType, setFormProviderType] = useState<"openai" | "anthropic">("openai");
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
      toast.success("Provider created successfully");
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
      toast.success("Provider updated successfully");
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
      toast.success("Provider deleted");
      qc.invalidateQueries({ queryKey: ["provider-configs"] });
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const testMut = useMutation({
    mutationFn: (payload: { provider_type: string; api_key: string; api_url?: string; model: string }) =>
      testProviderConnection(payload),
    onSuccess: (result) => {
      if (result.data.success) {
        toast.success(`Connection successful: ${result.data.message}`);
      } else {
        toast.error(`Connection failed: ${result.data.message}`);
      }
    },
    onError: (err: Error) => {
      toast.error(`Test failed: ${err.message}`);
    },
  });

  const setActiveMut = useMutation({
    mutationFn: (id: string) => updateProviderConfig(id, { is_active: true }),
    onSuccess: () => {
      toast.success("Active provider updated");
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
    if (window.confirm(`Are you sure you want to delete "${provider.label}"?`)) {
      deleteMut.mutate(provider.id);
    }
  }

  function handleTestConnection(provider: ProviderConfig) {
    setTestingId(provider.id);
    testMut.mutate(
      {
        provider_type: provider.provider_type,
        api_key: provider.api_key,
        api_url: provider.api_url ?? undefined,
        model: provider.model,
      },
      {
        onSettled: () => setTestingId(null),
      },
    );
  }

  function handleSave() {
    if (!formLabel.trim()) {
      toast.error("Label is required");
      return;
    }
    if (!formApiKey.trim() && !editingProvider) {
      toast.error("API key is required");
      return;
    }
    if (!formModel.trim()) {
      toast.error("Model is required");
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
        <h1 className="text-2xl font-bold tracking-tight text-white">AI Provider Settings</h1>
        <p style={{ color: "#a3a3a3" }}>
          Configure your AI provider connections for document drafting and analysis.
        </p>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings2 className="size-5" style={{ color: "#a3a3a3" }} />
          <span className="text-sm" style={{ color: "#a3a3a3" }}>
            {providers.length} provider{providers.length !== 1 ? "s" : ""} configured
          </span>
        </div>
        <Button onClick={handleAddProvider} className="bg-[#84cc16] text-[#0a0a0a] hover:bg-[#65a30d]">
          <Plus className="size-4" />
          Add Provider
        </Button>
      </div>

      {providers.length === 0 ? (
        <div className="rounded-xl py-12 text-center" style={{ background: "#171717", border: "1px solid rgba(163, 163, 163, 0.1)" }}>
          <Settings2 className="mx-auto size-10 mb-3 opacity-40" style={{ color: "#737373" }} />
          <p className="text-sm" style={{ color: "#a3a3a3" }}>No providers configured yet.</p>
          <p className="text-xs mt-1" style={{ color: "#737373" }}>
            Add an AI provider to get started with document drafting.
          </p>
          <Button
            onClick={handleAddProvider}
            className="mt-4 bg-[#84cc16] text-[#0a0a0a] hover:bg-[#65a30d]"
          >
            <Plus className="size-4" />
            Add Your First Provider
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
                      {provider.provider_type}
                    </Badge>
                    {provider.is_active && (
                      <span className="text-xs px-2 py-0.5 rounded flex items-center gap-1" style={{ background: "rgba(132, 204, 22, 0.15)", color: "#84cc16" }}>
                        <CheckCircle2 className="size-3" />
                        Active
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
                      Model:{" "}
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
                  <div className="mt-3 pt-3" style={{ borderTop: "1px solid rgba(163, 163, 163, 0.08)" }}>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setActiveMut.mutate(provider.id)}
                      disabled={setActiveMut.isPending}
                      className="gap-1.5 border-[rgba(132,204,22,0.3)] text-[#84cc16] hover:bg-[rgba(132,204,22,0.1)]"
                    >
                      {setActiveMut.isPending ? (
                        <Spinner className="size-3.5" />
                      ) : (
                        <Circle className="size-3.5" />
                      )}
                      Set Active
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
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingProvider ? "Edit Provider" : "Add Provider"}
            </DialogTitle>
            <DialogDescription>
              {editingProvider
                ? "Update your AI provider configuration."
                : "Configure a new AI provider connection."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Provider Type */}
            <div className="space-y-2">
              <Label>Provider Type</Label>
              <Select
                value={formProviderType}
                onValueChange={(v: string | null) => {
                  if (!v) return;
                  setFormProviderType(v as "openai" | "anthropic");
                  if (!editingProvider) {
                    setFormModel(DEFAULT_MODELS[v as "openai" | "anthropic"]);
                  }
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai">OpenAI</SelectItem>
                  <SelectItem value="anthropic">Anthropic</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Label */}
            <div className="space-y-2">
              <Label htmlFor="label">Label</Label>
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
                API Key{" "}
                {editingProvider && (
                  <span className="text-muted-foreground font-normal">
                    (leave blank to keep existing)
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
                    ? "Enter new key or leave blank"
                    : "sk-..."
                }
              />
            </div>

            {/* API URL */}
            <div className="space-y-2">
              <Label htmlFor="api-url">API URL (optional)</Label>
              <Input
                id="api-url"
                value={formApiUrl}
                onChange={(e) => setFormApiUrl(e.target.value)}
                placeholder={
                  formProviderType === "openai"
                    ? "https://api.openai.com"
                    : "https://api.anthropic.com"
                }
              />
            </div>

            {/* Model */}
            <div className="space-y-2">
              <Label htmlFor="model">Model</Label>
              <Input
                id="model"
                value={formModel}
                onChange={(e) => setFormModel(e.target.value)}
                placeholder={DEFAULT_MODELS[formProviderType]}
              />
              <p className="text-xs text-muted-foreground">
                e.g.,{" "}
                {formProviderType === "openai"
                  ? "gpt-4o, gpt-4-turbo"
                  : "claude-sonnet-4-20250514, claude-3-5-sonnet-20241022"}
              </p>
            </div>

            {/* Active Switch */}
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="space-y-0.5">
                <Label htmlFor="is-active">Set as active provider</Label>
                <p className="text-xs text-muted-foreground">
                  This provider will be used by default for drafting.
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
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving && <Spinner />}
              {editingProvider ? "Update" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
