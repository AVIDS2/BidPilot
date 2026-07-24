import {
  BookOpenCheckIcon,
  FileSearchIcon,
  FilePenLineIcon,
  FolderOpenIcon,
  ListChecksIcon,
  NavigationIcon,
  PackageIcon,
  RefreshCcwIcon,
  SearchIcon,
  TerminalIcon,
  Trash2Icon,
  UploadCloudIcon,
  WrenchIcon,
  type LucideIcon,
} from "lucide-react";
import type { AssistantExecutionItem } from "@/lib/ai-assistant-store";

type Translate = (key: string, options?: Record<string, unknown>) => string;

const TOOL_FALLBACK_LABELS: Record<string, string> = {
  search_projects: "搜索项目",
  create_demo_workspace: "创建演示工作区",
  create_project: "创建项目",
  get_project_summary: "读取项目概览",
  list_project_bundles: "查看资料包",
  list_sections: "查看章节",
  list_pending_reviews: "查看待审核项",
  submit_review_decision: "提交章节审核决定",
  list_requirements: "查看需求",
  list_claim_review_queue: "查看待核验主张",
  get_readiness_summary: "查看投标准备度",
  list_readiness_gaps: "查看就绪缺口",
  open_requirement_source: "定位需求来源",
  list_evidence: "查看证据",
  list_deliverables: "查看交付物",
  list_documents: "查看文档",
  attach_uploaded_documents: "将附件加入资料包",
  get_section_versions: "查看章节版本",
  create_deliverable: "创建交付物",
  start_draft_section: "启动章节起草",
  write_section: "写入章节内容",
  start_redraft_section: "重新起草章节",
  propose_memory_graph: "生成实体关系提案",
  get_runtime_status: "读取执行状态",
  retry_run: "重试任务",
  export_deliverable: "导出交付物",
  generate_readiness_pack: "生成投标准备度包",
  semantic_search: "检索资料",
  web_search: "联网搜索",
  fetch_url_to_project: "下载网页到项目",
  search_bid_wiki: "查询 Bid Wiki",
  list_knowledge_portfolio: "查看知识资产概览",
  propose_memory: "保存个人偏好",
  forget_memory: "遗忘记忆",
  search_knowledge: "检索知识库",
  open_page: "打开页面",
  upload_document: "上传文档",
  delete_project: "删除项目",
};

const TOOL_ICONS: Record<string, LucideIcon> = {
  search_projects: SearchIcon,
  semantic_search: SearchIcon,
  web_search: SearchIcon,
  fetch_url_to_project: UploadCloudIcon,
  search_knowledge: SearchIcon,
  get_project_summary: FolderOpenIcon,
  list_project_bundles: PackageIcon,
  list_sections: ListChecksIcon,
  list_pending_reviews: ListChecksIcon,
  submit_review_decision: ListChecksIcon,
  list_requirements: ListChecksIcon,
  list_claim_review_queue: ListChecksIcon,
  get_readiness_summary: ListChecksIcon,
  list_readiness_gaps: FileSearchIcon,
  open_requirement_source: SearchIcon,
  list_evidence: SearchIcon,
  list_deliverables: FilePenLineIcon,
  list_documents: PackageIcon,
  attach_uploaded_documents: UploadCloudIcon,
  get_section_versions: FilePenLineIcon,
  create_project: FolderOpenIcon,
  create_demo_workspace: FolderOpenIcon,
  create_deliverable: FilePenLineIcon,
  start_draft_section: FilePenLineIcon,
  write_section: FilePenLineIcon,
  start_redraft_section: FilePenLineIcon,
  propose_memory_graph: FileSearchIcon,
  get_runtime_status: TerminalIcon,
  retry_run: RefreshCcwIcon,
  export_deliverable: FilePenLineIcon,
  generate_readiness_pack: FilePenLineIcon,
  open_page: NavigationIcon,
  search_bid_wiki: BookOpenCheckIcon,
  list_knowledge_portfolio: BookOpenCheckIcon,
  propose_memory: BookOpenCheckIcon,
  forget_memory: Trash2Icon,
  upload_document: UploadCloudIcon,
  delete_project: Trash2Icon,
};

export function getAssistantToolLabel(toolName: string | undefined, t: Translate) {
  if (!toolName) {
    return t("activity.tool.default", { defaultValue: "平台操作" });
  }
  return t(`activity.tool.${toolName}`, {
    defaultValue: TOOL_FALLBACK_LABELS[toolName] ?? t("activity.tool.default", { defaultValue: "平台操作" }),
  });
}

export function getAssistantToolIcon(item: AssistantExecutionItem): LucideIcon {
  if (item.kind === "workflow") return FilePenLineIcon;
  if (item.toolName && TOOL_ICONS[item.toolName]) return TOOL_ICONS[item.toolName];
  return WrenchIcon;
}
