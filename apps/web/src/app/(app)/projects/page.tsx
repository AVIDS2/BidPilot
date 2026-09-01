'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FolderKanban, Plus, Search } from 'lucide-react';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Badge } from '@/components/ui/badge';
import { buttonVariants, Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { createProject, listProjects, type ProjectRead } from '@/lib/bidpilot-api';

export default function ProjectsPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['projects'], queryFn: listProjects });
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [name, setName] = useState('');
  const [scenario, setScenario] = useState('bidpilot');
  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['projects'] });
      setOpen(false);
      setName('');
    }
  });
  const data =
    query.data?.filter((project) =>
      `${project.name} ${project.slug}`.toLowerCase().includes(search.toLowerCase())
    ) ?? [];

  return (
    <>
      <PageHeader
        eyebrow='投标工作流'
        title='项目'
        description='每个项目拥有独立的资料包、需求、证据、运行记录和交付物。'
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus data-icon='inline-start' />
            新建项目
          </Button>
        }
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {query.isPending ? (
          <QuerySkeleton rows={5} />
        ) : query.error ? (
          <QueryError message={query.error instanceof Error ? query.error.message : undefined} />
        ) : (
          <Card>
            <CardContent className='p-0'>
              <div className='flex flex-col gap-3 border-b p-4 sm:flex-row sm:items-center sm:justify-between'>
                <div className='relative w-full max-w-sm'>
                  <Search className='text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2' />
                  <Input
                    className='pl-8'
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder='搜索项目'
                    aria-label='搜索项目'
                  />
                </div>
                <p className='text-muted-foreground text-sm'>{query.data?.length ?? 0} 个项目</p>
              </div>
              {data.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>项目</TableHead>
                      <TableHead>场景</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead className='text-right'>进入</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.map((project) => (
                      <ProjectRow key={project.id} project={project} />
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className='p-5'>
                  <EmptyState
                    title={query.data?.length ? '没有匹配项目' : '还没有项目'}
                    description={
                      query.data?.length
                        ? '换一个搜索词试试。'
                        : '创建项目后，从资料包开始建立响应工作区。'
                    }
                  />
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建投标项目</DialogTitle>
            <DialogDescription>创建后可以继续上传招标文件和企业资料。</DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (name.trim())
                mutation.mutate({
                  name: name.trim(),
                  scenario_package: scenario.trim() || 'bidpilot'
                });
            }}
          >
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor='project-name'>项目名称</FieldLabel>
                <Input
                  id='project-name'
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder='例如：某医院内窥镜维保服务'
                  required
                />
                <FieldDescription>名称会显示在项目、运行和交付页面。</FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor='project-scenario'>场景包</FieldLabel>
                <Input
                  id='project-scenario'
                  value={scenario}
                  onChange={(event) => setScenario(event.target.value)}
                  required
                />
              </Field>
            </FieldGroup>
            <DialogFooter>
              <Button type='button' variant='outline' onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button type='submit' disabled={mutation.isPending || !name.trim()}>
                {mutation.isPending ? '创建中…' : '创建项目'}
              </Button>
            </DialogFooter>
            {mutation.error && (
              <p className='text-destructive text-sm' role='alert'>
                {mutation.error instanceof Error ? mutation.error.message : '创建失败'}
              </p>
            )}
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ProjectRow({ project }: { project: ProjectRead }) {
  return (
    <TableRow>
      <TableCell>
        <Link className='flex min-w-0 items-center gap-3' href={`/projects/${project.id}`}>
          <span className='bg-primary/10 text-primary flex size-8 shrink-0 items-center justify-center rounded-md'>
            <FolderKanban className='size-4' />
          </span>
          <span className='min-w-0'>
            <span className='block truncate font-medium'>{project.name}</span>
            <span className='text-muted-foreground mt-1 block truncate text-xs'>
              {project.slug}
            </span>
          </span>
        </Link>
      </TableCell>
      <TableCell className='text-muted-foreground'>{project.scenario_package}</TableCell>
      <TableCell>
        <Badge variant={['failed', 'error'].includes(project.status) ? 'destructive' : 'outline'}>
          {project.status}
        </Badge>
      </TableCell>
      <TableCell className='text-right'>
        <Link
          className={buttonVariants({ variant: 'ghost', size: 'sm' })}
          href={`/projects/${project.id}`}
        >
          打开
        </Link>
      </TableCell>
    </TableRow>
  );
}
