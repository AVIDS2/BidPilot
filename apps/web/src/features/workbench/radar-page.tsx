import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  ArrowUpRightIcon,
  BellRingIcon,
  BookmarkIcon,
  ChevronRightIcon,
  ExternalLinkIcon,
  FileSearchIcon,
  LoaderCircleIcon,
  PlusIcon,
  RadarIcon,
  RefreshCwIcon,
  RssIcon,
  SearchIcon,
  SendIcon,
  TargetIcon,
  TimerResetIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import {
  convertRadarNoticeToProject,
  createRadarSource,
  createRadarSubscription,
  getRadarOverview,
  pollRadarSource,
  updateRadarNoticeStatus,
  updateRadarSource,
  type NoticeSourceKind,
  type RadarNoticeRead,
  type RadarOverviewView,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
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
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const radarChartConfig = {
  notices: { label: "新增公告", color: "#348463" },
} satisfies ChartConfig;

const radarViews: Array<{ value: RadarOverviewView; label: string }> = [
  { value: "recommended", label: "推荐" },
  { value: "all", label: "全部" },
  { value: "intent", label: "意向" },
  { value: "tender", label: "招标" },
  { value: "saved", label: "已保存" },
  { value: "ignored", label: "已忽略" },
];

function splitTerms(value: string) {
  return value.split(/[，,\n]/).map((term) => term.trim()).filter(Boolean);
}

function formatDate(value: string | null, options: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" }) {
  if (!value) return "未提供";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未提供";
  return new Intl.DateTimeFormat("zh-CN", options).format(date);
}

function formatCurrency(value: number | null) {
  if (value === null) return null;
  return new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 0 }).format(value);
}

function deadlineLabel(value: string | null) {
  if (!value) return "截止日期待补充";
  const deadline = new Date(value);
  const today = new Date();
  const days = Math.ceil((deadline.getTime() - today.getTime()) / 86_400_000);
  if (Number.isNaN(days)) return "截止日期待补充";
  if (days < 0) return "已截止";
  if (days === 0) return "今天截止";
  if (days <= 14) return `${days} 天内截止`;
  return `${formatDate(value)} 截止`;
}

function noticeTypeLabel(type: RadarNoticeRead["notice_type"]) {
  return {
    intent: "采购意向",
    tender: "招标公告",
    prequalification: "资格预审",
    rfi: "需求征询",
    other: "其他公告",
  }[type];
}

function noticeStatusLabel(status: RadarNoticeRead["status"]) {
  return {
    new: "待研判",
    saved: "已保存",
    ignored: "已忽略",
    converted: "已转项目",
  }[status];
}

function sourceKindLabel(kind: NoticeSourceKind) {
  return {
    rss: "RSS Feed",
    json_feed: "JSON Feed",
    webhook: "推送来源",
  }[kind];
}

function safeExternalUrl(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : undefined;
  } catch {
    return undefined;
  }
}

