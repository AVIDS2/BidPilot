import { useEffect, useState, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { useTranslation } from "react-i18next";
import {
  BookOpenIcon,
  RocketIcon,
  CpuIcon,
  LayersIcon,
  CodeIcon,
  ServerIcon,
  ChevronRightIcon,
  ArrowLeftIcon,
  FileTextIcon,
  SearchIcon,
  PenToolIcon,
  ShieldCheckIcon,
  DownloadIcon,
  FolderIcon,
  BrainCircuitIcon,
  GitBranchIcon,
  CheckCircleIcon,
  CopyIcon,
  CheckIcon,
  MenuIcon,
  XIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import AnimatedContent from "@/components/AnimatedContent";
import { ProductGlareCard, ProductShinyText } from "@/components/reactbits-product";

// ---------- ScrollReveal (老师风格) ----------
function ScrollReveal({
  children,
  className = "",
  delay = 0,
  direction = "up",
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  direction?: "up" | "down" | "left" | "right";
}) {
  return (
    <AnimatedContent
      className={className}
      distance={40}
      direction={direction === "left" || direction === "right" ? "horizontal" : "vertical"}
      reverse={direction === "down" || direction === "right"}
      duration={0.8}
      delay={delay / 1000}
      threshold={0.08}
    >
      {children}
    </AnimatedContent>
  );
}

// ---------- Code Block 组件 ----------
function CodeBlock({
  children,
  language = "bash",
  filename,
}: {
  children: string;
  language?: string;
  filename?: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(children.trim());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [children]);

  return (
    <ProductGlareCard>
      <div
        className="relative group my-6 w-full overflow-hidden"
        style={{
          background: "var(--card)",
          border: "1px solid var(--border)",
        }}
      >
        {/* 标题栏 */}
        <div
          className="flex items-center justify-between px-4 py-2.5"
          style={{
            borderBottom: "1px solid var(--border)",
            background: "var(--background)",
          }}
        >
          <div className="flex items-center gap-3">
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--muted-foreground)" }} />
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--muted-foreground)" }} />
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--muted-foreground)" }} />
            </div>
            {filename && (
              <span className="text-xs font-mono" style={{ color: "var(--muted-foreground)" }}>
                {filename}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono tracking-wider uppercase" style={{ color: "var(--muted-foreground)" }}>
              {language}
            </span>
            <button
              onClick={handleCopy}
              className="p-1.5 transition-all duration-200 hover:scale-110"
              style={{
                color: copied ? "var(--primary)" : "var(--muted-foreground)",
              }}
              title="Copy code"
            >
              {copied ? <CheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}
            </button>
          </div>
        </div>

        {/* 代码内容 */}
        <pre className="p-5 overflow-x-auto text-sm leading-relaxed font-mono" style={{ color: "var(--muted-foreground)" }}>
          <code>{children.trim()}</code>
        </pre>
      </div>
    </ProductGlareCard>
  );
}

// ---------- Feature Card 组件 ----------
function FeatureCard({
  icon: Icon,
  title,
  description,
  index,
}: {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  title: string;
  description: string;
  index: number;
}) {
  return (
    <ScrollReveal delay={index * 100}>
      <ProductGlareCard>
        <div
          className="group w-full p-7 transition-all duration-300 hover:-translate-y-1"
          style={{
            border: "1px solid var(--border)",
            background: "var(--card)",
          }}
        >
          <div
            className="w-10 h-10 flex items-center justify-center mb-5"
            style={{
              background: "rgba(132, 204, 22, 0.1)",
              border: "1px solid var(--border)",
            }}
          >
            <Icon className="w-5 h-5" style={{ color: "var(--primary)" }} />
          </div>
          <h3 className="text-lg font-medium mb-2" style={{ color: "var(--foreground)" }}>
            {title}
          </h3>
          <p className="text-sm leading-relaxed" style={{ color: "var(--muted-foreground)" }}>
            {description}
          </p>
        </div>
      </ProductGlareCard>
    </ScrollReveal>
  );
}

// ---------- Section Heading 组件 ----------
function SectionHeading({
  label,
  title,
  description,
}: {
  label: string;
  title: string;
  description: string;
}) {
  return (
    <ScrollReveal>
      <span
        className="text-xs font-medium tracking-widest uppercase mb-4 block"
        style={{ color: "var(--primary)" }}
      >
        {label}
      </span>
      <h2
        className="text-3xl md:text-4xl font-medium leading-tight tracking-tight mb-4"
        style={{ color: "var(--foreground)" }}
      >
        <ProductShinyText text={title} />
      </h2>
      <p className="text-lg max-w-2xl mb-14" style={{ color: "var(--muted-foreground)" }}>
        {description}
      </p>
    </ScrollReveal>
  );
}

// ---------- 导航数据 ----------
interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
}

