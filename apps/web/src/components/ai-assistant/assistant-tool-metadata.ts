import {
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
  create_project: "创建项目",
  get_project_summary: "读取项目概览",
  list_project_bundles: "查看资料包",
  list_sections: "查看章节",
  list_pending_reviews: "查看待审核项",
  list_requirements: "查看需求",
  list_evidence: "查看证据",
  list_deliverables: "查看交付物",
  list_documents: "查看文档",
  get_section_versions: "查看章节版本",
  create_deliverable: "创建交付物",
  start_draft_section: "启动章节起草",
  start_redraft_section: "重新起草章节",
  get_runtime_status: "读取执行状态",
  retry_run: "重试任务",
  export_deliverable: "导出交付物",
  semantic_search: "检索资料",
  search_knowledge: "检索知识库",
  open_page: "打开页面",
  upload_document: "上传文档",
  delete_project: "删除项目",
};

const TOOL_ICONS: Record<string, LucideIcon> = {
  search_projects: SearchIcon,
  semantic_search: SearchIcon,
  search_knowledge: SearchIcon,
  get_project_summary: FolderOpenIcon,
  list_project_bundles: PackageIcon,
  list_sections: ListChecksIcon,
  list_pending_reviews: ListChecksIcon,
  list_requirements: ListChecksIcon,
  list_evidence: SearchIcon,
  list_deliverables: FilePenLineIcon,
  list_documents: PackageIcon,
  get_section_versions: FilePenLineIcon,
  create_project: FolderOpenIcon,
  create_deliverable: FilePenLineIcon,
  start_draft_section: FilePenLineIcon,
  start_redraft_section: FilePenLineIcon,
  get_runtime_status: TerminalIcon,
  retry_run: RefreshCcwIcon,
  export_deliverable: FilePenLineIcon,
  open_page: NavigationIcon,
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
