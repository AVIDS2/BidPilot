import { PageHeader } from '@/components/bidpilot/page-header';
import { KnowledgeWorkspace } from '@/features/knowledge/knowledge-workspace';

export default function KnowledgePage() {
  return (
    <>
      <PageHeader
        eyebrow='AI 知识工作区'
        title='知识库'
        description='像 AI 工作区一样整理资料、检索依据，并确认可以交给 Copilot 使用的项目知识。'
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        <KnowledgeWorkspace />
      </div>
    </>
  );
}