function buildNavItems(t: (key: string) => string): NavItem[] {
  return [
    { id: "overview", label: t("nav.overview"), icon: BookOpenIcon },
    { id: "quickstart", label: t("nav.quickstart"), icon: RocketIcon },
    { id: "features", label: t("nav.features"), icon: LayersIcon },
    { id: "architecture", label: t("nav.architecture"), icon: CpuIcon },
    { id: "techstack", label: t("nav.techstack"), icon: CodeIcon },
    { id: "deployment", label: t("nav.deployment"), icon: ServerIcon },
  ];
}

// ---------- Section 1: Overview ----------
function OverviewSection() {
  const { t } = useTranslation("docs");
  const pipelineSteps = t("overview.pipelineSteps", {
    returnObjects: true,
  }) as unknown as string[];

  return (
    <section id="overview" className="pt-8 pb-20">
      <ScrollReveal>
        <div className="mb-12">
          <span
            className="text-xs font-medium tracking-widest uppercase mb-4 block"
            style={{ color: "var(--primary)" }}
          >
            {t("overview.label")}
          </span>
          <h1
            className="text-5xl md:text-6xl font-medium leading-[0.9] tracking-tight mb-6"
            style={{ color: "var(--foreground)" }}
          >
            {t("overview.titleLine1")}
            <br />
            <span style={{ color: "var(--primary)" }}>{t("overview.titleLine2")}</span>
          </h1>
          <p className="text-xl leading-relaxed max-w-2xl" style={{ color: "var(--muted-foreground)" }}>
            {t("overview.description")}
          </p>
        </div>
      </ScrollReveal>

      {/* 概述卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-16">
        {[
          {
            icon: BrainCircuitIcon,
            title: t("overview.aiNativeTitle"),
            desc: t("overview.aiNativeDesc"),
          },
          {
            icon: GitBranchIcon,
            title: t("overview.statefulTitle"),
            desc: t("overview.statefulDesc"),
          },
          {
            icon: ShieldCheckIcon,
            title: t("overview.enterpriseTitle"),
            desc: t("overview.enterpriseDesc"),
          },
        ].map((item, i) => (
          <FeatureCard key={item.title} icon={item.icon} title={item.title} description={item.desc} index={i} />
        ))}
      </div>

      {/* 流程概览 */}
      <ScrollReveal>
        <div
          className="p-8"
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
          }}
        >
          <h3 className="text-lg font-medium mb-6" style={{ color: "var(--foreground)" }}>
            {t("overview.pipelineTitle")}
          </h3>
          <div className="flex flex-wrap items-center gap-3">
            {pipelineSteps.map((step, i, arr) => (
              <div key={step} className="flex items-center gap-3">
                <div
                  className="px-4 py-2 text-xs font-medium tracking-wide"
                  style={{
                    background: "rgba(132, 204, 22, 0.08)",
                    border: "1px solid var(--border)",
                    color: "var(--primary)",
                  }}
                >
                  {step}
                </div>
                {i < arr.length - 1 && (
                  <ChevronRightIcon className="size-4 shrink-0" style={{ color: "var(--muted-foreground)" }} />
                )}
              </div>
            ))}
          </div>
        </div>
      </ScrollReveal>
    </section>
  );
}

