import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2Icon,
  ChevronRightIcon,
  FileOutputIcon,
  FileTextIcon,
  FolderKanbanIcon,
  InboxIcon,
  LibraryBigIcon,
  MailPlusIcon,
  PlusIcon,
  Settings2Icon,
  ShieldCheckIcon,
  UsersRoundIcon,
} from "lucide-react";
import { type FormEvent, type ReactNode, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  createInvitation,
  createDeliverable,
  getOrganizationEntitlements,
  listDeliverableSections,
  listDeliverables,
  listInvitations,
  listOrganizationMembers,
  listOrganizations,
  listProjects,
  listProviderConfigs,
  listRequirements,
  listReviewThreads,
  listTeams,
  type DeliverableRead,
  type DeliverableSectionRead,
  type ProjectRead,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { displayDeliverableType, displayWorkbenchValue } from "./workbench-labels";
import { SettingsNavigation } from "./settings-navigation";
import { Skeleton } from "@/components/ui/skeleton";

const EMPTY_PROJECTS: ProjectRead[] = [];
const EMPTY_DELIVERABLES: DeliverableRead[] = [];

function projectLabel(project: ProjectRead) {
  return project.name || project.slug || project.id;
}

function compactDate(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(date);
}

function statusTone(value: string) {
  const normalized = value.toLowerCase();
  if (/(approved|accepted|succeeded|ready|complete|completed|verified)/.test(normalized)) return "complete";
  if (/(review|pending|awaiting|draft)/.test(normalized)) return "approval";
  if (/(fail|error|reject|blocked|gap)/.test(normalized)) return "failed";
  if (/(run|queue|progress|active)/.test(normalized)) return "active";
  return "neutral";
}

function StatusText({ value, label }: { value: string; label?: string }) {
  return (
    <span className={cn("wb-status-text", `wb-status-text--${statusTone(value)}`)}>
      {label ?? displayWorkbenchValue(value)}
    </span>
  );
}

function ProjectScope({
  projects,
  selectedId,
  onSelect,
}: {
  projects: ProjectRead[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="wb-project-scope">
      <FolderKanbanIcon aria-hidden="true" />
      <Select disabled={!projects.length} onValueChange={(value) => value && onSelect(value)} value={selectedId ?? undefined}>
        <SelectTrigger aria-label="选择投标项目"><SelectValue placeholder="选择投标项目" /></SelectTrigger>
        <SelectContent><SelectGroup>{projects.map((project) => <SelectItem key={project.id} value={project.id}>{projectLabel(project)}</SelectItem>)}</SelectGroup></SelectContent>
      </Select>
    </div>
  );
}

function OperationsEmpty({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof FileOutputIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="wb-operations-empty">
      <Icon aria-hidden="true" />
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}

function PendingMetric({ loading, children }: { loading: boolean; children: ReactNode }) {
  return loading ? <span aria-label="正在加载">—</span> : children;
}

function OperationsLoading({ label }: { label: string }) {
  return <div className="flex flex-col gap-3 py-6" role="status" aria-label={label}><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-11/12" /><Skeleton className="h-10 w-4/5" /></div>;
}

export function DeliverablesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: listProjects, staleTime: 30_000 });
  const projects = projectsQuery.data ?? EMPTY_PROJECTS;
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [deliverableTitle, setDeliverableTitle] = useState("");
  const [deliverableType, setDeliverableType] = useState("technical_response");
  const activeProjectId = selectedProjectId ?? projects[0]?.id ?? null;
  const selectedProject = projects.find((project) => project.id === activeProjectId) ?? null;
  const deliverablesQuery = useQuery({
    queryKey: ["deliverables", activeProjectId],
    queryFn: () => listDeliverables(activeProjectId!),
    enabled: Boolean(activeProjectId),
    staleTime: 15_000,
  });
  const deliverables = deliverablesQuery.data ?? EMPTY_DELIVERABLES;
  const sectionQueries = useQueries({
    queries: deliverables.map((deliverable) => ({
      queryKey: ["deliverable-sections", deliverable.id],
      queryFn: () => listDeliverableSections(deliverable.id),
      staleTime: 15_000,
    })),
  });
  const sectionCounts = useMemo(() => new Map(
    deliverables.map((deliverable, index) => [deliverable.id, sectionQueries[index]?.data?.length ?? 0]),
  ), [deliverables, sectionQueries]);
  const exportedCount = deliverables.filter((deliverable) => deliverable.export_status === "exported").length;
  const reviewCount = deliverables.filter((deliverable) => /(draft|review|pending)/i.test(deliverable.status)).length;
  const deliverablesLoading = deliverablesQuery.isLoading || sectionQueries.some((query) => query.isLoading);
  const createMutation = useMutation({
    mutationFn: createDeliverable,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["deliverables", activeProjectId] });
      setCreateOpen(false);
      setDeliverableTitle("");
      toast.success("交付物已创建，可在项目中编排章节并提交审核。");
    },
    onError: () => toast.error("交付物未能创建。"),
  });

  return (
    <section className="wb-workboard-page" aria-labelledby="deliverables-title">
      <header className="wb-workboard-header">
        <div><p className="wb-eyebrow">Response operations</p><h1 id="deliverables-title">{t("nav.deliverables")}</h1><p>集中查看响应文件的章节覆盖、审核状态与导出准备情况。</p></div>
        <div className="flex flex-wrap items-center justify-end gap-2"><ProjectScope onSelect={setSelectedProjectId} projects={projects} selectedId={activeProjectId} /><Button disabled={!activeProjectId} onClick={() => setCreateOpen(true)} size="sm"><PlusIcon aria-hidden="true" data-icon="inline-start" />新建交付物</Button></div>
      </header>
      <ScrollArea className="wb-workboard-scroll"><div className="wb-workboard-content">
        {projectsQuery.isLoading ? <OperationsLoading label="正在读取投标项目" /> : selectedProject ? <>
          <section className="wb-workboard-summary" aria-label="交付物概览">
            <div><span>当前项目</span><strong>{projectLabel(selectedProject)}</strong><small>{displayWorkbenchValue(selectedProject.status)}</small></div>
            <div><span>交付物</span><strong><PendingMetric loading={deliverablesLoading}>{deliverables.length}</PendingMetric></strong><small>已建立的响应文件</small></div>
            <div><span>待审核</span><strong><PendingMetric loading={deliverablesLoading}>{reviewCount}</PendingMetric></strong><small>需要内部确认</small></div>
            <div><span>已导出</span><strong><PendingMetric loading={deliverablesLoading}>{exportedCount}</PendingMetric></strong><small>可供提交或归档</small></div>
          </section>
          <section className="wb-workboard-section">
            <header><div><h2>响应文件</h2><p>从章节完整度和导出状态判断交付准备程度。</p></div><Button onClick={() => navigate(`/projects/${selectedProject.id}`)} size="sm" variant="outline">打开项目 <ChevronRightIcon aria-hidden="true" data-icon="inline-end" /></Button></header>
             {deliverablesLoading ? <OperationsLoading label="正在读取交付物" /> : null}
            {!deliverablesQuery.isLoading && deliverables.length === 0 ? <OperationsEmpty description="项目中还没有创建交付物。可在项目工作区或通过 Agent 创建。" icon={FileOutputIcon} title="暂无交付物" /> : null}
            {deliverables.length > 0 ? <div className="wb-workboard-table wb-deliverables-table"><div className="wb-workboard-table-head"><span>交付物</span><span>类型</span><span>章节</span><span>内容状态</span><span>导出</span></div>{deliverables.map((deliverable) => <DeliverableRow deliverable={deliverable} key={deliverable.id} sectionCount={sectionCounts.get(deliverable.id) ?? 0} />)}</div> : null}
          </section>
        </> : <OperationsEmpty description="创建投标项目后，响应文件和导出记录会出现在这里。" icon={FileOutputIcon} title="选择一个项目" />}
      </div></ScrollArea>
      <Dialog onOpenChange={setCreateOpen} open={createOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>新建交付物</DialogTitle><DialogDescription>建立一个可编排章节、提交审核并导出的响应文件。创建后不会自动跳转或启动起草。</DialogDescription></DialogHeader>
          <FieldGroup><Field><FieldLabel htmlFor="deliverable-title">交付物名称</FieldLabel><Input id="deliverable-title" onChange={(event) => setDeliverableTitle(event.target.value)} placeholder="例如：技术响应文件" value={deliverableTitle} /></Field><Field><FieldLabel htmlFor="deliverable-type">文件类型</FieldLabel><Select onValueChange={(value) => value && setDeliverableType(value)} value={deliverableType}><SelectTrigger id="deliverable-type"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="technical_response">技术响应</SelectItem><SelectItem value="commercial_response">商务响应</SelectItem><SelectItem value="bid_response">完整投标响应</SelectItem><SelectItem value="proposal">投标方案</SelectItem></SelectGroup></SelectContent></Select></Field></FieldGroup>
          <DialogFooter><Button onClick={() => setCreateOpen(false)} type="button" variant="outline">取消</Button><Button disabled={!activeProjectId || !deliverableTitle.trim() || createMutation.isPending} onClick={() => activeProjectId && createMutation.mutate({ project_id: activeProjectId, title: deliverableTitle.trim(), type: deliverableType })} type="button">创建交付物</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function DeliverableRow({ deliverable, sectionCount }: { deliverable: DeliverableRead; sectionCount: number }) {
  return (
    <div className="wb-workboard-table-row">
      <span className="wb-workboard-primary"><FileTextIcon aria-hidden="true" /> {deliverable.title}</span>
      <span>{displayDeliverableType(deliverable.type)}</span>
      <span>{sectionCount}</span>
      <StatusText value={deliverable.status} />
      <StatusText value={deliverable.export_status} />
    </div>
  );
}

type ReviewSection = {
  deliverable: DeliverableRead;
  section: DeliverableSectionRead;
  threadCount: number;
  openThreadCount: number;
};

export function ReviewsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: listProjects, staleTime: 30_000 });
  const projects = projectsQuery.data ?? EMPTY_PROJECTS;
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const activeProjectId = selectedProjectId ?? projects[0]?.id ?? null;
  const selectedProject = projects.find((project) => project.id === activeProjectId) ?? null;
  const deliverablesQuery = useQuery({
    queryKey: ["deliverables", activeProjectId],
    queryFn: () => listDeliverables(activeProjectId!),
    enabled: Boolean(activeProjectId),
    staleTime: 15_000,
  });
  const requirementsQuery = useQuery({
    queryKey: ["requirements", activeProjectId],
    queryFn: () => listRequirements(activeProjectId!),
    enabled: Boolean(activeProjectId),
    staleTime: 15_000,
  });
  const deliverables = deliverablesQuery.data ?? EMPTY_DELIVERABLES;
  const sectionQueries = useQueries({
    queries: deliverables.map((deliverable) => ({
      queryKey: ["deliverable-sections", deliverable.id],
      queryFn: () => listDeliverableSections(deliverable.id),
      staleTime: 15_000,
    })),
  });
  const sections = useMemo(() => deliverables.flatMap((deliverable, index) => (
    (sectionQueries[index]?.data ?? []).map((section) => ({ deliverable, section }))
  )), [deliverables, sectionQueries]);
  const threadQueries = useQueries({
    queries: sections.map(({ section }) => ({
      queryKey: ["review-threads", section.id],
      queryFn: () => listReviewThreads(section.id),
      staleTime: 15_000,
    })),
  });
  const reviewSections = useMemo<ReviewSection[]>(() => sections.map(({ deliverable, section }, index) => {
    const threads = threadQueries[index]?.data ?? [];
    return {
      deliverable,
      section,
      threadCount: threads.length,
      openThreadCount: threads.filter((thread) => thread.status !== "resolved").length,
    };
  }), [sections, threadQueries]);
  const unverifiedRequirements = useMemo(
    () => (requirementsQuery.data ?? []).filter((requirement) => requirement.verification_status !== "verified"),
    [requirementsQuery.data],
  );
  const reviewLoading = deliverablesQuery.isLoading || requirementsQuery.isLoading || sectionQueries.some((query) => query.isLoading) || threadQueries.some((query) => query.isLoading);

  return (
    <section className="wb-workboard-page" aria-labelledby="reviews-title">
      <header className="wb-workboard-header"><div><p className="wb-eyebrow">Quality control</p><h1 id="reviews-title">{t("nav.reviews")}</h1><p>把章节评审和证据核验放在同一条待办队列中，优先处理影响提交的事项。</p></div><ProjectScope onSelect={setSelectedProjectId} projects={projects} selectedId={activeProjectId} /></header>
      <ScrollArea className="wb-workboard-scroll"><div className="wb-workboard-content">
        {projectsQuery.isLoading ? <OperationsLoading label="正在读取投标项目" /> : selectedProject ? <>
          <section className="wb-workboard-summary" aria-label="审核概览"><div><span>当前项目</span><strong>{projectLabel(selectedProject)}</strong><small>{displayWorkbenchValue(selectedProject.status)}</small></div><div><span>章节评审</span><strong><PendingMetric loading={reviewLoading}>{reviewSections.length}</PendingMetric></strong><small>已进入评审范围</small></div><div><span>未解决线程</span><strong><PendingMetric loading={reviewLoading}>{reviewSections.reduce((count, item) => count + item.openThreadCount, 0)}</PendingMetric></strong><small>等待响应或处理</small></div><div><span>待核验要求</span><strong><PendingMetric loading={reviewLoading}>{unverifiedRequirements.length}</PendingMetric></strong><small>尚未形成可审证据</small></div></section>
          <section className="wb-workboard-section"><header><div><h2>章节评审</h2><p>按开放线程优先，确认每个响应章节可进入下一轮。</p></div><Button onClick={() => navigate(`/projects/${selectedProject.id}`)} size="sm" variant="outline">进入项目 <ChevronRightIcon aria-hidden="true" data-icon="inline-end" /></Button></header>
              {reviewLoading ? <OperationsLoading label="正在读取交付物与章节" /> : null}
              {!deliverablesQuery.isLoading && reviewSections.length === 0 ? (
                <p className="wb-inline-empty">当前项目还没有可评审章节。</p>
              ) : null}
              {reviewSections.length > 0 ? (
                <div className="wb-workboard-table wb-reviews-table">
                  <div className="wb-workboard-table-head">
                    <span>章节</span><span>交付物</span><span>线程</span><span>未解决</span><span>状态</span>
                  </div>
                  {reviewSections.map(({ deliverable, section, threadCount, openThreadCount }) => (
                    <div className="wb-workboard-table-row" key={section.id}>
                      <span className="wb-workboard-primary"><FileTextIcon aria-hidden="true" /> {section.title}</span>
                      <span>{deliverable.title}</span>
                      <span>{threadCount}</span>
                      <span>{openThreadCount}</span>
                      <StatusText value={section.status} />
                    </div>
                  ))}
                </div>
              ) : null}
          </section>

          <section className="wb-workboard-section"><header><div><h2>待核验证据要求</h2><p>未核验的要求会直接影响响应内容的可信度。</p></div></header>
              {requirementsQuery.isLoading ? <OperationsLoading label="正在读取要求状态" /> : null}
              {!requirementsQuery.isLoading && unverifiedRequirements.length === 0 ? (
                <p className="wb-inline-empty">所有已提取要求均已标记为已核验，或当前项目尚未提取要求。</p>
              ) : null}
              {unverifiedRequirements.length > 0 ? (
                <div className="wb-workboard-table wb-requirement-review-table">
                  <div className="wb-workboard-table-head">
                    <span>要求</span><span>来源</span><span>优先级</span><span>核验</span>
                  </div>
                  {unverifiedRequirements.slice(0, 50).map((requirement) => (
                    <div className="wb-workboard-table-row" key={requirement.id}>
                      <span className="wb-workboard-primary wb-workboard-primary--copy"><ShieldCheckIcon aria-hidden="true" /> {requirement.requirement_text}</span>
                      <span>{requirement.source_document_name || "-"}</span>
                      <span>{displayWorkbenchValue(requirement.priority)}</span>
                      <StatusText value={requirement.verification_status} />
                    </div>
                  ))}
                </div>
              ) : null}
          </section>
        </> : <OperationsEmpty description="创建投标项目后，章节审核和证据核验会出现在这里。" icon={ShieldCheckIcon} title="选择一个项目" />}
      </div></ScrollArea>
    </section>
  );
}

