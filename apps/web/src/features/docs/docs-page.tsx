import { useEffect, useRef, useState, useCallback } from "react";
import { Link } from "react-router-dom";
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
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (!ref.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTimeout(() => setIsVisible(true), delay);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.08 }
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [delay]);

  const getTransform = () => {
    switch (direction) {
      case "up":
        return "translateY(40px)";
      case "down":
        return "translateY(-40px)";
      case "left":
        return "translateX(40px)";
      case "right":
        return "translateX(-40px)";
      default:
        return "translateY(40px)";
    }
  };

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? "none" : getTransform(),
        filter: isVisible ? "blur(0px)" : "blur(4px)",
        transition: `all 0.8s cubic-bezier(0.32, 0.72, 0, 1) ${delay}ms`,
      }}
    >
      {children}
    </div>
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
    <div
      className="relative group my-6 overflow-hidden"
      style={{
        background: "var(--landing-surface-1)",
        border: "1px solid var(--landing-hairline)",
      }}
    >
      {/* 标题栏 */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{
          borderBottom: "1px solid var(--landing-hairline)",
          background: "var(--landing-canvas)",
        }}
      >
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--landing-surface-3)" }} />
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--landing-surface-3)" }} />
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--landing-surface-3)" }} />
          </div>
          {filename && (
            <span className="text-xs font-mono" style={{ color: "var(--landing-text-tertiary)" }}>
              {filename}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono tracking-wider uppercase" style={{ color: "var(--landing-text-tertiary)" }}>
            {language}
          </span>
          <button
            onClick={handleCopy}
            className="p-1.5 transition-all duration-200 hover:scale-110"
            style={{
              color: copied ? "var(--landing-accent)" : "var(--landing-text-tertiary)",
            }}
            title="Copy code"
          >
            {copied ? <CheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}
          </button>
        </div>
      </div>

      {/* 代码内容 */}
      <pre className="p-5 overflow-x-auto text-sm leading-relaxed font-mono" style={{ color: "var(--landing-text-secondary)" }}>
        <code>{children.trim()}</code>
      </pre>
    </div>
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
      <div
        className="group p-7 transition-all duration-300 hover:-translate-y-1"
        style={{
          background: "var(--landing-surface-1)",
          border: "1px solid var(--landing-hairline)",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = "var(--landing-border-inner)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "var(--landing-hairline)";
        }}
      >
        <div
          className="w-10 h-10 flex items-center justify-center mb-5"
          style={{
            background: "rgba(132, 204, 22, 0.1)",
            border: "1px solid var(--landing-border-inner)",
          }}
        >
          <Icon className="w-5 h-5" style={{ color: "var(--landing-accent)" }} />
        </div>
        <h3 className="text-lg font-medium mb-2" style={{ color: "var(--landing-text-primary)" }}>
          {title}
        </h3>
        <p className="text-sm leading-relaxed" style={{ color: "var(--landing-text-secondary)" }}>
          {description}
        </p>
      </div>
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
        style={{ color: "var(--landing-accent)" }}
      >
        {label}
      </span>
      <h2
        className="text-3xl md:text-4xl font-medium leading-tight tracking-tight mb-4"
        style={{ color: "var(--landing-text-primary)" }}
      >
        {title}
      </h2>
      <p className="text-lg max-w-2xl mb-14" style={{ color: "var(--landing-text-secondary)" }}>
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

const NAV_ITEMS: NavItem[] = [
  { id: "overview", label: "Overview", icon: BookOpenIcon },
  { id: "quickstart", label: "Quick Start", icon: RocketIcon },
  { id: "features", label: "Core Features", icon: LayersIcon },
  { id: "architecture", label: "Architecture", icon: CpuIcon },
  { id: "techstack", label: "Tech Stack", icon: CodeIcon },
  { id: "deployment", label: "Deployment", icon: ServerIcon },
];

// ---------- Section 1: Overview ----------
function OverviewSection() {
  return (
    <section id="overview" className="pt-8 pb-20">
      <ScrollReveal>
        <div className="mb-12">
          <span
            className="text-xs font-medium tracking-widest uppercase mb-4 block"
            style={{ color: "var(--landing-accent)" }}
          >
            / Enterprise AI Document System
          </span>
          <h1
            className="text-5xl md:text-6xl font-medium leading-[0.9] tracking-tight mb-6"
            style={{ color: "var(--landing-text-primary)" }}
          >
            DocPilot
            <br />
            <span style={{ color: "var(--landing-accent)" }}>Documentation</span>
          </h1>
          <p className="text-xl leading-relaxed max-w-2xl" style={{ color: "var(--landing-text-secondary)" }}>
            DocPilot is an enterprise-grade AI document execution system designed for complex
            document workflows. From RFP ingestion to final delivery, DocPilot orchestrates
            multi-agent workflows to automate the entire bid response process.
          </p>
        </div>
      </ScrollReveal>

      {/* 概述卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-16">
        {[
          {
            icon: BrainCircuitIcon,
            title: "AI-Native",
            desc: "Built on LangGraph multi-agent architecture with specialized agents for each workflow stage.",
          },
          {
            icon: GitBranchIcon,
            title: "Stateful Workflows",
            desc: "Checkpoint-backed execution with human-in-the-loop approval gates and full audit trails.",
          },
          {
            icon: ShieldCheckIcon,
            title: "Enterprise Ready",
            desc: "RBAC, encrypted storage, provider-agnostic LLM integration, and production-grade infrastructure.",
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
            background: "var(--landing-surface-1)",
            border: "1px solid var(--landing-hairline)",
          }}
        >
          <h3 className="text-lg font-medium mb-6" style={{ color: "var(--landing-text-primary)" }}>
            Workflow Pipeline
          </h3>
          <div className="flex flex-wrap items-center gap-3">
            {[
              "Project Setup",
              "RFP Ingestion",
              "Requirement Extraction",
              "Knowledge Retrieval",
              "Section Drafting",
              "Quality Review",
              "Human Approval",
              "Export & Delivery",
            ].map((step, i, arr) => (
              <div key={step} className="flex items-center gap-3">
                <div
                  className="px-4 py-2 text-xs font-medium tracking-wide"
                  style={{
                    background: "rgba(132, 204, 22, 0.08)",
                    border: "1px solid var(--landing-border-inner)",
                    color: "var(--landing-accent)",
                  }}
                >
                  {step}
                </div>
                {i < arr.length - 1 && (
                  <ChevronRightIcon className="size-4 shrink-0" style={{ color: "var(--landing-surface-3)" }} />
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
  return (
    <section id="quickstart" className="py-20">
      <SectionHeading
        label="Quick Start"
        title="Get Running in Minutes"
        description="DocPilot is fully containerized. A single command brings up the entire stack: API, Worker, PostgreSQL, Redis, and MinIO."
      />

      <div className="space-y-12">
        {/* Prerequisites */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--landing-text-primary)" }}>
            Prerequisites
          </h3>
          <ul className="space-y-3">
            {[
              "Docker Engine 24+ and Docker Compose v2",
              "Node.js 20+ (for frontend development)",
              "Python 3.11+ (for backend development)",
              "An OpenAI or Anthropic API key",
            ].map((item) => (
              <li key={item} className="flex items-start gap-3">
                <CheckCircleIcon className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "var(--landing-accent)" }} />
                <span className="text-sm" style={{ color: "var(--landing-text-secondary)" }}>
                  {item}
                </span>
              </li>
            ))}
          </ul>
        </ScrollReveal>

        {/* Installation */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--landing-text-primary)" }}>
            Installation
          </h3>
          <p className="text-sm mb-4" style={{ color: "var(--landing-text-secondary)" }}>
            Clone the repository and start all services with Docker Compose:
          </p>
          <CodeBlock language="bash" filename="terminal">
{`git clone https://github.com/your-org/docpilot.git
cd docpilot

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
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--landing-text-primary)" }}>
            Environment Configuration
          </h3>
          <p className="text-sm mb-4" style={{ color: "var(--landing-text-secondary)" }}>
            The <code className="px-1.5 py-0.5 text-xs font-mono" style={{ background: "var(--landing-surface-2)", color: "var(--landing-accent)" }}>.env</code> file
            controls all service connections and API keys. Key variables:
          </p>
          <CodeBlock language="env" filename=".env">
{`# Database
DATABASE_URL=postgresql+asyncpg://docpilot:secret@postgres:5432/docpilot

# Redis (task queue + cache)
REDIS_URL=redis://redis:6379/0

# MinIO (document storage)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# LLM Provider
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...

# Vector Store (pgvector)
EMBEDDING_MODEL=text-embedding-3-small`}
          </CodeBlock>
        </ScrollReveal>

        {/* First Project */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--landing-text-primary)" }}>
            Create Your First Project
          </h3>
          <div className="space-y-4">
            {[
              { num: "01", title: "Sign up / Log in", desc: "Navigate to the web UI and create an account." },
              { num: "02", title: "New Project", desc: "Click 'New Project' on the dashboard and name your bid." },
              { num: "03", title: "Upload RFP", desc: "Drag and drop your RFP document (PDF, DOCX, or Markdown)." },
              { num: "04", title: "Review & Export", desc: "AI agents process the document. Review drafts, approve, and export." },
            ].map((step, i) => (
              <ScrollReveal key={step.num} delay={i * 100} direction="left">
                <div className="flex gap-5 items-start">
                  <div
                    className="shrink-0 w-10 h-10 flex items-center justify-center text-sm font-mono font-medium"
                    style={{
                      background: "var(--landing-surface-1)",
                      border: "1px solid var(--landing-border-inner)",
                      color: "var(--landing-accent)",
                    }}
                  >
                    {step.num}
                  </div>
                  <div className="pt-1">
                    <h4 className="text-sm font-medium mb-1" style={{ color: "var(--landing-text-primary)" }}>
                      {step.title}
                    </h4>
                    <p className="text-sm" style={{ color: "var(--landing-text-secondary)" }}>
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
  const features = [
    {
      icon: FolderIcon,
      title: "Project Management",
      desc: "Create and manage bid projects. Each project is a self-contained workspace with its own RFP documents, knowledge base, deliverables, and review history. Search, filter, and organize across your portfolio.",
    },
    {
      icon: FileTextIcon,
      title: "Document Ingestion",
      desc: "Upload RFP documents in PDF, DOCX, or Markdown format. DocPilot automatically parses structure, extracts tables, and chunks content into searchable segments stored in MinIO.",
    },
    {
      icon: SearchIcon,
      title: "Requirement Extraction",
      desc: "AI agents analyze the RFP and extract structured requirements: mandatory criteria, evaluation factors, compliance requirements, and submission guidelines. All requirements are linked back to source pages.",
    },
    {
      icon: BrainCircuitIcon,
      title: "Knowledge Retrieval",
      desc: "The Knowledge Retriever agent uses pgvector semantic search to find the most relevant content chunks from your uploaded documents. Cosine similarity scoring ensures high-quality evidence for every section.",
    },
    {
      icon: PenToolIcon,
      title: "Section Drafting",
      desc: "The Section Drafter agent generates compliant, compelling content by combining RFP requirements with retrieved evidence. Each draft includes citations and follows your organization's tone and style guidelines.",
    },
    {
      icon: ShieldCheckIcon,
      title: "Quality Review",
      desc: "The Quality Reviewer agent evaluates drafts for completeness, compliance, evidence usage, and clarity. Sections below the quality threshold are automatically flagged and revised before human review.",
    },
    {
      icon: CheckCircleIcon,
      title: "Human Approval",
      desc: "Critical sections pause at a human-in-the-loop gate. Reviewers can approve, request changes, or add inline comments. The workflow resumes only after explicit approval, ensuring quality control.",
    },
    {
      icon: DownloadIcon,
      title: "Export & Delivery",
      desc: "Export individual sections as Markdown or DOCX. Compile full deliverables with headers, formatting, and a table of contents. Version history is preserved for audit and compliance.",
    },
  ];

  return (
    <section id="features" className="py-20">
      <SectionHeading
        label="Core Features"
        title="End-to-End Document Automation"
        description="DocPilot covers every stage of the document lifecycle, from initial ingestion to final export."
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
  return (
    <section id="architecture" className="py-20">
      <SectionHeading
        label="Architecture"
        title="Layered System Design"
        description="DocPilot follows a clean separation of concerns: Web, API, Worker, and Data layers."
      />

      {/* Architecture Diagram */}
      <ScrollReveal>
        <div
          className="p-8 mb-10"
          style={{
            background: "var(--landing-surface-1)",
            border: "1px solid var(--landing-hairline)",
          }}
        >
          <h3 className="text-lg font-medium mb-6" style={{ color: "var(--landing-text-primary)" }}>
            System Layers
          </h3>
          <div className="space-y-4">
            {[
              {
                layer: "Web Application",
                tech: "React 19 + TypeScript + Vite + Tailwind CSS",
                color: "var(--landing-accent)",
                desc: "SPA frontend with shadcn/ui components, react-router-dom routing, and TanStack Query for server state.",
              },
              {
                layer: "API Application",
                tech: "FastAPI + SQLAlchemy + Alembic",
                color: "var(--landing-accent-light)",
                desc: "REST API layer handling auth, project CRUD, document management, and WebSocket streaming for agent progress.",
              },
              {
                layer: "Worker Application",
                tech: "Celery + LangGraph",
                color: "var(--landing-accent-hover)",
                desc: "Async task execution with LangGraph-powered multi-agent workflows. Handles all AI processing in isolated workers.",
              },
              {
                layer: "Data Services",
                tech: "PostgreSQL + pgvector + Redis + MinIO",
                color: "var(--landing-accent-hover)",
                desc: "Persistent storage, vector search, task queuing, caching, and object storage for documents.",
              },
            ].map((item, i) => (
              <ScrollReveal key={item.layer} delay={i * 120} direction="left">
                <div
                  className="flex flex-col md:flex-row md:items-center gap-4 p-5 transition-all duration-300"
                  style={{
                    background: "var(--landing-canvas)",
                    borderLeft: `3px solid ${item.color}`,
                  }}
                >
                  <div className="shrink-0 w-40">
                    <p className="text-sm font-medium" style={{ color: "var(--landing-text-primary)" }}>
                      {item.layer}
                    </p>
                    <p className="text-xs font-mono mt-1" style={{ color: "var(--landing-text-tertiary)" }}>
                      {item.tech}
                    </p>
                  </div>
                  <div className="flex-1">
                    <p className="text-sm" style={{ color: "var(--landing-text-secondary)" }}>
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
            background: "var(--landing-surface-1)",
            border: "1px solid var(--landing-hairline)",
          }}
        >
          <h3 className="text-lg font-medium mb-2" style={{ color: "var(--landing-text-primary)" }}>
            LangGraph Multi-Agent Workflow
          </h3>
          <p className="text-sm mb-6" style={{ color: "var(--landing-text-secondary)" }}>
            The Worker layer uses LangGraph to orchestrate stateful, multi-agent workflows. Each agent is a
            specialized node in a directed graph with checkpoint-backed execution.
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
                      background: agent === "human_approval" ? "rgba(132, 204, 22, 0.15)" : "var(--landing-hairline)",
                      border: `1px solid ${agent === "human_approval" ? "var(--landing-border-inner)" : "var(--landing-hairline)"}`,
                      color: agent === "human_approval" ? "var(--landing-accent)" : "var(--landing-text-secondary)",
                    }}
                  >
                    {agent}
                  </div>
                  {i < arr.length - 1 && (
                    <ChevronRightIcon className="size-3.5 shrink-0" style={{ color: "var(--landing-surface-3)" }} />
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
  const stacks = [
    {
      category: "Frontend",
      items: [
        { name: "React 19", desc: "UI library with concurrent features" },
        { name: "TypeScript", desc: "End-to-end type safety" },
        { name: "Vite", desc: "Fast dev server and build tool" },
        { name: "Tailwind CSS", desc: "Utility-first styling" },
        { name: "shadcn/ui", desc: "Accessible component primitives" },
        { name: "TanStack Query", desc: "Server state management" },
        { name: "react-router-dom", desc: "Client-side routing" },
      ],
    },
    {
      category: "Backend",
      items: [
        { name: "FastAPI", desc: "Async Python web framework" },
        { name: "Celery", desc: "Distributed task queue" },
        { name: "SQLAlchemy 2.0", desc: "Async ORM with type hints" },
        { name: "Alembic", desc: "Database migration management" },
        { name: "LangGraph", desc: "Multi-agent workflow orchestration" },
        { name: "LangChain", desc: "LLM abstraction layer" },
      ],
    },
    {
      category: "Data & Storage",
      items: [
        { name: "PostgreSQL 16", desc: "Primary relational database" },
        { name: "pgvector", desc: "Vector similarity search" },
        { name: "Redis 7", desc: "Task queue broker + caching" },
        { name: "MinIO", desc: "S3-compatible object storage" },
      ],
    },
  ];

  return (
    <section id="techstack" className="py-20">
      <SectionHeading
        label="Tech Stack"
        title="Built with Modern Tools"
        description="Every technology choice is deliberate: async-first, type-safe, and battle-tested in production."
      />

      <div className="space-y-10">
        {stacks.map((stack, si) => (
          <ScrollReveal key={stack.category} delay={si * 150}>
            <div
              className="p-7"
              style={{
                background: "var(--landing-surface-1)",
                border: "1px solid var(--landing-hairline)",
              }}
            >
              <h3
                className="text-sm font-medium tracking-widest uppercase mb-5"
                style={{ color: "var(--landing-accent)" }}
              >
                {stack.category}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {stack.items.map((item) => (
                  <div
                    key={item.name}
                    className="flex items-start gap-3 p-3 transition-colors duration-200"
                    style={{ background: "var(--landing-canvas)" }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "var(--landing-canvas)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "var(--landing-canvas)";
                    }}
                  >
                    <div
                      className="w-1.5 h-1.5 mt-1.5 shrink-0"
                      style={{ background: "var(--landing-accent)" }}
                    />
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--landing-text-primary)" }}>
                        {item.name}
                      </p>
                      <p className="text-xs mt-0.5" style={{ color: "var(--landing-text-tertiary)" }}>
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
  return (
    <section id="deployment" className="py-20">
      <SectionHeading
        label="Deployment"
        title="Production Deployment"
        description="DocPilot is designed for containerized deployment. The Docker Compose stack includes all services with health checks."
      />

      <div className="space-y-10">
        {/* Docker Compose */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--landing-text-primary)" }}>
            Docker Compose Stack
          </h3>
          <p className="text-sm mb-4" style={{ color: "var(--landing-text-secondary)" }}>
            The production stack includes 6 services, all orchestrated via Docker Compose:
          </p>
          <CodeBlock language="yaml" filename="docker-compose.yml">
{`services:
  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U docpilot"]

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
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--landing-text-primary)" }}>
            Health & Monitoring
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { endpoint: "/health", desc: "Basic liveness check" },
              { endpoint: "/health/db", desc: "Database connectivity" },
              { endpoint: "/health/redis", desc: "Redis connectivity" },
              { endpoint: "/health/storage", desc: "MinIO connectivity" },
            ].map((item) => (
              <div
                key={item.endpoint}
                className="flex items-center gap-4 p-4"
                style={{
                  background: "var(--landing-surface-1)",
                  border: "1px solid var(--landing-hairline)",
                }}
              >
                <code
                  className="text-xs font-mono px-2 py-1 shrink-0"
                  style={{ background: "var(--landing-surface-2)", color: "var(--landing-accent)" }}
                >
                  {item.endpoint}
                </code>
                <span className="text-sm" style={{ color: "var(--landing-text-secondary)" }}>
                  {item.desc}
                </span>
              </div>
            ))}
          </div>
        </ScrollReveal>

        {/* Project Structure */}
        <ScrollReveal>
          <h3 className="text-xl font-medium mb-4" style={{ color: "var(--landing-text-primary)" }}>
            Project Structure
          </h3>
          <CodeBlock language="text" filename="directory tree">
{`docpilot/
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
  const [activeSection, setActiveSection] = useState("overview");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Track active section on scroll
  useEffect(() => {
    const handleScroll = () => {
      const sections = NAV_ITEMS.map((item) => {
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
  }, []);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    setMobileNavOpen(false);
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--landing-canvas)" }}>
      {/* Top Navigation Bar */}
      <header
        className="sticky top-0 z-50 backdrop-blur-xl"
        style={{
          background: "rgba(10, 10, 10, 0.85)",
          borderBottom: "1px solid var(--landing-hairline)",
        }}
      >
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="flex items-center gap-2 transition-colors duration-200 hover:opacity-80"
            >
              <ArrowLeftIcon className="size-4" style={{ color: "var(--landing-text-tertiary)" }} />
              <span className="text-sm" style={{ color: "var(--landing-text-tertiary)" }}>
                Back
              </span>
            </Link>
            <div className="w-px h-4" style={{ background: "var(--landing-hairline)" }} />
            <div className="flex items-center gap-2">
              <div
                className="w-6 h-6 flex items-center justify-center"
                style={{ background: "var(--landing-accent)" }}
              >
                <FileTextIcon className="size-3.5" style={{ color: "var(--landing-canvas)" }} />
              </div>
              <span className="text-sm font-medium" style={{ color: "var(--landing-text-primary)" }}>
                DocPilot
              </span>
              <span
                className="text-xs px-2 py-0.5 font-mono"
                style={{
                  background: "rgba(132, 204, 22, 0.1)",
                  border: "1px solid var(--landing-border-inner)",
                  color: "var(--landing-accent)",
                }}
              >
                Docs
              </span>
            </div>
          </div>

          {/* Desktop nav indicator */}
          <div className="hidden md:flex items-center gap-1">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                onClick={() => scrollToSection(item.id)}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium transition-all duration-200",
                )}
                style={{
                  color: activeSection === item.id ? "var(--landing-accent)" : "var(--landing-text-tertiary)",
                  background: activeSection === item.id ? "rgba(132, 204, 22, 0.08)" : "transparent",
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
            style={{ color: "var(--landing-text-secondary)" }}
          >
            {mobileNavOpen ? <XIcon className="size-5" /> : <MenuIcon className="size-5" />}
          </button>
        </div>

        {/* Mobile dropdown nav */}
        {mobileNavOpen && (
          <div
            className="md:hidden px-6 py-4 space-y-1"
            style={{
              background: "var(--landing-canvas)",
              borderTop: "1px solid var(--landing-hairline)",
            }}
          >
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                onClick={() => scrollToSection(item.id)}
                className="flex items-center gap-3 w-full px-3 py-2.5 text-sm transition-colors duration-200"
                style={{
                  color: activeSection === item.id ? "var(--landing-accent)" : "var(--landing-text-secondary)",
                  background: activeSection === item.id ? "rgba(132, 204, 22, 0.08)" : "transparent",
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
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.id}
                  onClick={() => scrollToSection(item.id)}
                  className="flex items-center gap-3 w-full px-3 py-2 text-sm transition-all duration-200"
                  style={{
                    color: activeSection === item.id ? "var(--landing-accent)" : "var(--landing-text-tertiary)",
                    background: activeSection === item.id ? "rgba(132, 204, 22, 0.06)" : "transparent",
                    borderLeft: activeSection === item.id ? "2px solid #84cc16" : "2px solid transparent",
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
                background: "var(--landing-surface-1)",
                border: "1px solid var(--landing-hairline)",
              }}
            >
              <p className="text-xs font-medium mb-1" style={{ color: "var(--landing-text-primary)" }}>
                Need help?
              </p>
              <p className="text-xs leading-relaxed" style={{ color: "var(--landing-text-tertiary)" }}>
                Open an issue on GitHub or reach out to the team.
              </p>
            </div>
          </aside>

          {/* Content Area */}
          <div className="flex-1 min-w-0 py-8">
            <OverviewSection />
            <div style={{ borderTop: "1px solid var(--landing-hairline)" }} />
            <QuickStartSection />
            <div style={{ borderTop: "1px solid var(--landing-hairline)" }} />
            <CoreFeaturesSection />
            <div style={{ borderTop: "1px solid var(--landing-hairline)" }} />
            <ArchitectureSection />
            <div style={{ borderTop: "1px solid var(--landing-hairline)" }} />
            <TechStackSection />
            <div style={{ borderTop: "1px solid var(--landing-hairline)" }} />
            <DeploymentSection />

            {/* Footer */}
            <div
              className="py-16 mt-10 text-center"
              style={{ borderTop: "1px solid var(--landing-hairline)" }}
            >
              <ScrollReveal>
                <p className="text-sm mb-2" style={{ color: "var(--landing-text-tertiary)" }}>
                  DocPilot Documentation
                </p>
                <p className="text-xs" style={{ color: "var(--landing-surface-3)" }}>
                  Built for teams that ship winning proposals.
                </p>
              </ScrollReveal>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