// ---------- Section 2: Quick Start ----------
function QuickStartSection() {
  const { t } = useTranslation("docs");

  return (
    <section id="quickstart" className="py-20">
      <SectionHeading
        label={t("quickstart.label")}
        title={t("quickstart.title")}
        description={t("quickstart.description")}
      />

      <div className="space-y-12">
        {/* Prerequisites */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--foreground)" }}>
            {t("quickstart.prerequisites")}
          </h3>
          <ul className="space-y-3">
            {[
              t("quickstart.prereq1"),
              t("quickstart.prereq2"),
              t("quickstart.prereq3"),
              t("quickstart.prereq4"),
            ].map((item) => (
              <li key={item} className="flex items-start gap-3">
                <CheckCircleIcon className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "var(--primary)" }} />
                <span className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                  {item}
                </span>
              </li>
            ))}
          </ul>
        </ScrollReveal>

        {/* Installation */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--foreground)" }}>
            {t("quickstart.installation")}
          </h3>
          <p className="text-sm mb-4" style={{ color: "var(--muted-foreground)" }}>
            {t("quickstart.installDesc")}
          </p>
          <CodeBlock language="bash" filename="terminal">
{`git clone https://github.com/your-org/BidPilot.git
cd BidPilot

# Copy environment template
cp .env.example .env

# Start all services
docker compose up -d

# Verify health
curl http://localhost:8000/health`}
          </CodeBlock>
        </ScrollReveal>

        {/* Environment Configuration */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--foreground)" }}>
            {t("quickstart.envConfig")}
          </h3>
          <p className="text-sm mb-4" style={{ color: "var(--muted-foreground)" }}>
            {t("quickstart.envDesc1")} <code className="px-1.5 py-0.5 text-xs font-mono" style={{ background: "var(--muted)", color: "var(--primary)" }}>.env</code> {t("quickstart.envDesc2")}
          </p>
          <CodeBlock language="env" filename=".env">
{`# Database
DATABASE_URL=postgresql+asyncpg://BidPilot:secret@postgres:5432/BidPilot

# Redis (task queue + cache)
REDIS_URL=redis://redis:6379/0

# MinIO (document storage)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# LLM Provider
OPENAI_API_KEY=<server-side-openai-api-key>
# or
ANTHROPIC_API_KEY=<server-side-anthropic-api-key>

# Vector Store (pgvector)
EMBEDDING_MODEL=text-embedding-3-small`}
          </CodeBlock>
        </ScrollReveal>

        {/* First Project */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--foreground)" }}>
            {t("quickstart.firstProject")}
          </h3>
          <div className="space-y-4">
            {[
              { num: "01", title: t("quickstart.step1Title"), desc: t("quickstart.step1Desc") },
              { num: "02", title: t("quickstart.step2Title"), desc: t("quickstart.step2Desc") },
              { num: "03", title: t("quickstart.step3Title"), desc: t("quickstart.step3Desc") },
              { num: "04", title: t("quickstart.step4Title"), desc: t("quickstart.step4Desc") },
            ].map((step, i) => (
              <ScrollReveal key={step.num} delay={i * 100} direction="left">
                <div className="flex gap-5 items-start">
                  <div
                    className="shrink-0 w-10 h-10 flex items-center justify-center text-sm font-mono font-medium"
                    style={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      color: "var(--primary)",
                    }}
                  >
                    {step.num}
                  </div>
                  <div className="pt-1">
                    <h4 className="text-sm font-medium mb-1" style={{ color: "var(--foreground)" }}>
                      {step.title}
                    </h4>
                    <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                      {step.desc}
                    </p>
                  </div>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}

// ---------- Section 3: Core Features ----------
function CoreFeaturesSection() {
  const { t } = useTranslation("docs");
  const features = [
    {
      icon: FolderIcon,
      title: t("features.projectMgmtTitle"),
      desc: t("features.projectMgmtDesc"),
    },
    {
      icon: FileTextIcon,
      title: t("features.docIngestTitle"),
      desc: t("features.docIngestDesc"),
    },
    {
      icon: SearchIcon,
      title: t("features.reqExtractTitle"),
      desc: t("features.reqExtractDesc"),
    },
    {
      icon: BrainCircuitIcon,
      title: t("features.knowledgeTitle"),
      desc: t("features.knowledgeDesc"),
    },
    {
      icon: PenToolIcon,
      title: t("features.draftingTitle"),
      desc: t("features.draftingDesc"),
    },
    {
      icon: ShieldCheckIcon,
      title: t("features.qualityTitle"),
      desc: t("features.qualityDesc"),
    },
    {
      icon: CheckCircleIcon,
      title: t("features.approvalTitle"),
      desc: t("features.approvalDesc"),
    },
    {
      icon: DownloadIcon,
      title: t("features.exportTitle"),
      desc: t("features.exportDesc"),
    },
  ];

  return (
    <section id="features" className="py-20">
      <SectionHeading
        label={t("features.label")}
        title={t("features.title")}
        description={t("features.description")}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {features.map((f, i) => (
          <FeatureCard key={f.title} icon={f.icon} title={f.title} description={f.desc} index={i} />
        ))}
      </div>
    </section>
  );
}

// ---------- Section 4: Architecture ----------
function ArchitectureSection() {
  const { t } = useTranslation("docs");
  return (
    <section id="architecture" className="py-20">
      <SectionHeading
        label={t("architecture.label")}
        title={t("architecture.title")}
        description={t("architecture.description")}
      />

      {/* Architecture Diagram */}
      <ScrollReveal>
        <div
          className="p-8 mb-10"
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
          }}
        >
          <h3 className="text-lg font-medium mb-6" style={{ color: "var(--foreground)" }}>
            {t("architecture.systemLayers")}
          </h3>
          <div className="space-y-4">
            {[
              {
                layer: t("architecture.webApp"),
                tech: t("architecture.webAppTech"),
                color: "var(--primary)",
                desc: t("architecture.webAppDesc"),
              },
              {
                layer: t("architecture.apiApp"),
                tech: t("architecture.apiAppTech"),
                color: "var(--primary)",
                desc: t("architecture.apiAppDesc"),
              },
              {
                layer: t("architecture.workerApp"),
                tech: t("architecture.workerAppTech"),
                color: "var(--primary)",
                desc: t("architecture.workerAppDesc"),
              },
              {
                layer: t("architecture.dataServices"),
                tech: t("architecture.dataServicesTech"),
                color: "var(--primary)",
                desc: t("architecture.dataServicesDesc"),
              },
            ].map((item, i) => (
              <ScrollReveal key={item.layer} delay={i * 120} direction="left">
                <div
                  className="flex flex-col md:flex-row md:items-center gap-4 p-5 transition-all duration-300"
                  style={{
                    background: "var(--background)",
                    borderLeft: `3px solid ${item.color}`,
                  }}
                >
                  <div className="shrink-0 w-40">
                    <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                      {item.layer}
                    </p>
                    <p className="text-xs font-mono mt-1" style={{ color: "var(--muted-foreground)" }}>
                      {item.tech}
                    </p>
                  </div>
                  <div className="flex-1">
                    <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                      {item.desc}
                    </p>
                  </div>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </ScrollReveal>

      {/* LangGraph Agent Workflow */}
      <ScrollReveal>
        <div
          className="p-8"
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
          }}
        >
          <h3 className="text-lg font-medium mb-2" style={{ color: "var(--foreground)" }}>
            {t("architecture.langgraphTitle")}
          </h3>
          <p className="text-sm mb-6" style={{ color: "var(--muted-foreground)" }}>
            {t("architecture.langgraphDesc")}
          </p>

          <CodeBlock language="python" filename="services/worker/app/graph/builder.py">
{`from langgraph.graph import StateGraph, START, END

# Define the agent workflow graph
workflow = StateGraph(BidPilotState)

# Add agent nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("rfp_parser", rfp_parser_node)
workflow.add_node("knowledge_retriever", knowledge_retriever_node)
workflow.add_node("section_drafter", section_drafter_node)
workflow.add_node("quality_reviewer", quality_reviewer_node)
workflow.add_node("human_approval", human_approval_node)
workflow.add_node("persist_result", persist_result_node)

# Define edges (workflow routing)
workflow.add_edge(START, "supervisor")
workflow.add_conditional_edges("supervisor", route_next_agent)
workflow.add_edge("rfp_parser", "knowledge_retriever")
workflow.add_edge("knowledge_retriever", "section_drafter")
workflow.add_edge("section_drafter", "quality_reviewer")
workflow.add_conditional_edges("quality_reviewer", quality_gate)
workflow.add_edge("human_approval", "persist_result")
workflow.add_edge("persist_result", END)

# Compile with checkpointing
graph = workflow.compile(checkpointer=PostgresSaver())`}
          </CodeBlock>

          {/* Agent Pipeline Visualization */}
          <div className="mt-8 flex flex-wrap items-center gap-2">
            {["supervisor", "rfp_parser", "knowledge_retriever", "section_drafter", "quality_reviewer", "human_approval", "persist_result"].map(
              (agent, i, arr) => (
                <div key={agent} className="flex items-center gap-2">
                  <div
                    className="px-3 py-1.5 text-xs font-mono"
                    style={{
                      background: agent === "human_approval" ? "rgba(132, 204, 22, 0.15)" : "var(--border)",
                      border: `1px solid ${agent === "human_approval" ? "var(--border)" : "var(--border)"}`,
                      color: agent === "human_approval" ? "var(--primary)" : "var(--muted-foreground)",
                    }}
                  >
                    {agent}
                  </div>
                  {i < arr.length - 1 && (
                    <ChevronRightIcon className="size-3.5 shrink-0" style={{ color: "var(--muted-foreground)" }} />
                  )}
                </div>
              )
            )}
          </div>
        </div>
      </ScrollReveal>
    </section>
  );
}

