import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2Icon,
  CircleAlertIcon,
  CopyIcon,
  KeyRoundIcon,
  LoaderCircleIcon,
  PlusIcon,
  RefreshCwIcon,
  RotateCcwIcon,
  SendIcon,
  Trash2Icon,
  WebhookIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import {
  createWebhookEndpoint,
  deleteWebhookEndpoint,
  getWebhookOverview,
  retryWebhookDelivery,
  rotateWebhookSecret,
  testWebhookEndpoint,
  updateWebhookEndpoint,
  type WebhookDeliveryRead,
  type WebhookEventType,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";

import { SettingsNavigation } from "./settings-navigation";

const eventLabels: Record<WebhookEventType, { title: string; description: string }> = {
  "radar.notice.matched": { title: "雷达命中", description: "新公告满足团队订阅条件时发送" },
  "radar.notice.saved": { title: "公告已保存", description: "团队确认值得跟进时发送" },
  "radar.notice.converted": { title: "已转投标项目", description: "公告转化为项目并进入工作流时发送" },
};

function displayError(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function formatMoment(value: string | null) {
  if (!value) return "尚未发生";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}

function deliveryStatus(delivery: WebhookDeliveryRead) {
  if (delivery.status === "delivered") return { label: "已送达", tone: "success" as const };
  if (delivery.status === "failed") return { label: "投递失败", tone: "danger" as const };
  if (delivery.status === "delivering") return { label: "正在投递", tone: "neutral" as const };
  return { label: "等待重试", tone: "warning" as const };
}

export function WebhookSettingsPageV2() {
  const queryClient = useQueryClient();
  const overviewQuery = useQuery({ queryKey: ["webhook-overview"], queryFn: getWebhookOverview, staleTime: 8_000 });
  const overview = overviewQuery.data;
  const [createOpen, setCreateOpen] = useState(false);
  const [secretOpen, setSecretOpen] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState("");
  const [endpointName, setEndpointName] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [events, setEvents] = useState<WebhookEventType[]>(["radar.notice.matched"]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["webhook-overview"] });
  const supportedEvents = overview?.supported_events ?? (Object.keys(eventLabels) as WebhookEventType[]);
  const endpoints = overview?.endpoints ?? [];
  const deliveries = useMemo(() => overview?.deliveries ?? [], [overview?.deliveries]);
  const failureCount = overview?.summary.failed_delivery_count ?? 0;
  const pendingCount = overview?.summary.pending_delivery_count ?? 0;
  const endpointCount = overview?.summary.active_endpoint_count ?? 0;
  const canCreate = endpointName.trim().length > 0 && targetUrl.trim().length > 0 && events.length > 0;

  const createMutation = useMutation({
    mutationFn: createWebhookEndpoint,
    onSuccess: (result) => {
      void refresh();
      setCreateOpen(false);
      setEndpointName("");
      setTargetUrl("");
      setEvents(["radar.notice.matched"]);
      setRevealedSecret(result.signing_secret);
      setSecretOpen(true);
      toast.success("Webhook 已创建。请立即保存签名密钥。");
    },
    onError: (error) => toast.error(displayError(error, "Webhook 创建失败。")),
  });
  const updateMutation = useMutation({
    mutationFn: ({ endpointId, payload }: { endpointId: string; payload: Parameters<typeof updateWebhookEndpoint>[1] }) => updateWebhookEndpoint(endpointId, payload),
    onSuccess: () => { void refresh(); toast.success("Webhook 配置已更新。"); },
    onError: (error) => toast.error(displayError(error, "配置更新失败。")),
  });
  const testMutation = useMutation({
    mutationFn: testWebhookEndpoint,
    onSuccess: (result) => {
      void refresh();
      const status = result.delivery.status;
      if (status === "delivered") toast.success("测试事件已送达目标地址。");
      else toast.error(`测试事件未送达：${result.delivery.last_error_code ?? "等待重试"}`);
    },
    onError: (error) => toast.error(displayError(error, "测试事件未能发出。")),
  });
  const rotateMutation = useMutation({
    mutationFn: rotateWebhookSecret,
    onSuccess: (result) => {
      void refresh();
      setRevealedSecret(result.signing_secret);
      setSecretOpen(true);
      toast.success("签名密钥已轮换，旧密钥立即失效。");
    },
    onError: (error) => toast.error(displayError(error, "密钥轮换失败。")),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteWebhookEndpoint,
    onSuccess: () => { void refresh(); toast.success("Webhook 及其历史投递记录已删除。"); },
    onError: (error) => toast.error(displayError(error, "Webhook 删除失败。")),
  });
  const retryMutation = useMutation({
    mutationFn: retryWebhookDelivery,
    onSuccess: (result) => {
      void refresh();
      if (result.delivery.status === "delivered") toast.success("已重新投递并送达。");
      else toast.error(`本次投递未完成：${result.delivery.last_error_code ?? "等待重试"}`);
    },
    onError: (error) => toast.error(displayError(error, "重新投递失败。")),
  });

  const endpointActionBusy = updateMutation.isPending || testMutation.isPending || rotateMutation.isPending || deleteMutation.isPending;
  const deliveredPercent = useMemo(() => {
    if (!deliveries.length) return null;
    return Math.round((deliveries.filter((delivery) => delivery.status === "delivered").length / deliveries.length) * 100);
  }, [deliveries]);

  function toggleEvent(event: WebhookEventType, checked: boolean) {
    setEvents((current) => checked
      ? [...current, event]
      : current.filter((value) => value !== event));
  }

  function copySecret() {
    void navigator.clipboard.writeText(revealedSecret).then(
      () => toast.success("签名密钥已复制。"),
      () => toast.error("无法写入剪贴板，请手动复制。"),
    );
  }

  return (
    <section className="wb-settings-page wb-webhook-settings">
      <SettingsNavigation />
      <main className="wb-settings-main">
        <div className="wb-settings-content">
          <header className="wb-settings-content-head">
            <div>
              <p className="wb-settings-eyebrow">Integrations</p>
              <h1>Webhook</h1>
              <p>把关键招采进展送进你已有的自动化流程。每次事件都会用 HMAC-SHA256 签名，并保留可重试的投递记录。</p>
            </div>
            <Button onClick={() => setCreateOpen(true)} type="button"><PlusIcon aria-hidden="true" />新建端点</Button>
          </header>

          <section className="wb-webhook-facts" aria-label="Webhook 概况">
            <div><span>已启用端点</span><strong>{endpointCount}</strong><small>{endpoints.length} 个已配置</small></div>
            <div><span>等待处理</span><strong>{pendingCount}</strong><small>后台每 30 秒恢复扫描</small></div>
            <div className={failureCount ? "is-attention" : ""}><span>需要关注</span><strong>{failureCount}</strong><small>{failureCount ? "请检查目标服务状态" : "最近投递没有失败"}</small></div>
            <div><span>近 80 次送达</span><strong>{deliveredPercent === null ? "-" : `${deliveredPercent}%`}</strong><small>来自可审计的投递记录</small></div>
          </section>

          <section className="wb-settings-section wb-webhook-endpoints">
            <header className="wb-settings-section-head wb-settings-section-head--row">
              <div><h2>端点</h2><p>只允许公共 HTTP(S) 地址；重定向会被禁止，避免投递请求被导向内网。</p></div>
            </header>
            {overviewQuery.isLoading ? <p className="wb-list-loading">正在读取 Webhook 配置…</p> : null}
            {!overviewQuery.isLoading && endpoints.length === 0 ? (
              <div className="wb-webhook-empty"><WebhookIcon aria-hidden="true" /><div><strong>还没有连接的自动化端点</strong><p>新建端点后，雷达命中、保存和转项目等真实业务事件才会触发投递。</p></div><Button onClick={() => setCreateOpen(true)} type="button" variant="outline">配置第一个端点</Button></div>
            ) : null}
            <div className="wb-webhook-endpoint-list">
              {endpoints.map((endpoint) => (
                <article className={endpoint.is_active ? "wb-webhook-endpoint" : "wb-webhook-endpoint is-paused"} key={endpoint.id}>
                  <div className="wb-webhook-endpoint__identity"><WebhookIcon aria-hidden="true" /><div><strong>{endpoint.name}</strong><code>{endpoint.target_url}</code></div></div>
                  <div className="wb-webhook-event-badges">{endpoint.events.map((event) => <Badge key={event} variant="secondary">{eventLabels[event].title}</Badge>)}</div>
                  <div className="wb-webhook-endpoint__state"><Switch aria-label={`启用 ${endpoint.name}`} checked={endpoint.is_active} disabled={endpointActionBusy} onCheckedChange={(isActive) => updateMutation.mutate({ endpointId: endpoint.id, payload: { is_active: isActive } })} /><span>{endpoint.is_active ? "已启用" : "已暂停"}</span></div>
                  <div className="wb-webhook-endpoint__actions">
                    <Button disabled={!endpoint.is_active || endpointActionBusy} onClick={() => testMutation.mutate(endpoint.id)} size="sm" type="button" variant="outline"><SendIcon aria-hidden="true" />测试</Button>
                    <Button disabled={endpointActionBusy} onClick={() => rotateMutation.mutate(endpoint.id)} size="icon-sm" title="轮换签名密钥" type="button" variant="ghost"><RotateCcwIcon aria-hidden="true" /></Button>
                    <Button disabled={endpointActionBusy} onClick={() => { if (window.confirm(`删除「${endpoint.name}」以及投递记录吗？`)) deleteMutation.mutate(endpoint.id); }} size="icon-sm" title="删除端点" type="button" variant="ghost"><Trash2Icon aria-hidden="true" /></Button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="wb-settings-section wb-webhook-contract">
            <header className="wb-settings-section-head"><h2>接收约定</h2><p>POST 请求的 body 是 JSON 事件信封。验证签名时使用 <code>timestamp + "." + rawBody</code> 计算 HMAC-SHA256。</p></header>
            <div className="wb-webhook-contract__code"><div><span>请求头</span><code>X-BidPilot-Event · X-BidPilot-Delivery · X-BidPilot-Timestamp · X-BidPilot-Signature</code></div><div><span>事件载荷</span><code>{'{ id, type, created_at, data: { notice, matches, project? } }'}</code></div></div>
          </section>

          <section className="wb-settings-section wb-webhook-deliveries">
            <header className="wb-settings-section-head wb-settings-section-head--row"><div><h2>最近投递</h2><p>响应正文不会被保存，避免把第三方系统数据带回平台；状态码、错误码和重试次数会被保留。</p></div><Button disabled={overviewQuery.isFetching} onClick={() => void overviewQuery.refetch()} size="sm" type="button" variant="ghost"><RefreshCwIcon className={overviewQuery.isFetching ? "wb-spin-icon" : undefined} aria-hidden="true" />刷新</Button></header>
            {deliveries.length === 0 ? <p className="wb-webhook-delivery-empty">还没有投递记录。端点接收到匹配事件后，历史会显示在这里。</p> : null}
            <div className="wb-webhook-delivery-list">
              {deliveries.map((delivery) => {
                const status = deliveryStatus(delivery);
                return <article className="wb-webhook-delivery" key={delivery.id}>
                  <div className="wb-webhook-delivery__event">{status.tone === "success" ? <CheckCircle2Icon aria-hidden="true" /> : <CircleAlertIcon aria-hidden="true" />}<div><strong>{eventLabels[delivery.event_type as WebhookEventType]?.title ?? delivery.event_type}</strong><small>{delivery.endpoint_name} · {formatMoment(delivery.created_at)}</small></div></div>
                  <Badge className={`wb-webhook-status is-${status.tone}`} variant="secondary">{status.label}</Badge>
                  <div className="wb-webhook-delivery__meta"><span>{delivery.last_http_status ? `HTTP ${delivery.last_http_status}` : delivery.last_error_code ?? "等待首次投递"}</span><span>第 {delivery.attempt_count}/{delivery.max_attempts} 次</span></div>
                  {delivery.status !== "delivered" ? <Button disabled={retryMutation.isPending} onClick={() => retryMutation.mutate(delivery.id)} size="sm" type="button" variant="ghost"><RotateCcwIcon aria-hidden="true" />立即重试</Button> : <span className="wb-webhook-delivery__sent">{formatMoment(delivery.delivered_at)}</span>}
                </article>;
              })}
            </div>
          </section>
        </div>
      </main>

      <Dialog onOpenChange={setCreateOpen} open={createOpen}>
        <DialogContent className="wb-webhook-dialog sm:max-w-lg">
          <DialogHeader><DialogTitle>新建 Webhook 端点</DialogTitle><DialogDescription>端点应由你的自动化系统接收。平台会使用只显示一次的签名密钥对每个事件签名。</DialogDescription></DialogHeader>
          <FieldGroup>
            <Field><FieldLabel htmlFor="webhook-name">端点名称</FieldLabel><Input id="webhook-name" onChange={(event) => setEndpointName(event.target.value)} placeholder="例如：飞书招采通知" value={endpointName} /></Field>
            <Field><FieldLabel htmlFor="webhook-url">目标 URL</FieldLabel><Input id="webhook-url" onChange={(event) => setTargetUrl(event.target.value)} placeholder="https://automation.example.com/bidpilot" value={targetUrl} /></Field>
            <Field><FieldLabel>订阅事件</FieldLabel><div className="wb-webhook-event-options">{supportedEvents.map((event) => <label key={event}><Checkbox checked={events.includes(event)} onCheckedChange={(checked) => toggleEvent(event, checked === true)} /><span><strong>{eventLabels[event].title}</strong><small>{eventLabels[event].description}</small></span></label>)}</div></Field>
          </FieldGroup>
          <DialogFooter><Button onClick={() => setCreateOpen(false)} type="button" variant="outline">取消</Button><Button disabled={!canCreate || createMutation.isPending} onClick={() => createMutation.mutate({ name: endpointName.trim(), target_url: targetUrl.trim(), events })} type="button">{createMutation.isPending ? <LoaderCircleIcon className="animate-spin" aria-hidden="true" /> : <WebhookIcon aria-hidden="true" />}创建端点</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog onOpenChange={setSecretOpen} open={secretOpen}>
        <DialogContent className="wb-webhook-dialog sm:max-w-lg"><DialogHeader><DialogTitle>保存签名密钥</DialogTitle><DialogDescription>此密钥只会显示这一次。请保存到接收端的安全配置中；关闭后只能通过“轮换”生成新的密钥。</DialogDescription></DialogHeader><div className="wb-webhook-secret"><KeyRoundIcon aria-hidden="true" /><code>{revealedSecret}</code><Button onClick={copySecret} size="icon-sm" title="复制签名密钥" type="button" variant="outline"><CopyIcon aria-hidden="true" /></Button></div><DialogFooter><Button onClick={() => setSecretOpen(false)} type="button">我已保存</Button></DialogFooter></DialogContent>
      </Dialog>
    </section>
  );
}
