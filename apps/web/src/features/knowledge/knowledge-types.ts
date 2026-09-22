import type {
  BundleRead,
  MemoryRead,
  ProjectRead,
  SearchResult,
  SourceDocumentRead
} from '@/lib/bidpilot-api';

export type WorkspaceView = 'documents' | 'knowledge';
export type InspectorView = 'search' | 'document' | 'status';
export type DocumentRecord = SourceDocumentRead & { bundle: BundleRead; project: ProjectRead };

export const sourceTypeLabels: Record<string, string> = {
  buyer_rfp: '招标文件',
  supplier_evidence: '企业资料',
  supporting_material: '补充资料'
};

export const statusLabels: Record<string, string> = {
  pending: '等待处理',
  parsing: '解析中',
  parsed: '已解析',
  failed: '处理失败',
  not_applicable: '无需解析',
  queued: '准备处理',
  indexed: '可检索'
};

export function documentTone(status: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (status === 'failed') return 'destructive';
  if (status === 'parsed' || status === 'indexed') return 'secondary';
  return 'outline';
}

export function statusLabel(status: string) {
  return statusLabels[status] ?? status;
}

export function memoryStatusLabel(status: MemoryRead['status']) {
  return (
    {
      active: '已确认',
      proposed: '待确认',
      superseded: '已替代',
      rejected: '已退回',
      deleted: '已移除'
    }[status] ?? status
  );
}

export function memoryKindLabel(kind: MemoryRead['kind']) {
  return (
    {
      fact: '项目事实',
      decision: '项目决定',
      procedure: '工作方法',
      risk: '项目风险',
      summary: '项目总结',
      preference: '偏好',
      entity_note: '实体信息'
    }[kind] ?? kind
  );
}

export function projectStatusLabel(value: string) {
  return (
    {
      active: '进行中',
      draft: '草稿',
      completed: '已完成',
      archived: '已归档',
      failed: '需要处理'
    }[value] ?? '进行中'
  );
}

export function scenarioLabel(value: string) {
  return value === 'bidpilot' ? '招标响应' : value;
}

export type KnowledgeCenterProps = {
  view: WorkspaceView;
  onViewChange: (value: WorkspaceView) => void;
  documents: DocumentRecord[];
  memories: MemoryRead[];
  loadingDocuments: boolean;
  memoryLoading: boolean;
  memoryError: boolean;
  selectedDocumentId: string | null;
  onSelectDocument: (id: string) => void;
  onApproveMemory: (id: string) => void;
  approvingMemoryId: string | null;
  projectId: string;
};

export type KnowledgeInspectorProps = {
  view: InspectorView;
  onViewChange: (view: InspectorView) => void;
  searchText: string;
  onSearchTextChange: (value: string) => void;
  search: SearchResult[];
  searching: boolean;
  searchError: boolean;
  documents: DocumentRecord[];
  selectedDocument: DocumentRecord | null;
  onSelectDocument: (id: string) => void;
  project?: ProjectRead;
  documentCount: number;
  indexedCount: number;
  processingCount: number;
  activeMemoryCount: number;
  proposedMemoryCount: number;
  compiling: boolean;
  onCompile: () => void;
};