export function MembersPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const membersQuery = useQuery({ queryKey: ["organization-members"], queryFn: listOrganizationMembers, staleTime: 30_000 });
  const teamsQuery = useQuery({ queryKey: ["teams"], queryFn: listTeams, staleTime: 30_000 });
  const invitationsQuery = useQuery({ queryKey: ["invitations"], queryFn: listInvitations, staleTime: 30_000 });
  const [email, setEmail] = useState("");
  const inviteMutation = useMutation({
    mutationFn: createInvitation,
    onSuccess: () => {
      setEmail("");
      toast.success("邀请已发送。");
      void queryClient.invalidateQueries({ queryKey: ["invitations"] });
    },
    onError: (error: Error) => toast.error(error.message || "邀请未能发送。"),
  });
  const members = membersQuery.data ?? [];
  const teams = teamsQuery.data?.items ?? [];
  const invitations = invitationsQuery.data ?? [];

  const submitInvitation = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = email.trim();
    if (!normalized) return;
    inviteMutation.mutate({ email: normalized });
  };

  return (
    <section className="wb-workboard-page wb-members-workboard" aria-labelledby="members-title">
      <header className="wb-workboard-header">
        <div>
          <p className="wb-eyebrow">Response team</p>
          <h1 id="members-title">{t("nav.members")}</h1>
          <p>集中管理参与投标响应的成员、角色、团队归属与待接受邀请。</p>
        </div>
        <form className="wb-invite-form" onSubmit={submitInvitation}>
          <Input
            aria-label="邀请成员邮箱"
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="name@company.com"
            type="email"
            value={email}
          />
          <Button disabled={inviteMutation.isPending} size="sm" type="submit">
            <MailPlusIcon aria-hidden="true" data-icon="inline-start" /> 邀请成员
          </Button>
        </form>
      </header>
      <ScrollArea className="wb-workboard-scroll">
        <div className="wb-workboard-content">
      <section className="wb-workboard-section">
        <header><div><h2>组织成员</h2><p>成员身份和账单责任保持在同一个可扫描目录中。</p></div><span className="wb-section-total">{members.length} 人</span></header>
        {membersQuery.isLoading ? <p className="wb-list-loading">正在读取成员…</p> : null}
        {!membersQuery.isLoading && members.length === 0 ? <p className="wb-inline-empty">当前组织还没有成员。</p> : null}
        {members.length > 0 ? (
          <div className="wb-workboard-table wb-members-table">
            <div className="wb-workboard-table-head">
              <span>成员</span><span>邮箱</span><span>角色</span><span>账单</span>
            </div>
            {members.map((member) => (
              <div className="wb-workboard-table-row" key={member.id}>
                <span className="wb-workboard-primary"><UsersRoundIcon aria-hidden="true" /> {member.display_name}</span>
                <span>{member.email}</span>
                <span>{displayWorkbenchValue(member.role)}</span>
                <span>{member.is_billing_owner ? "账单负责人" : "-"}</span>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="wb-workboard-section">
        <header>
          <div><h2>响应团队</h2><p>把负责不同章节、资料或评审阶段的成员组织成可复用团队。</p></div>
          <Button onClick={() => navigate("/admin/teams")} size="xs" variant="ghost">管理团队 <ChevronRightIcon aria-hidden="true" data-icon="inline-end" /></Button>
        </header>
        {teamsQuery.isLoading ? <p className="wb-list-loading">正在读取团队…</p> : null}
        {!teamsQuery.isLoading && teams.length === 0 ? <p className="wb-inline-empty">尚未创建响应团队。</p> : null}
        {teams.length > 0 ? (
          <div className="wb-workboard-table wb-teams-table">
            <div className="wb-workboard-table-head"><span>团队</span><span>标识</span><span>成员数</span></div>
            {teams.map((team) => (
              <div className="wb-workboard-table-row" key={team.id}>
                <span className="wb-workboard-primary"><UsersRoundIcon aria-hidden="true" /> {team.name}</span>
                <span>{team.slug}</span>
                <span>{team.members?.length ?? 0}</span>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="wb-workboard-section">
        <header><div><h2>待接受邀请</h2><p>只有未加入工作区的邀请会保留在此处。</p></div></header>
        {invitationsQuery.isLoading ? <p className="wb-list-loading">正在读取邀请…</p> : null}
        {!invitationsQuery.isLoading && invitations.length === 0 ? <p className="wb-inline-empty">没有待处理的邀请。</p> : null}
        {invitations.length > 0 ? (
          <div className="wb-workboard-table wb-invitations-table">
            <div className="wb-workboard-table-head"><span>邮箱</span><span>状态</span><span>创建时间</span></div>
            {invitations.map((invitation) => (
              <div className="wb-workboard-table-row" key={invitation.id}>
                <span className="wb-workboard-primary"><InboxIcon aria-hidden="true" /> {invitation.email}</span>
                <StatusText value={invitation.status} />
                <span>{compactDate(invitation.created_at)}</span>
              </div>
            ))}
          </div>
        ) : null}
      </section>
        </div>
      </ScrollArea>
    </section>
  );
}

export function AdministrationPage() {
  const navigate = useNavigate();
  const entitlementsQuery = useQuery({ queryKey: ["organization-entitlements"], queryFn: getOrganizationEntitlements, staleTime: 30_000 });
  const organizationsQuery = useQuery({ queryKey: ["organizations"], queryFn: listOrganizations, staleTime: 30_000 });
  const providersQuery = useQuery({ queryKey: ["provider-configs"], queryFn: listProviderConfigs, staleTime: 30_000 });
  const entitlements = entitlementsQuery.data;
  const providers = providersQuery.data?.data ?? [];

  return (
    <section className="wb-settings-page wb-organization-settings" aria-labelledby="administration-title">
      <SettingsNavigation />
      <main className="wb-settings-main">
        <div className="wb-settings-content">
          <header className="wb-settings-content-head">
            <div>
              <p className="wb-settings-eyebrow">工作区设置</p>
              <h1 id="administration-title">组织设置</h1>
              <p>管理团队边界、模型连接和可用容量。项目、资料、响应与审阅仍在各自的业务工作台中执行。</p>
            </div>
          </header>

          <section className="wb-settings-section" aria-labelledby="organization-capacity-title">
            <div className="wb-settings-section-head">
              <div><h2 id="organization-capacity-title">当前容量</h2><p>开始批量解析或起草前，先确认团队仍有可用资源。</p></div>
            </div>
            {entitlementsQuery.isLoading ? <p className="wb-list-loading">正在读取组织额度…</p> : null}
            {entitlements ? (
              <div className="wb-organization-capacity">
                <div><span>套餐</span><strong>{displayWorkbenchValue(entitlements.plan)}</strong><small>{displayWorkbenchValue(entitlements.subscription_status)}</small></div>
                <div><span>成员席位</span><strong>{entitlements.active_member_count} / {entitlements.seat_limit}</strong><small>{entitlements.available_seats} 个可用</small></div>
                <div><span>项目上限</span><strong>{entitlements.project_limit}</strong><small>当前工作区</small></div>
                <div><span>本月工作流</span><strong>{entitlements.monthly_workflow_limit}</strong><small>用于解析与起草</small></div>
              </div>
            ) : null}
          </section>

          <section className="wb-settings-section" aria-labelledby="organization-actions-title">
            <div className="wb-settings-section-head">
              <div><h2 id="organization-actions-title">组织操作</h2><p>这些入口对应已接入的平台能力，不在这里重复放置项目级操作。</p></div>
            </div>
            <div className="wb-settings-action-list">
              <Button className="wb-settings-action-row" onClick={() => navigate("/members")} type="button" variant="ghost">
                <UsersRoundIcon aria-hidden="true" />
                <span><strong>成员与权限</strong><small>{entitlements ? `${entitlements.active_member_count} 位成员正在使用此工作区` : "管理成员、邀请和职责边界"}</small></span>
                <ChevronRightIcon aria-hidden="true" />
              </Button>
              <Button className="wb-settings-action-row" onClick={() => navigate("/admin/teams")} type="button" variant="ghost">
                <FolderKanbanIcon aria-hidden="true" />
                <span><strong>响应团队</strong><small>按资料、章节和审阅职责组织投标协作。</small></span>
                <ChevronRightIcon aria-hidden="true" />
              </Button>
              <Button className="wb-settings-action-row" onClick={() => navigate("/settings/providers")} type="button" variant="ghost">
                <Settings2Icon aria-hidden="true" />
                <span><strong>集成与模型</strong><small>{providers.length ? `已保存 ${providers.length} 条模型连接` : "配置并测试 Agent 与工作流可用的模型连接"}</small></span>
                <ChevronRightIcon aria-hidden="true" />
              </Button>
            </div>
          </section>

          <section className="wb-settings-section" aria-labelledby="providers-title">
            <div className="wb-settings-section-head wb-settings-section-head--row">
              <div><h2 id="providers-title">已连接模型</h2><p>只显示已保存的连接及生效状态，密钥不会显示在这里。</p></div>
              <Button onClick={() => navigate("/settings/providers")} size="sm" type="button" variant="outline">管理连接</Button>
            </div>
            {providersQuery.isLoading ? <p className="wb-list-loading">正在读取提供商配置…</p> : null}
            {!providersQuery.isLoading && providers.length === 0 ? <p className="wb-inline-empty">尚未配置模型连接。先添加并测试一个连接，Agent 与响应工作流才能使用它。</p> : null}
            {providers.length > 0 ? (
              <div className="wb-organization-provider-list">
                {providers.map((provider) => (
                  <div className="wb-organization-provider-row" key={provider.id}>
                    <LibraryBigIcon aria-hidden="true" />
                    <span><strong>{provider.label}</strong><small>{displayWorkbenchValue(provider.provider_type)} · {provider.model}</small></span>
                    <StatusText value={provider.is_active ? "active" : "inactive"} />
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className="wb-settings-section" aria-labelledby="workspace-boundary-title">
            <div className="wb-settings-section-head">
              <div><h2 id="workspace-boundary-title">可访问工作区</h2><p>账户可访问的组织边界，用于避免跨团队误操作。</p></div>
            </div>
            {organizationsQuery.isLoading ? <p className="wb-list-loading">正在读取工作区…</p> : null}
            {!organizationsQuery.isLoading && (organizationsQuery.data?.length ?? 0) === 0 ? <p className="wb-inline-empty">当前账户没有其他工作区。</p> : null}
            {(organizationsQuery.data?.length ?? 0) > 0 ? (
              <div className="wb-organization-provider-list">
                {organizationsQuery.data?.map((organization) => (
                  <div className="wb-organization-provider-row" key={organization.id}>
                    <CheckCircle2Icon aria-hidden="true" />
                    <span><strong>{organization.name}</strong><small>{organization.slug}</small></span>
                  </div>
                ))}
              </div>
            ) : null}
          </section>
        </div>
      </main>
    </section>
  );
}
