'use client';

import { useState } from 'react';
import { IconFolder, IconFolderOpen, IconSearch, IconChevronRight } from '@tabler/icons-react';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { projectStatusLabel, scenarioLabel } from './knowledge-types';
import type { ProjectRead } from '@/lib/bidpilot-api';

export function KnowledgeProjectList({
  projects,
  projectId,
  onChange
}: {
  projects: ProjectRead[];
  projectId: string;
  onChange: (value: string) => void;
}) {
  const [filter, setFilter] = useState('');
  const visible = projects.filter((project) =>
    project.name.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className='flex h-full min-h-0 flex-col bg-muted/10'>
      <div className='flex items-center justify-between gap-3 px-4 py-4'>
        <div>
          <p className='text-sm font-semibold'>项目空间</p>
          <p className='text-muted-foreground mt-1 text-xs'>{projects.length} 个项目</p>
        </div>
        <IconFolderOpen className='text-muted-foreground' />
      </div>
      <div className='px-3 pb-3'>
        <div className='relative'>
          <IconSearch className='text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2' />
          <Input
            aria-label='搜索项目'
            className='h-8 pl-8'
            onChange={(event) => setFilter(event.target.value)}
            placeholder='搜索项目'
            value={filter}
          />
        </div>
      </div>
      <Separator />
      <ScrollArea className='min-h-0 flex-1'>
        <div className='flex flex-col gap-1 p-2'>
          {visible.map((project) => {
            const active = project.id === projectId;
            return (
              <button
                aria-current={active ? 'page' : undefined}
                className={`flex items-start gap-2 rounded-md px-2.5 py-2.5 text-left transition-colors ${
                  active ? 'bg-primary/10 text-primary' : 'hover:bg-muted/70'
                }`}
                key={project.id}
                onClick={() => onChange(project.id)}
                type='button'
              >
                <IconFolder className='mt-0.5 shrink-0' />
                <span className='min-w-0 flex-1'>
                  <span className='block truncate text-sm font-medium'>{project.name}</span>
                  <span className='text-muted-foreground mt-1 block truncate text-xs'>
                    {projectStatusLabel(project.status)} · {scenarioLabel(project.scenario_package)}
                  </span>
                </span>
                {active ? <IconChevronRight className='mt-0.5 shrink-0' /> : null}
              </button>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}