export function RadarPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [view, setView] = useState<RadarOverviewView>("recommended");
  const [query, setQuery] = useState("");
  const [sourceDialogOpen, setSourceDialogOpen] = useState(false);
  const [subscriptionDialogOpen, setSubscriptionDialogOpen] = useState(false);
  const [selectedNoticeId, setSelectedNoticeId] = useState<string | null>(null);
  const [sourceName, setSourceName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceKind, setSourceKind] = useState<Extract<NoticeSourceKind, "rss" | "json_feed">>("rss");
  const [sourcePollingMinutes, setSourcePollingMinutes] = useState("60");
  const [subscriptionName, setSubscriptionName] = useState("");
  const [subscriptionKeywords, setSubscriptionKeywords] = useState("");
  const [subscriptionRegions, setSubscriptionRegions] = useState("");
  const [subscriptionCategories, setSubscriptionCategories] = useState("");

  const radarQuery = useQuery({
    queryKey: ["radar-overview", view, query],
    queryFn: () => getRadarOverview({ view, query }),
    staleTime: 15_000,
  });
  const overview = radarQuery.data;
  const selectedNotice = overview?.notices.find((notice) => notice.id === selectedNoticeId) ?? null;
  const selectedNoticeUrl = selectedNotice ? safeExternalUrl(selectedNotice.source_url) : undefined;
  const summary = overview?.summary;
  const activeSources = useMemo(
    () => (overview?.sources ?? []).filter((source) => source.is_active),
    [overview?.sources],
  );
  const chartData = overview?.summary.trends ?? [];

  const invalidateRadar = () => queryClient.invalidateQueries({ queryKey: ["radar-overview"] });

  const createSourceMutation = useMutation({
    mutationFn: createRadarSource,
    onSuccess: () => {
      void invalidateRadar();
      setSourceDialogOpen(false);
      setSourceName("");
      setSourceUrl("");
      setSourcePollingMinutes("60");
      toast.success("雷达来源已接入，将按设定间隔采集公开公告。");
    },
    onError: () => toast.error("来源未能接入。请检查公开地址和访问权限。"),
  });

  const createSubscriptionMutation = useMutation({
    mutationFn: createRadarSubscription,
    onSuccess: () => {
      void invalidateRadar();
      setSubscriptionDialogOpen(false);
      setSubscriptionName("");
      setSubscriptionKeywords("");
      setSubscriptionRegions("");
      setSubscriptionCategories("");
      toast.success("订阅已创建，后续命中会显示匹配理由。");
    },
    onError: () => toast.error("订阅未能创建。请检查筛选条件。"),
  });

  const pollSourceMutation = useMutation({
    mutationFn: pollRadarSource,
    onSuccess: (result) => {
      void invalidateRadar();
      if (result.status === "succeeded") {
        toast.success(`来源已刷新：发现 ${result.discovered_count} 条，新增 ${result.created_count} 条。`);
      } else {
        toast.error("来源暂时无法刷新，请检查地址或稍后重试。");
      }
    },
    onError: () => toast.error("来源暂时无法刷新，请稍后重试。"),
  });

  const toggleSourceMutation = useMutation({
    mutationFn: ({ sourceId, isActive }: { sourceId: string; isActive: boolean }) => updateRadarSource(sourceId, { is_active: isActive }),
    onSuccess: () => {
      void invalidateRadar();
      toast.success("来源状态已更新。");
    },
    onError: () => toast.error("来源状态未能更新。"),
  });

  const updateNoticeMutation = useMutation({
    mutationFn: ({ noticeId, status }: { noticeId: string; status: "new" | "saved" | "ignored" }) => updateRadarNoticeStatus(noticeId, status),
    onSuccess: () => {
      void invalidateRadar();
      toast.success("公告状态已更新。");
    },
    onError: () => toast.error("公告状态未能更新。"),
  });

  const convertNoticeMutation = useMutation({
    mutationFn: ({ noticeId, projectName }: { noticeId: string; projectName?: string }) => convertRadarNoticeToProject(noticeId, projectName),
    onSuccess: ({ project_id }) => {
      void invalidateRadar();
      setSelectedNoticeId(null);
      toast.success("已创建投标项目，并保留公告来源和匹配记录。");
      navigate(`/projects/${project_id}`);
    },
    onError: () => toast.error("暂时无法创建项目，请稍后重试。"),
  });

  function submitSource() {
    const pollingInterval = Number(sourcePollingMinutes);
    if (!sourceName.trim() || !sourceUrl.trim() || !Number.isInteger(pollingInterval)) return;
    createSourceMutation.mutate({
      name: sourceName.trim(),
      kind: sourceKind,
      endpoint_url: sourceUrl.trim(),
      polling_interval_minutes: pollingInterval,
    });
  }

  function submitSubscription() {
    if (!subscriptionName.trim()) return;
    createSubscriptionMutation.mutate({
      name: subscriptionName.trim(),
      keywords: splitTerms(subscriptionKeywords),
      regions: splitTerms(subscriptionRegions),
      categories: splitTerms(subscriptionCategories),
    });
  }

  return (
    <section className="wb-radar" aria-labelledby="radar-title">
      <header className="wb-radar-header">
        <div>
          <p className="wb-eyebrow">Opportunity intelligence</p>
          <h1 id="radar-title">招采雷达</h1>
          <p>把公开来源、团队关注方向和机会研判放到同一条可追溯的工作路径上。</p>
        </div>
        <div className="wb-radar-header-actions">
          <Button onClick={() => setSourceDialogOpen(true)} size="sm" variant="outline"><RssIcon aria-hidden="true" data-icon="inline-start" />管理来源</Button>
          <Button onClick={() => setSubscriptionDialogOpen(true)} size="sm"><PlusIcon aria-hidden="true" data-icon="inline-start" />新建订阅</Button>
        </div>
      </header>

      <section className="wb-radar-summary" aria-label="招采雷达概况">
        <div><span><RssIcon aria-hidden="true" />采集来源</span><strong>{summary?.active_source_count ?? 0}</strong><small>{summary?.source_attention_count ? `${summary.source_attention_count} 个来源需要处理` : "按来源频率持续采集"}</small></div>
        <div><span><TargetIcon aria-hidden="true" />生效订阅</span><strong>{summary?.active_subscription_count ?? 0}</strong><small>定义关键词、区域与品类意图</small></div>
        <div><span><BellRingIcon aria-hidden="true" />推荐机会</span><strong>{summary?.recommended_count ?? 0}</strong><small>已按订阅计算匹配理由</small></div>
        <div><span><TimerResetIcon aria-hidden="true" />近期截止</span><strong>{summary?.due_soon_count ?? 0}</strong><small>未来 14 天内需要研判</small></div>
      </section>

      <div className="wb-radar-overview-grid">
        <section className="wb-radar-scope-panel" aria-labelledby="radar-scope-title">
          <header>
            <div><h2 id="radar-scope-title">来源信号</h2><p>动效只在至少一个来源处于采集状态时显示。</p></div>
            <span className={activeSources.length ? "is-live" : ""}>{activeSources.length ? "采集中" : "待连接"}</span>
          </header>
          <div className={`wb-radar-scope${activeSources.length ? " is-live" : ""}`} aria-label={activeSources.length ? `${activeSources.length} 个来源正在采集` : "尚未连接来源"}>
            <i className="wb-radar-scope__ring wb-radar-scope__ring--outer" aria-hidden="true" />
            <i className="wb-radar-scope__ring wb-radar-scope__ring--middle" aria-hidden="true" />
            <i className="wb-radar-scope__ring wb-radar-scope__ring--inner" aria-hidden="true" />
            <i className="wb-radar-scope__sweep" aria-hidden="true" />
            <span className="wb-radar-scope__core"><RadarIcon aria-hidden="true" /><strong>{activeSources.length}</strong><small>活跃来源</small></span>
            {activeSources.slice(0, 4).map((source, index) => <span className={`wb-radar-scope__signal signal-${index + 1}`} key={source.id} title={source.name}><i aria-hidden="true" /><em>{source.name}</em></span>)}
          </div>
          <footer>
            {activeSources.length ? activeSources.slice(0, 3).map((source) => <span key={source.id}><i aria-hidden="true" />{source.name}<small>{source.last_success_at ? `上次成功 ${formatDate(source.last_success_at, { hour: "2-digit", minute: "2-digit" })}` : "等待首次刷新"}</small></span>) : <Button onClick={() => setSourceDialogOpen(true)} size="sm" variant="outline"><RssIcon aria-hidden="true" data-icon="inline-start" />接入第一个公开来源</Button>}
          </footer>
        </section>

        <section className="wb-radar-trend-panel" aria-labelledby="radar-trend-title">
          <header><div><h2 id="radar-trend-title">新增机会趋势</h2><p>最近 14 天由已接入来源采集到的公告数量。</p></div><span>{chartData.reduce((total, point) => total + point.notice_count, 0)} 条</span></header>
          {chartData.some((point) => point.notice_count > 0) ? <ChartContainer className="h-[236px] w-full" config={radarChartConfig}>
            <AreaChart accessibilityLayer data={chartData} margin={{ top: 12, right: 6, left: -24, bottom: 0 }}>
              <defs><linearGradient id="radar-notices" x1="0" x2="0" y1="0" y2="1"><stop offset="5%" stopColor="var(--color-notices)" stopOpacity={0.22} /><stop offset="95%" stopColor="var(--color-notices)" stopOpacity={0.02} /></linearGradient></defs>
              <CartesianGrid vertical={false} />
              <XAxis axisLine={false} dataKey="day" tickFormatter={(value) => formatDate(`${value}T00:00:00`, { month: "short", day: "numeric" })} tickLine={false} tickMargin={10} minTickGap={22} />
              <YAxis allowDecimals={false} axisLine={false} tickLine={false} width={34} />
              <ChartTooltip content={<ChartTooltipContent labelFormatter={(value) => formatDate(`${value}T00:00:00`, { year: "numeric", month: "long", day: "numeric" })} />} cursor={{ stroke: "#d8d9dd", strokeWidth: 1 }} />
              <Area dataKey="notice_count" fill="url(#radar-notices)" fillOpacity={1} name="新增公告" stroke="var(--color-notices)" strokeWidth={2} type="monotone" />
            </AreaChart>
          </ChartContainer> : <div className="wb-radar-trend-empty"><FileSearchIcon aria-hidden="true" /><strong>暂无真实采集数据</strong><span>接入来源并完成首次刷新后，这里显示每日新增公告，而不是填充演示数据。</span></div>}
        </section>
      </div>

      <section className="wb-radar-notices" aria-labelledby="radar-notices-title">
        <header className="wb-radar-section-head">
          <div><h2 id="radar-notices-title">机会队列</h2><p>每条推荐都带有订阅命中依据，先研判，再决定是否进入项目工作区。</p></div>
          <span>{overview?.notices.length ?? 0} 条结果</span>
        </header>
        <div className="wb-radar-toolbar">
          <Tabs onValueChange={(value) => setView(value as RadarOverviewView)} value={view}>
            <TabsList aria-label="筛选公告状态" variant="line">{radarViews.map((item) => <TabsTrigger key={item.value} value={item.value}>{item.label}</TabsTrigger>)}</TabsList>
          </Tabs>
          <InputGroup className="wb-radar-search"><InputGroupAddon><SearchIcon aria-hidden="true" /></InputGroupAddon><InputGroupInput aria-label="搜索招采公告" onChange={(event) => setQuery(event.target.value)} placeholder="搜索公告、采购人或区域" value={query} /></InputGroup>
        </div>

        {radarQuery.isLoading ? <div className="wb-radar-loading"><LoaderCircleIcon className="animate-spin" aria-hidden="true" />正在读取雷达队列…</div> : null}
        {!radarQuery.isLoading && !overview?.notices.length ? <div className="wb-radar-empty"><RadarIcon aria-hidden="true" /><strong>{overview?.sources.length ? "当前筛选没有匹配机会" : "从一个公开来源开始"}</strong><p>{overview?.sources.length ? "调整筛选或新建订阅后，新的命中机会会持续出现。" : "接入 RSS 或 JSON Feed，平台会保留来源链接、采集时间和订阅匹配记录。"}</p><Button onClick={() => setSourceDialogOpen(true)} size="sm"><PlusIcon aria-hidden="true" data-icon="inline-start" />管理来源</Button></div> : null}
        {overview?.notices.length ? <div className="wb-radar-notice-list">{overview.notices.map((notice) => {
          const primaryMatch = notice.matches[0];
          return <button className="wb-radar-notice-row" key={notice.id} onClick={() => setSelectedNoticeId(notice.id)} type="button">
            <span className={`wb-radar-notice-marker is-${notice.status}`} aria-hidden="true" />
            <span className="wb-radar-notice-title"><strong>{notice.title}</strong><small>{[notice.buyer_name, notice.region, notice.category].filter(Boolean).join(" · ") || notice.source_name}</small></span>
            <span className="wb-radar-notice-match"><small>匹配依据</small><strong>{primaryMatch ? `${primaryMatch.subscription_name} · ${primaryMatch.score} 分` : "尚未命中订阅"}</strong><em>{primaryMatch?.reasons[0] || "可手动保存后继续研判"}</em></span>
            <span className="wb-radar-notice-deadline"><small>时间窗口</small><strong>{deadlineLabel(notice.deadline_at)}</strong><em>{notice.published_at ? `发布于 ${formatDate(notice.published_at)}` : "发布时间待补充"}</em></span>
            <Badge variant="outline">{noticeTypeLabel(notice.notice_type)}</Badge>
            <ChevronRightIcon aria-hidden="true" />
          </button>;
        })}</div> : null}
      </section>

      <Dialog onOpenChange={setSourceDialogOpen} open={sourceDialogOpen}>
        <DialogContent className="wb-radar-dialog sm:max-w-lg">
          <DialogHeader><DialogTitle>管理采集来源</DialogTitle><DialogDescription>仅接入公开 RSS 或 JSON Feed。服务端会限制重定向、请求时长和下载体积，并保留来源健康状态。</DialogDescription></DialogHeader>
          <div className="wb-radar-source-list">{overview?.sources.map((source) => <div key={source.id}>
            <span><strong>{source.name}</strong><small>{sourceKindLabel(source.kind)} · {source.polling_interval_minutes} 分钟一次</small></span>
            <span className={source.last_error_code ? "is-attention" : ""}>{source.last_error_code ? "需要处理" : source.last_success_at ? "正常" : "等待刷新"}</span>
            <Button aria-label={`刷新 ${source.name}`} disabled={pollSourceMutation.isPending} onClick={() => pollSourceMutation.mutate(source.id)} size="icon-xs" title="立即刷新" variant="ghost"><RefreshCwIcon className={pollSourceMutation.isPending ? "animate-spin" : ""} aria-hidden="true" /></Button>
            <Button disabled={toggleSourceMutation.isPending} onClick={() => toggleSourceMutation.mutate({ sourceId: source.id, isActive: !source.is_active })} size="xs" variant="ghost">{source.is_active ? "暂停" : "启用"}</Button>
          </div>)}</div>
          <FieldGroup className="wb-radar-source-form">
            <Field><FieldLabel htmlFor="radar-source-name">来源名称</FieldLabel><Input id="radar-source-name" onChange={(event) => setSourceName(event.target.value)} placeholder="例如：某省政府采购公告" value={sourceName} /></Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-[minmax(0,1fr)_150px]"><Field><FieldLabel htmlFor="radar-source-kind">数据格式</FieldLabel><Select onValueChange={(value) => value && setSourceKind(value as Extract<NoticeSourceKind, "rss" | "json_feed">)} value={sourceKind}><SelectTrigger id="radar-source-kind"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="rss">RSS Feed</SelectItem><SelectItem value="json_feed">JSON Feed</SelectItem></SelectGroup></SelectContent></Select></Field><Field><FieldLabel htmlFor="radar-source-interval">刷新间隔（分钟）</FieldLabel><Input id="radar-source-interval" max="1440" min="5" onChange={(event) => setSourcePollingMinutes(event.target.value)} type="number" value={sourcePollingMinutes} /></Field></div>
            <Field><FieldLabel htmlFor="radar-source-url">公开地址</FieldLabel><Input id="radar-source-url" onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://example.gov.cn/notices.xml" type="url" value={sourceUrl} /></Field>
          </FieldGroup>
          <DialogFooter><Button onClick={() => setSourceDialogOpen(false)} type="button" variant="outline">取消</Button><Button disabled={!sourceName.trim() || !sourceUrl.trim() || !Number.isInteger(Number(sourcePollingMinutes)) || Number(sourcePollingMinutes) < 5 || Number(sourcePollingMinutes) > 1440 || createSourceMutation.isPending} onClick={submitSource} type="button">{createSourceMutation.isPending ? <LoaderCircleIcon className="animate-spin" aria-hidden="true" /> : <RssIcon aria-hidden="true" />}接入来源</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog onOpenChange={setSubscriptionDialogOpen} open={subscriptionDialogOpen}>
        <DialogContent className="wb-radar-dialog sm:max-w-lg">
          <DialogHeader><DialogTitle>新建招采订阅</DialogTitle><DialogDescription>订阅不是提醒开关，而是团队的机会判断标准。命中后会逐条展示关键词、区域或品类理由。</DialogDescription></DialogHeader>
          <FieldGroup>
            <Field><FieldLabel htmlFor="radar-subscription-name">订阅名称</FieldLabel><Input id="radar-subscription-name" onChange={(event) => setSubscriptionName(event.target.value)} placeholder="例如：华东数字化采购" value={subscriptionName} /></Field>
            <Field><FieldLabel htmlFor="radar-subscription-keywords">关键词</FieldLabel><Input id="radar-subscription-keywords" onChange={(event) => setSubscriptionKeywords(event.target.value)} placeholder="例如：数据治理，智能客服，云平台" value={subscriptionKeywords} /><small className="text-muted-foreground">用中文逗号、英文逗号或换行分隔。</small></Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2"><Field><FieldLabel htmlFor="radar-subscription-regions">关注区域</FieldLabel><Input id="radar-subscription-regions" onChange={(event) => setSubscriptionRegions(event.target.value)} placeholder="例如：上海，江苏" value={subscriptionRegions} /></Field><Field><FieldLabel htmlFor="radar-subscription-categories">采购品类</FieldLabel><Input id="radar-subscription-categories" onChange={(event) => setSubscriptionCategories(event.target.value)} placeholder="例如：软件服务，咨询" value={subscriptionCategories} /></Field></div>
          </FieldGroup>
          <DialogFooter><Button onClick={() => setSubscriptionDialogOpen(false)} type="button" variant="outline">取消</Button><Button disabled={!subscriptionName.trim() || createSubscriptionMutation.isPending} onClick={submitSubscription} type="button">{createSubscriptionMutation.isPending ? <LoaderCircleIcon className="animate-spin" aria-hidden="true" /> : <TargetIcon aria-hidden="true" />}创建订阅</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Sheet onOpenChange={(open) => !open && setSelectedNoticeId(null)} open={Boolean(selectedNotice)}>
        <SheetContent className="wb-radar-notice-sheet gap-0 p-0 sm:max-w-xl" side="right">
          {selectedNotice ? <>
            <SheetHeader className="pr-12"><SheetTitle>{selectedNotice.title}</SheetTitle><SheetDescription>{selectedNotice.buyer_name || selectedNotice.source_name} · {noticeTypeLabel(selectedNotice.notice_type)}</SheetDescription></SheetHeader>
            <div className="min-h-0 flex-1 overflow-auto px-5 pb-6">
              <div className="wb-radar-notice-sheet__status"><span className={`is-${selectedNotice.status}`}><i aria-hidden="true" />{noticeStatusLabel(selectedNotice.status)}</span><span>{deadlineLabel(selectedNotice.deadline_at)}</span></div>
              {selectedNotice.summary ? <p className="wb-radar-notice-sheet__summary">{selectedNotice.summary}</p> : null}
              <section className="wb-radar-notice-sheet__matches"><header><h2>匹配理由</h2><span>{selectedNotice.matches.length} 个订阅命中</span></header>{selectedNotice.matches.length ? selectedNotice.matches.map((match) => <div key={match.subscription_id}><span><TargetIcon aria-hidden="true" /><strong>{match.subscription_name}</strong></span><Badge variant="outline">{match.score} 分</Badge><p>{match.reasons.join("；")}</p></div>) : <p>该公告尚未命中现有订阅。可保存后由团队继续研判。</p>}</section>
              <dl className="wb-radar-notice-sheet__facts"><dt>采购人</dt><dd>{selectedNotice.buyer_name || "待补充"}</dd><dt>区域与品类</dt><dd>{[selectedNotice.region, selectedNotice.category].filter(Boolean).join(" · ") || "待补充"}</dd><dt>预算金额</dt><dd>{formatCurrency(selectedNotice.budget_amount) || "待补充"}</dd><dt>发布时间</dt><dd>{formatDate(selectedNotice.published_at, { year: "numeric", month: "long", day: "numeric" })}</dd><dt>截止时间</dt><dd>{formatDate(selectedNotice.deadline_at, { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })}</dd><dt>采集来源</dt><dd>{selectedNotice.source_name}</dd></dl>
            </div>
            <SheetFooter className="wb-radar-notice-sheet__footer">
              <div><Button disabled={updateNoticeMutation.isPending || selectedNotice.status === "ignored"} onClick={() => updateNoticeMutation.mutate({ noticeId: selectedNotice.id, status: "ignored" })} size="sm" variant="ghost">忽略</Button>{selectedNotice.status !== "saved" ? <Button disabled={updateNoticeMutation.isPending} onClick={() => updateNoticeMutation.mutate({ noticeId: selectedNotice.id, status: "saved" })} size="sm" variant="outline"><BookmarkIcon aria-hidden="true" data-icon="inline-start" />保存研判</Button> : null}</div>
              <div>{selectedNoticeUrl ? <Button onClick={() => window.open(selectedNoticeUrl, "_blank", "noopener,noreferrer")} size="sm" variant="ghost">原始公告<ExternalLinkIcon aria-hidden="true" data-icon="inline-end" /></Button> : null}{selectedNotice.converted_project_id ? <Button onClick={() => navigate(`/projects/${selectedNotice.converted_project_id}`)} size="sm">打开项目<ArrowUpRightIcon aria-hidden="true" data-icon="inline-end" /></Button> : <Button disabled={convertNoticeMutation.isPending} onClick={() => convertNoticeMutation.mutate({ noticeId: selectedNotice.id, projectName: selectedNotice.title })} size="sm">{convertNoticeMutation.isPending ? <LoaderCircleIcon className="animate-spin" aria-hidden="true" /> : <SendIcon aria-hidden="true" />}转为项目</Button>}</div>
            </SheetFooter>
          </> : null}
        </SheetContent>
      </Sheet>
    </section>
  );
}
