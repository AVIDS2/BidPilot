'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Cpu, Plus, Server, Trash2 } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { PageHeader } from '@/components/bidpilot/page-header';
import { QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
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
  createProviderConfig,
  deleteProviderConfig,
  getPiModelCatalog,
  getPiRuntimeContract,
  listProviderConfigs,
  type ProviderConfigCreate
} from '@/lib/bidpilot-api';

export default function ProviderSettingsPage() {
  const { user } = useAuth();
  const client = useQueryClient();
  const configs = useQuery({ queryKey: ['provider-configs'], queryFn: listProviderConfigs });
  const catalog = useQuery({ queryKey: ['pi-model-catalog'], queryFn: getPiModelCatalog });
  const runtime = useQuery({
    queryKey: ['pi-runtime-contract'],
    queryFn: getPiRuntimeContract,
    enabled: user?.role === 'admin'
  });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ProviderConfigCreate>({
    provider_type: 'openai',
    provider_id: 'xiaomi',
    api_key: '',
    api_url: '',
    model: '',
    label: '小米 MiMo'
  });
  const create = useMutation({
    mutationFn: createProviderConfig,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['provider-configs'] });
      setOpen(false);
      setForm((current) => ({ ...current, api_key: '' }));
    }
  });
  const remove = useMutation({
    mutationFn: deleteProviderConfig,
    onSuccess: () => client.invalidateQueries({ queryKey: ['provider-configs'] })
  });
  return (
    <>
      <PageHeader
        eyebrow='工作区'
        title='模型供应商'
        description='配置你希望用于 Agent 任务的模型连接。密钥只提交给后端，不在页面中回显。'
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus data-icon='inline-start' />
            添加供应商
          </Button>
        }
      />
      <div className='grid flex-1 gap-6 px-5 py-6 lg:grid-cols-[1.1fr_0.9fr] lg:px-8'>
        <Card>
          <CardHeader className='flex flex-row items-start justify-between gap-3 border-b'>
            <div>
              <div className='flex items-center gap-2'>
                <Cpu className='text-primary size-4' />
                <h2 className='font-medium'>已配置供应商</h2>
              </div>
              <p className='text-muted-foreground mt-1 text-sm'>当前账户可用的模型连接。</p>
            </div>
          </CardHeader>
          <CardContent className='p-0'>
            {configs.isPending ? (
              <div className='p-5'>
                <QuerySkeleton rows={3} />
              </div>
            ) : configs.error ? (
              <div className='p-5'>
                <QueryError
                  message={configs.error instanceof Error ? configs.error.message : undefined}
                />
              </div>
            ) : configs.data?.data?.length ? (
              <div className='divide-y'>
                {configs.data.data.map((config) => (
                  <div className='flex items-center gap-4 px-5 py-4' key={config.id}>
                    <div className='bg-muted flex size-9 items-center justify-center rounded-lg'>
                      <Server className='size-4' />
                    </div>
                    <div className='min-w-0 flex-1'>
                      <p className='truncate text-sm font-medium'>{config.label}</p>
                      <p className='text-muted-foreground mt-1 truncate text-xs'>
                        {config.provider_type} · {config.model || '未指定模型'}
                      </p>
                    </div>
                    <Badge variant={config.is_active ? 'secondary' : 'outline'}>
                      {config.is_active ? '启用' : '停用'}
                    </Badge>
                    <Button
                      aria-label={`删除 ${config.label}`}
                      title='删除供应商'
                      variant='ghost'
                      size='icon-sm'
                      onClick={() => remove.mutate(config.id)}
                      disabled={remove.isPending}
                    >
                      <Trash2 className='text-destructive size-4' />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className='p-5'>
                <Alert>
                  <AlertTitle>尚未配置</AlertTitle>
                  <AlertDescription>
                    添加一个 OpenAI 兼容或 Anthropic 供应商后，Agent 才能使用该连接。
                  </AlertDescription>
                </Alert>
              </div>
            )}
          </CardContent>
        </Card>
        <div className='grid content-start gap-6'>
          <Card>
            <CardHeader className='border-b'>
              <h2 className='font-medium'>平台模型目录</h2>
              <p className='text-muted-foreground mt-1 text-sm'>查看平台当前支持的模型和供应商。</p>
            </CardHeader>
            <CardContent className='p-5'>
              {catalog.isPending ? (
                <QuerySkeleton rows={2} />
              ) : catalog.error ? (
                <QueryError
                  message={catalog.error instanceof Error ? catalog.error.message : undefined}
                />
              ) : (
                <div className='flex flex-col gap-3'>
                  <p className='text-sm'>
                    {catalog.data?.data.models.length ?? 0} 个模型 ·{' '}
                    {catalog.data?.data.providers.length ?? 0} 个供应商
                  </p>
                  <p className='text-muted-foreground text-xs'>
                    目录来源：{catalog.data?.data.source || '—'} · 版本：
                    {catalog.data?.data.version || '—'}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
          {user?.role === 'admin' ? (
            <Card>
              <CardHeader className='border-b'>
                <h2 className='font-medium'>Pi 运行时</h2>
                <p className='text-muted-foreground mt-1 text-sm'>
                  仅管理员可查看服务端运行时能力摘要。
                </p>
              </CardHeader>
              <CardContent className='p-5'>
                {runtime.isPending ? (
                  <QuerySkeleton rows={2} />
                ) : runtime.error ? (
                  <QueryError
                    message={runtime.error instanceof Error ? runtime.error.message : undefined}
                  />
                ) : runtime.data?.data ? (
                  <div className='flex flex-col gap-3 text-sm'>
                    <div className='flex justify-between gap-4'>
                      <span className='text-muted-foreground'>运行时版本</span>
                      <span>{runtime.data.data.version}</span>
                    </div>
                    <div className='flex justify-between gap-4'>
                      <span className='text-muted-foreground'>扩展能力</span>
                      <span>{runtime.data.data.extensions.length}</span>
                    </div>
                    <div className='flex justify-between gap-4'>
                      <span className='text-muted-foreground'>技能</span>
                      <span>{runtime.data.data.skills.length}</span>
                    </div>
                  </div>
                ) : (
                  <p className='text-muted-foreground text-sm'>暂无运行时信息。</p>
                )}
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加模型供应商</DialogTitle>
            <DialogDescription>连接信息由 FastAPI 保存和校验，页面不会回显密钥。</DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (form.api_key.trim() && form.model.trim()) create.mutate(form);
            }}
          >
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor='provider-label'>显示名称</FieldLabel>
                <Input
                  id='provider-label'
                  value={form.label}
                  onChange={(event) => setForm({ ...form, label: event.target.value })}
                  required
                />
              </Field>
              <Field>
                <FieldLabel htmlFor='provider-id'>供应商标识</FieldLabel>
                <Input
                  id='provider-id'
                  value={form.provider_id || ''}
                  onChange={(event) => setForm({ ...form, provider_id: event.target.value })}
                  placeholder='例如 xiaomi'
                />
                <FieldDescription>用于平台模型目录中的供应商标识。</FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor='provider-url'>兼容 API 地址</FieldLabel>
                <Input
                  id='provider-url'
                  value={form.api_url || ''}
                  onChange={(event) => setForm({ ...form, api_url: event.target.value })}
                  placeholder='可选'
                />
              </Field>
              <Field>
                <FieldLabel htmlFor='provider-model'>模型 ID</FieldLabel>
                <Input
                  id='provider-model'
                  value={form.model}
                  onChange={(event) => setForm({ ...form, model: event.target.value })}
                  required
                />
              </Field>
              <Field>
                <FieldLabel htmlFor='provider-key'>API 密钥</FieldLabel>
                <Input
                  id='provider-key'
                  type='password'
                  value={form.api_key}
                  onChange={(event) => setForm({ ...form, api_key: event.target.value })}
                  autoComplete='new-password'
                  required
                />
              </Field>
            </FieldGroup>
            <DialogFooter>
              <Button type='button' variant='outline' onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button
                type='submit'
                disabled={create.isPending || !form.api_key.trim() || !form.model.trim()}
              >
                {create.isPending ? '保存中…' : '保存连接'}
              </Button>
            </DialogFooter>
            {create.error && (
              <p className='text-destructive text-sm' role='alert'>
                {create.error instanceof Error ? create.error.message : '保存失败'}
              </p>
            )}
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