// ---------- Section 5: Tech Stack ----------
function TechStackSection() {
  const { t } = useTranslation("docs");
  const stacks = [
    {
      category: t("techstack.frontend"),
      items: [
        { name: "React 19", desc: t("techstack.reactDesc") },
        { name: "TypeScript", desc: t("techstack.typescriptDesc") },
        { name: "Vite", desc: t("techstack.viteDesc") },
        { name: "Tailwind CSS", desc: t("techstack.tailwindDesc") },
        { name: "shadcn/ui", desc: t("techstack.shadcnDesc") },
        { name: "TanStack Query", desc: t("techstack.queryDesc") },
        { name: "react-router-dom", desc: t("techstack.routerDesc") },
      ],
    },
    {
      category: t("techstack.backend"),
      items: [
        { name: "FastAPI", desc: t("techstack.fastapiDesc") },
        { name: "Celery", desc: t("techstack.celeryDesc") },
        { name: "SQLAlchemy 2.0", desc: t("techstack.sqlalchemyDesc") },
        { name: "Alembic", desc: t("techstack.alembicDesc") },
        { name: "LangGraph", desc: t("techstack.langgraphDesc") },
        { name: "LangChain", desc: t("techstack.langchainDesc") },
      ],
    },
    {
      category: t("techstack.dataStorage"),
      items: [
        { name: "PostgreSQL 16", desc: t("techstack.postgresDesc") },
        { name: "pgvector", desc: t("techstack.pgvectorDesc") },
        { name: "Redis 7", desc: t("techstack.redisDesc") },
        { name: "MinIO", desc: t("techstack.minioDesc") },
      ],
    },
  ];

  return (
    <section id="techstack" className="py-20">
      <SectionHeading
        label={t("techstack.label")}
        title={t("techstack.title")}
        description={t("techstack.description")}
      />

      <div className="space-y-10">
        {stacks.map((stack, si) => (
          <ScrollReveal key={stack.category} delay={si * 150}>
            <div
              className="p-7"
              style={{
                background: "var(--card)",
                border: "1px solid var(--border)",
              }}
            >
              <h3
                className="text-sm font-medium tracking-widest uppercase mb-5"
                style={{ color: "var(--primary)" }}
              >
                {stack.category}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {stack.items.map((item) => (
                  <div
                    key={item.name}
                    className="flex items-start gap-3 p-3 transition-colors duration-200"
                    style={{ background: "var(--background)" }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "var(--background)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "var(--background)";
                    }}
                  >
                    <div
                      className="w-1.5 h-1.5 mt-1.5 shrink-0"
                      style={{ background: "var(--primary)" }}
                    />
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                        {item.name}
                      </p>
                      <p className="text-xs mt-0.5" style={{ color: "var(--muted-foreground)" }}>
                        {item.desc}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </ScrollReveal>
        ))}
      </div>
    </section>
  );
}

// ---------- Section 6: Deployment ----------
function DeploymentSection() {
  const { t } = useTranslation("docs");
  return (
    <section id="deployment" className="py-20">
      <SectionHeading
        label={t("deployment.label")}
        title={t("deployment.title")}
        description={t("deployment.description")}
      />

      <div className="space-y-10">
        {/* Docker Compose */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--foreground)" }}>
            {t("deployment.dockerTitle")}
          </h3>
          <p className="text-sm mb-4" style={{ color: "var(--muted-foreground)" }}>
            {t("deployment.dockerDesc")}
          </p>
          <CodeBlock language="yaml" filename="docker-compose.yml">
{`services:
  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U BidPilot"]

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"

  api:
    build: ./services/api
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }

  worker:
    build: ./services/worker
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }

  web:
    build: ./apps/web
    ports: ["3000:3000"]`}
          </CodeBlock>
        </ScrollReveal>

        {/* Health Checks */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--foreground)" }}>
            {t("deployment.healthTitle")}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { endpoint: "/health", desc: t("deployment.liveness") },
              { endpoint: "/health/db", desc: t("deployment.dbConnectivity") },
              { endpoint: "/health/redis", desc: t("deployment.redisConnectivity") },
              { endpoint: "/health/storage", desc: t("deployment.storageConnectivity") },
            ].map((item) => (
              <div
                key={item.endpoint}
                className="flex items-center gap-4 p-4"
                style={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                }}
              >
                <code
                  className="text-xs font-mono px-2 py-1 shrink-0"
                  style={{ background: "var(--muted)", color: "var(--primary)" }}
                >
                  {item.endpoint}
                </code>
                <span className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                  {item.desc}
                </span>
              </div>
            ))}
          </div>
        </ScrollReveal>

        {/* Project Structure */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--foreground)" }}>
            {t("deployment.structureTitle")}
          </h3>
          <CodeBlock language="text" filename="directory tree">
{`BidPilot/
  apps/
    web/                  # React frontend
      src/
        features/         # Feature modules
        components/       # Shared UI components
        lib/              # Utilities and API client
  services/
    api/                  # FastAPI backend
      app/
        models.py         # SQLAlchemy models
        routers/          # API route handlers
    worker/               # Celery + LangGraph
      app/
        graph/
          builder.py      # LangGraph graph definition
          state.py        # Agent state schema
          nodes/          # Agent node implementations
  infra/
    docker-compose.yml    # Production stack
    alembic/              # Database migrations
  docs/                   # Project documentation`}
          </CodeBlock>
        </ScrollReveal>
      </div>
    </section>
  );
}

