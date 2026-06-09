import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SearchIcon, BookOpenIcon, FileTextIcon, SettingsIcon, HelpCircleIcon, UsersIcon, MessageSquareIcon, CheckCircleIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface DocArticle {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  content: string;
}

interface DocCategory {
  id: string;
  label: string;
  icon: React.ReactNode;
  articles: DocArticle[];
}

const DOC_CATEGORIES: DocCategory[] = [
  {
    id: "getting-started",
    label: "Getting Started",
    icon: <BookOpenIcon className="size-4" />,
    articles: [
      { id: "what-is-bidpilot", title: "What is BidPilot?", description: "Overview of the platform and its capabilities", icon: <BookOpenIcon className="size-4" />, content: "BidPilot is an AI-powered bid response platform that helps teams create professional, compliant, and compelling proposals. Upload an RFP, and our AI agents analyze requirements, retrieve relevant knowledge, draft sections, and manage reviews." },
      { id: "quick-start", title: "Quick Start Guide", description: "Create your first project in 5 minutes", icon: <FileTextIcon className="size-4" />, content: "1. Create a Project - Click 'New Project' and name it. 2. Upload RFP - Drag and drop your RFP document. 3. Review Content - Our AI parses the document and extracts requirements. 4. Start Drafting - AI generates sections automatically." },
      { id: "key-concepts", title: "Key Concepts", description: "Projects, bundles, sections, and versions", icon: <BookOpenIcon className="size-4" />, content: "Projects organize your bid work. Each project contains bundles (your uploaded documents), deliverables (the content you produce), sections (individual parts of a deliverable), and versions (revisions tracked over time)." },
    ],
  },
  {
    id: "projects",
    label: "Projects",
    icon: <FileTextIcon className="size-4" />,
    articles: [
      { id: "creating-projects", title: "Creating and Managing Projects", description: "Organize your bid work", icon: <FileTextIcon className="size-4" />, content: "Projects are the top-level container for all your work. Each project represents a bid opportunity. You can search, filter, and sort projects from the dashboard." },
      { id: "uploading-rfp", title: "Uploading RFP Documents", description: "Ingest and parse bid documents", icon: <FileTextIcon className="size-4" />, content: "Upload RFP documents in PDF, DOCX, or Markdown format. BidPilot automatically parses the document, extracts key requirements, and makes them searchable." },
      { id: "managing-content", title: "Managing Content", description: "Bundle, organize, and version content", icon: <FileTextIcon className="size-4" />, content: "Content is organized into bundles (source documents) and deliverables (your output). Each section has version history so you can track changes over time." },
    ],
  },
  {
    id: "drafting",
    label: "Drafting",
    icon: <MessageSquareIcon className="size-4" />,
    articles: [
      { id: "ai-drafting", title: "AI-Powered Drafting", description: "How AI generates bid sections", icon: <MessageSquareIcon className="size-4" />, content: "Our AI agent workflow uses multiple specialized agents: the RFP Parser extracts requirements, the Knowledge Retriever finds relevant evidence, and the Section Drafter generates content based on both." },
      { id: "evidence-retrieval", title: "Evidence Retrieval", description: "How context is gathered", icon: <SearchIcon className="size-4" />, content: "The Knowledge Retriever uses semantic search (pgvector) to find the most relevant content chunks from your uploaded documents. It considers cosine similarity between your section and available content." },
      { id: "quality-review", title: "Quality Review", description: "Automatic review of generated content", icon: <CheckCircleIcon className="size-4" />, content: "After drafting, the Quality Reviewer agent evaluates the content for completeness, compliance with RFP requirements, and proper evidence usage. Sections below quality threshold are automatically revised." },
    ],
  },
  {
    id: "review",
    label: "Review & Approval",
    icon: <MessageSquareIcon className="size-4" />,
    articles: [
      { id: "review-workflow", title: "Review Workflow", description: "Collaborative review process", icon: <MessageSquareIcon className="size-4" />, content: "Team members can review drafts, add threaded comments, and request changes. The review workflow supports approve/reject decisions with feedback." },
      { id: "approval-gate", title: "Human Approval", description: "Validation before finalization", icon: <CheckCircleIcon className="size-4" />, content: "For critical sections, the AI pauses and waits for human approval before finalizing. This ensures quality control while letting AI handle the heavy lifting." },
    ],
  },
  {
    id: "settings",
    label: "Settings",
    icon: <SettingsIcon className="size-4" />,
    articles: [
      { id: "account-settings", title: "Account Settings", description: "Manage your profile and preferences", icon: <SettingsIcon className="size-4" />, content: "Update your profile, change password, and manage notification preferences from the Account settings page." },
      { id: "ai-providers", title: "AI Provider Configuration", description: "Connect your own LLM provider", icon: <SettingsIcon className="size-4" />, content: "Bring your own API keys for OpenAI or Anthropic models. Configure custom endpoints, models, and manage multiple provider profiles." },
    ],
  },
  {
    id: "faq",
    label: "FAQ",
    icon: <HelpCircleIcon className="size-4" />,
    articles: [
      { id: "faq-security", title: "Is my data secure?", description: "Security and compliance", icon: <HelpCircleIcon className="size-4" />, content: "Yes. Data is encrypted at rest and in transit. We use industry-standard encryption and follow security best practices. Your documents are stored securely and never shared." },
      { id: "faq-models", title: "What AI models are used?", description: "Supported AI providers", icon: <HelpCircleIcon className="size-4" />, content: "BidPilot supports OpenAI (GPT-4o-mini) and Anthropic (Claude) models. You can also configure custom providers via the Settings page." },
      { id: "faq-export", title: "How do I export my work?", description: "Export formats and process", icon: <FileTextIcon className="size-4" />, content: "Sections can be exported as Markdown or DOCX. Full deliverables can be compiled into a single document with all sections, headers, and formatting preserved." },
    ],
  },
];

