'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BrainCircuit, Check, Cpu, ShieldCheck, Trash2 } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import {
  clearPersonalMemory,
  deleteMemory,
  deletePersonalProfileMemory,
  getPersonalMemory,
  updateCurrentUser,
  type PersonalProfileMemoryRead,
  type MemoryRead
} from '@/lib/bidpilot-api';
import { PageHeader } from '@/components/bidpilot/page-header';
import { QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';

export default function MemorySettingsPage() {
  const { user, refresh } = useAuth();
  const queryClient = useQueryClient();
  const [selectedLocalMemory, setSelectedLocalMemory] = useState<MemoryRead | null>(null);
  const [selectedProfileMemory, setSelectedProfileMemory] =
    useState<PersonalProfileMemoryRead | null>(null);
  const [clearOpen, setClearOpen] = useState(false);
  const memory = useQuery({
    queryKey: ['personal-memory'],
    queryFn: getPersonalMemory,
    enabled: Boolean(user)
  });
  const updatePreference = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: async (_nextUser, variables) => {
      await refresh();
      toast.success(variables.memory_enabled ? '个人偏好已开启。' : '个人偏好已关闭。');
    },
    onError: () => toast.error('设置暂时无法保存，请稍后再试。')
  });
  const removeLocalMemory = useMutation({
    mutationFn: deleteMemory,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['personal-memory'] });
      setSelectedLocalMemory(null);
      toast.success('这条个人偏好已删除。');
    },
    onError: () => toast.error('删除失败，请稍后再试。')
  });
  const removeProfileMemory = useMutation({
    mutationFn: deletePersonalProfileMemory,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['personal-memory'] });
      setSelectedProfileMemory(null);
      toast.success('这条个人偏好已删除。');
    },
    onError: () => toast.error('删除失败，请稍后再试。')
  });
  const clearMemory = useMutation({
    mutationFn: clearPersonalMemory,
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['personal-memory'] });
      setClearOpen(false);
      if (result.provider_status === 'failed') {
        toast.error('本地个人偏好已清除，但云端记录暂时未能清除。');
      } else {
        toast.success('个人偏好已全部清除。');
      }
    },
    onError: () => toast.error('清除失败，请稍后再试。')
  });
  const enabled = user?.memory_enabled ?? true;
  const localRecords = memory.data?.local_records ?? [];
  const profileRecords = memory.data?.profile_records ?? [];
  const totalRecords = localRecords.length + profileRecords.length;

  return (
    <>
      <PageHeader
        eyebrow='工作区设置'
        title='个性化与记忆'
        description='管理助手是否记住你的表达偏好和工作方式。项目资料、项目知识和团队方法不受此开关影响。'
        action={
          <Link className={buttonVariants({ variant: 'outline' })} href='/settings/providers'>
            <Cpu data-icon='inline-start' />
            模型与连接
          </Link>
        }
      />
      <div className='flex flex-1 flex-col gap-6 px-5 py-6 lg:px-8'>
        <Card>
          <CardHeader className='flex flex-row items-start gap-4 border-b'>
            <div className='bg-primary/10 text-primary flex size-10 shrink-0 items-center justify-center rounded-lg'>
              <BrainCircuit className='size-5' />
            </div>
            <div className='min-w-0 flex-1'>
              <h2 className='font-medium'>个人偏好</h2>
              <p className='text-muted-foreground mt-1 text-sm leading-6'>
                用于记住你明确表达过的语言、格式和协作习惯，只服务于你的账户。
              </p>
            </div>
            <Switch
              aria-label='启用个人偏好'
              checked={enabled}
              disabled={!user || updatePreference.isPending}
              onCheckedChange={(checked) => updatePreference.mutate({ memory_enabled: checked })}
            />
          </CardHeader>
          <CardContent className='space-y-4 p-5'>
            <Alert>
              <ShieldCheck className='size-4' />
              <AlertTitle>{enabled ? '已启用' : '已关闭'}</AlertTitle>
              <AlertDescription>
                {enabled
                  ? '助手会参考你的个人偏好，但不会把它们加入项目共享知识。'
                  : '关闭后不会读取或新增个人偏好；已有记录仍保留，你可以在下方逐条删除。'}
              </AlertDescription>
            </Alert>
            <div className='text-muted-foreground flex flex-wrap gap-x-6 gap-y-2 text-xs'>
              <span>项目知识：由项目成员审核后生效</span>
              <span>团队方法：由工作区发布和维护</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className='border-b'>
            <div className='flex items-center justify-between gap-4'>
              <div>
                <h2 className='font-medium'>已保存的个人偏好</h2>
                <p className='text-muted-foreground mt-1 text-sm'>
                  你可以随时删除，不影响项目资料和已交付文件。
                </p>
              </div>
              {totalRecords ? (
                <div className='flex items-center gap-2'>
                  <Badge variant='secondary'>{totalRecords} 条</Badge>
                  <Button
                    size='sm'
                    variant='outline'
                    onClick={() => setClearOpen(true)}
                    disabled={clearMemory.isPending}
                  >
                    全部清除
                  </Button>
                </div>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className='p-0'>
            {memory.isPending ? (
              <div className='p-5'>
                <QuerySkeleton rows={3} />
              </div>
            ) : memory.error ? (
              <div className='p-5'>
                <QueryError message='个人偏好暂时无法加载，请稍后重试。' />
              </div>
            ) : totalRecords ? (
              <div className='divide-y'>
                {localRecords.map((item) => (
                  <MemoryItem
                    item={item}
                    key={`local-${item.id}`}
                    onDelete={() => setSelectedLocalMemory(item)}
                  />
                ))}
                {profileRecords.map((item) => (
                  <ProfileMemoryItem
                    item={item}
                    key={`profile-${item.id}`}
                    onDelete={() => setSelectedProfileMemory(item)}
                  />
                ))}
              </div>
            ) : (
              <div className='p-5'>
                <div className='text-muted-foreground flex items-start gap-3 text-sm'>
                  <Check className='text-primary mt-0.5 size-4 shrink-0' />
                  <p>还没有保存的个人偏好。你明确告诉助手后，确认过的偏好才会出现在这里。</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <AlertDialog
        open={Boolean(selectedLocalMemory || selectedProfileMemory)}
        onOpenChange={(open) => {
          if (!open && !removeLocalMemory.isPending && !removeProfileMemory.isPending) {
            setSelectedLocalMemory(null);
            setSelectedProfileMemory(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除这条个人偏好？</AlertDialogTitle>
            <AlertDialogDescription>
              删除后，助手不会再使用这条偏好。项目资料、项目知识和团队方法不会受到影响。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              disabled={removeLocalMemory.isPending || removeProfileMemory.isPending}
            >
              取消
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={
                removeLocalMemory.isPending ||
                removeProfileMemory.isPending ||
                (!selectedLocalMemory && !selectedProfileMemory)
              }
              onClick={() => {
                if (selectedLocalMemory) removeLocalMemory.mutate(selectedLocalMemory.id);
                if (selectedProfileMemory) removeProfileMemory.mutate(selectedProfileMemory.id);
              }}
            >
              {removeLocalMemory.isPending || removeProfileMemory.isPending
                ? '删除中…'
                : '删除偏好'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog open={clearOpen} onOpenChange={setClearOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>清除全部个人偏好？</AlertDialogTitle>
            <AlertDialogDescription>
              这会删除当前账户下的个人偏好记录。项目资料、项目知识、团队方法和已交付文件不会受到影响。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={clearMemory.isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={clearMemory.isPending}
              onClick={() => clearMemory.mutate()}
            >
              {clearMemory.isPending ? '清除中…' : '确认清除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function MemoryItem({
  item,
  onDelete
}: {
  item: MemoryRead;
  onDelete: () => void;
}) {
  return (
    <div className='flex items-start gap-4 px-5 py-4'>
      <div className='bg-muted flex size-9 shrink-0 items-center justify-center rounded-lg'>
        <BrainCircuit className='text-muted-foreground size-4' />
      </div>
      <div className='min-w-0 flex-1'>
        <div className='flex flex-wrap items-center gap-2'>
          <p className='font-medium'>{item.title}</p>
          <Badge variant='outline'>{memoryKindLabel(item.kind)}</Badge>
        </div>
        <p className='text-muted-foreground mt-2 whitespace-pre-wrap text-sm leading-6'>
          {item.body_markdown}
        </p>
        <p className='text-muted-foreground mt-2 text-xs'>
          最近更新 {formatDate(item.updated_at || item.created_at)}
        </p>
      </div>
      <Button
        aria-label='删除个人偏好'
        title='删除偏好'
        variant='ghost'
        size='icon-sm'
        onClick={onDelete}
      >
        <Trash2 className='text-destructive size-4' />
      </Button>
    </div>
  );
}

function ProfileMemoryItem({
  item,
  onDelete
}: {
  item: PersonalProfileMemoryRead;
  onDelete: () => void;
}) {
  return (
    <div className='flex items-start gap-4 px-5 py-4'>
      <div className='bg-muted flex size-9 shrink-0 items-center justify-center rounded-lg'>
        <BrainCircuit className='text-muted-foreground size-4' />
      </div>
      <div className='min-w-0 flex-1'>
        <div className='flex flex-wrap items-center gap-2'>
          <p className='font-medium'>个人偏好</p>
          <Badge variant='outline'>已确认</Badge>
        </div>
        <p className='text-muted-foreground mt-2 text-sm leading-6'>{item.text}</p>
        <p className='text-muted-foreground mt-2 text-xs'>来源：你的助手对话</p>
      </div>
      <Button
        aria-label='删除个人偏好'
        title='删除偏好'
        variant='ghost'
        size='icon-sm'
        onClick={onDelete}
      >
        <Trash2 className='text-destructive size-4' />
      </Button>
    </div>
  );
}

function memoryKindLabel(kind: MemoryRead['kind']) {
  return kind === 'preference' ? '偏好' : '个人记录';
}

function formatDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat('zh-CN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      }).format(new Date(value))
    : '—';
}