// ---------- Main Component ----------
export function DocsPage() {
  const { isAuthenticated } = useAuth();
  const { t } = useTranslation("docs");
  const inPlatform = isAuthenticated;
  const [activeSection, setActiveSection] = useState("overview");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const navItems = useMemo(() => buildNavItems((key) => t(key)), [t]);

  // Track active section on scroll
  useEffect(() => {
    const handleScroll = () => {
      const sections = navItems.map((item) => {
        const el = document.getElementById(item.id);
        if (!el) return { id: item.id, top: Infinity };
        return { id: item.id, top: el.getBoundingClientRect().top };
      });

      const current = sections.reduce((closest, section) => {
        if (section.top <= 120 && section.top > closest.top) return section;
        return closest;
      }, { id: "overview", top: -Infinity });

      setActiveSection(current.id);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [navItems]);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    setMobileNavOpen(false);
  };

  return (
    <div className={inPlatform ? "" : "min-h-screen"} style={{ background: inPlatform ? "var(--background)" : "var(--background)" }}>
      {/* Top Navigation Bar */}
      <header
        className="sticky top-0 z-50 backdrop-blur-xl"
        style={{
          background: inPlatform ? "color-mix(in oklab, var(--background) 92%, transparent)" : "rgba(10, 10, 10, 0.85)",
          borderBottom: `1px solid ${inPlatform ? "var(--border)" : "var(--border)"}`,
        }}
      >
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {!inPlatform && (
              <>
                <Link
                  to="/"
                  className="flex items-center gap-2 transition-colors duration-200 hover:opacity-80"
                >
                  <ArrowLeftIcon className="size-4" style={{ color: "var(--muted-foreground)" }} />
                  <span className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                    {t("header.back")}
                  </span>
                </Link>
                <div className="w-px h-4" style={{ background: "var(--border)" }} />
              </>
            )}
            <div className="flex items-center gap-2">
              <div
                className="w-6 h-6 flex items-center justify-center"
                style={{ background: inPlatform ? "var(--primary)" : "var(--primary)" }}
              >
                <FileTextIcon className="size-3.5" style={{ color: inPlatform ? "var(--primary-foreground)" : "var(--background)" }} />
              </div>
              <span className="text-sm font-medium" style={{ color: inPlatform ? "var(--foreground)" : "var(--foreground)" }}>
                BidPilot
              </span>
              <span
                className="text-xs px-2 py-0.5 font-mono"
                style={{
                  background: inPlatform ? "var(--muted)" : "rgba(132, 204, 22, 0.1)",
                  border: `1px solid ${inPlatform ? "var(--border)" : "var(--border)"}`,
                  color: inPlatform ? "var(--primary)" : "var(--primary)",
                }}
              >
                {t("header.docsLabel")}
              </span>
            </div>
          </div>

          {/* Desktop nav indicator */}
          <div className="hidden md:flex items-center gap-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => scrollToSection(item.id)}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium transition-all duration-200",
                )}
                style={{
                  color: activeSection === item.id
                    ? (inPlatform ? "var(--primary)" : "var(--primary)")
                    : (inPlatform ? "var(--muted-foreground)" : "var(--muted-foreground)"),
                  background: activeSection === item.id
                    ? (inPlatform ? "var(--muted)" : "rgba(132, 204, 22, 0.08)")
                    : "transparent",
                }}
              >
                {item.label}
              </button>
            ))}
          </div>

          {/* Mobile menu toggle */}
          <button
            className="md:hidden p-2"
            onClick={() => setMobileNavOpen(!mobileNavOpen)}
            style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--muted-foreground)" }}
          >
            {mobileNavOpen ? <XIcon className="size-5" /> : <MenuIcon className="size-5" />}
          </button>
        </div>

        {/* Mobile dropdown nav */}
        {mobileNavOpen && (
          <div
            className="md:hidden px-6 py-4 space-y-1"
            style={{
              background: inPlatform ? "var(--background)" : "var(--background)",
              borderTop: `1px solid ${inPlatform ? "var(--border)" : "var(--border)"}`,
            }}
          >
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => scrollToSection(item.id)}
                className="flex items-center gap-3 w-full px-3 py-2.5 text-sm transition-colors duration-200"
                style={{
                  color: activeSection === item.id
                    ? (inPlatform ? "var(--primary)" : "var(--primary)")
                    : (inPlatform ? "var(--muted-foreground)" : "var(--muted-foreground)"),
                  background: activeSection === item.id
                    ? (inPlatform ? "var(--muted)" : "rgba(132, 204, 22, 0.08)")
                    : "transparent",
                }}
              >
                <item.icon className="size-4" />
                {item.label}
              </button>
            ))}
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 md:px-8">
        <div className="flex gap-12">
          {/* Sidebar (Desktop) */}
          <aside className="hidden lg:block w-56 shrink-0 sticky top-20 self-start">
            <nav className="space-y-1 pt-8">
              {navItems.map((item) => (
                <button
                  key={item.id}
                  onClick={() => scrollToSection(item.id)}
                className="flex items-center gap-3 w-full px-3 py-2 text-sm transition-all duration-200"
                style={{
                    color: activeSection === item.id
                      ? (inPlatform ? "var(--primary)" : "var(--primary)")
                      : (inPlatform ? "var(--muted-foreground)" : "var(--muted-foreground)"),
                    background: activeSection === item.id
                      ? (inPlatform ? "var(--muted)" : "rgba(132, 204, 22, 0.06)")
                      : "transparent",
                    borderLeft: activeSection === item.id
                      ? `2px solid ${inPlatform ? "var(--primary)" : "#84cc16"}`
                      : "2px solid transparent",
                  }}
                >
                  <item.icon className="size-4 shrink-0" />
                  <span className="font-medium">{item.label}</span>
                </button>
              ))}
            </nav>

            {/* Sidebar footer */}
            <div
              className="mt-10 p-4"
              style={{
                background: inPlatform ? "var(--card)" : "var(--card)",
                border: `1px solid ${inPlatform ? "var(--border)" : "var(--border)"}`,
              }}
            >
              <p className="text-xs font-medium mb-1" style={{ color: inPlatform ? "var(--foreground)" : "var(--foreground)" }}>
                {t("sidebar.needHelp")}
              </p>
              <p className="text-xs leading-relaxed" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--muted-foreground)" }}>
                {t("sidebar.helpDesc")}
              </p>
            </div>
          </aside>

          {/* Content Area */}
          <div className="flex-1 min-w-0 py-8">
            <OverviewSection />
            <div style={{ borderTop: `1px solid ${inPlatform ? "var(--border)" : "var(--border)"}` }} />
            <QuickStartSection />
            <div style={{ borderTop: `1px solid ${inPlatform ? "var(--border)" : "var(--border)"}` }} />
            <CoreFeaturesSection />
            <div style={{ borderTop: `1px solid ${inPlatform ? "var(--border)" : "var(--border)"}` }} />
            <ArchitectureSection />
            <div style={{ borderTop: `1px solid ${inPlatform ? "var(--border)" : "var(--border)"}` }} />
            <TechStackSection />
            <div style={{ borderTop: `1px solid ${inPlatform ? "var(--border)" : "var(--border)"}` }} />
            <DeploymentSection />

            {/* Footer */}
            <div
              className="py-16 mt-10 text-center"
              style={{ borderTop: `1px solid ${inPlatform ? "var(--border)" : "var(--border)"}` }}
            >
              <ScrollReveal>
                <p className="text-sm mb-2" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--muted-foreground)" }}>
                  {t("footer.title")}
                </p>
                <p className="text-xs" style={{ color: inPlatform ? "var(--muted-foreground)" : "var(--muted-foreground)" }}>
                  {t("footer.subtitle")}
                </p>
              </ScrollReveal>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

