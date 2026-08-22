const VALUE_LABELS: Record<string, string> = {
  active: "进行中",
  inactive: "已停用",
  draft: "草稿",
  pending: "待处理",
  queued: "排队中",
  running: "进行中",
  ready: "就绪",
  confirmed: "已确认",
  untriaged: "待分派",
  assigned: "已分派",
  review: "待审核",
  in_review: "审核中",
  needs_review: "待审核",
  approved: "已批准",
  rejected: "已驳回",
  completed: "已完成",
  succeeded: "已完成",
  failed: "失败",
  blocked: "受阻",
  open: "待处理",
  resolved: "已解决",
  verified: "已核验",
  unverified: "待核验",
  partial: "部分核验",
  covered: "已覆盖",
  uncovered: "未覆盖",
  disputed: "存在争议",
  sufficient: "证据充足",
  weak: "证据不足",
  missing: "缺少证据",
  low: "低",
  medium: "中",
  high: "高",
  critical: "紧急",
  not_exported: "未导出",
  exported: "已导出",
  sent: "已发送",
  accepted: "已接受",
  revoked: "已撤销",
  expired: "已过期",
  owner: "工作区所有者",
  admin: "管理员",
  member: "成员",
  openai: "OpenAI 兼容",
  anthropic: "Anthropic Messages",
  free: "免费版",
  starter: "入门版",
  professional: "专业版",
  enterprise: "企业版",
  trialing: "试用中",
  past_due: "待处理",
  canceled: "已取消",
};

const DELIVERABLE_TYPE_LABELS: Record<string, string> = {
  bid_response: "投标响应文件",
  technical_response: "技术响应",
  commercial_response: "商务响应",
  proposal: "投标方案",
  response: "响应文件",
  document: "文档",
};

const RUN_TYPE_LABELS: Record<string, string> = {
  draft: "章节起草",
  draft_section: "章节起草",
  redraft_section: "章节重写",
  ingest_bundle: "资料解析",
  memory_graph_extraction: "知识关系提取",
};

export function displayWorkbenchValue(value?: string | null, labels = VALUE_LABELS) {
  if (!value) return "-";
  return labels[value.trim().toLowerCase()] ?? value;
}

export function displayDeliverableType(value?: string | null) {
  return displayWorkbenchValue(value, DELIVERABLE_TYPE_LABELS);
}

export function displayRunType(value?: string | null) {
  return displayWorkbenchValue(value, RUN_TYPE_LABELS);
}