export function DocsPage() {
  const { t } = useTranslation();
  const [activeCategory, setActiveCategory] = useState(DOC_CATEGORIES[0].id);
  const [activeArticle, setActiveArticle] = useState(DOC_CATEGORIES[0].articles[0].id);
  const [searchQuery, setSearchQuery] = useState("");

  const currentCategory = DOC_CATEGORIES.find((c) => c.id === activeCategory) ?? DOC_CATEGORIES[0];
  const currentArticle = currentCategory.articles.find((a) => a.id === activeArticle) ?? currentCategory.articles[0];

  const filteredCategories = DOC_CATEGORIES.map((cat) => ({
    ...cat,
    articles: cat.articles.filter(
      (a) =>
        a.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.description.toLowerCase().includes(searchQuery.toLowerCase())
    ),
  })).filter((cat) => cat.articles.length > 0);

  return (
    <div className="flex h-full overflow-hidden">
      <aside className="w-64 shrink-0 border-r bg-muted/20">
        <div className="p-4 border-b">
          <div className="relative">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Search docs..."
              className="pl-9 h-9 text-sm"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
        <ScrollArea className="h-[calc(100%-4rem)]">
          <nav className="p-3 space-y-1">
            {filteredCategories.map((cat) => (
              <div key={cat.id}>
                <button
                  onClick={() => setActiveCategory(cat.id)}
                  className={cn(
                    "flex items-center gap-2 w-full rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    activeCategory === cat.id
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                  )}
                >
                  {cat.icon}
                  {cat.label}
                </button>
                {activeCategory === cat.id && (
                  <div className="ml-2 mt-1 space-y-0.5 pl-4 border-l">
                    {cat.articles.map((article) => (
                      <button
                        key={article.id}
                        onClick={() => { setActiveArticle(article.id); setActiveCategory(cat.id); }}
                        className={cn(
                          "flex items-center gap-2 w-full rounded-md px-3 py-1.5 text-xs transition-colors",
                          activeArticle === article.id
                            ? "text-foreground font-medium"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {article.title}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </nav>
        </ScrollArea>
      </aside>
      <main className="flex-1 overflow-y-auto p-8">
        <div className="max-w-3xl mx-auto">
          <div className="mb-8">
            <h1 className="text-2xl font-bold tracking-tight mb-2">{currentArticle.title}</h1>
            <p className="text-muted-foreground">{currentArticle.description}</p>
          </div>
          <div className="prose prose-neutral dark:prose-invert max-w-none">
            <Card>
              <CardContent className="p-6 leading-relaxed text-sm text-muted-foreground">
                {currentArticle.content}
              </CardContent>
            </Card>
          </div>
          <div className="mt-8 flex items-center gap-4 p-4 rounded-lg border bg-muted/30">
            <HelpCircleIcon className="size-5 text-muted-foreground shrink-0" />
            <p className="text-sm text-muted-foreground">
              Need more help? Contact support or check our integration guides.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
