'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link2, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { PageHeader } from '@/components/bidpilot/page-header';
import { EmptyState, QueryError, QuerySkeleton } from '@/components/bidpilot/query-state';
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
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import {
  createWebhookEndpoint,
  deleteWebhookEndpoint,
  getWebhookOverview,
  type WebhookEventType
} from '@/lib/bidpilot-api';

const EVENTS: WebhookEventType[] = [
  'radar.notice.matched',
  'radar.notice.saved',
  'radar.notice.converted'
];

export default function WebhookSettingsPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['webhook-overview'], queryFn: getWebhookOverview });
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const create = useMutation({
    mutationFn: createWebhookEndpoint,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['webhook-overview'] });
      setOpen(false);
      setName('');
      setUrl('');
    }
  });
  const remove = useMutation({
    mutationFn: deleteWebhookEndpoint,
    onSuccess: () => client.invalidateQueries({ queryKey: ['webhook-overview'] })
  });
  const endpoints = query.data?.endpoints ?? [];
  const supportedEvents = Array.isArray(query.data?.supported_events)
    ? query.data.supported_events
    : EVENTS;
  return (
    <>
      <PageHeader
        eyebrow='设置'
        title='Webhooks'
        description='把明确的业务事件发送到你管理的外部系统。签名密钥只在创建或轮换时返回。'
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus data-icon='inline-start' />
            添加端点
          </Button>
        }
      />
      <div className='flex flex-1 flex-col gap-5 px-5 py-6 lg:px-8'>
        {query.isPending ? (
          <QuerySkeleton rows={4} />
        ) : query.error ? (
          <QueryError message={query.error instanceof Error ? query.error.message : undefined} />
        ) : !endpoints.length ? (
          <EmptyState
            title='还没有 Webhook'
            description='添加端点后，项目业务事件可以被推送到外部系统。'
          />
        ) : (
          <Card>
            <CardHeader className='border-b'>
              <h2 className='font-medium'>已配置端点</h2>
            </CardHeader>
            <CardContent className='divide-y p-0'>
              {endpoints.map((endpoint) => (
                <div className='flex items-center gap-4 px-5 py-4' key={endpoint.id}>
                  <span className='bg-primary/10 text-primary flex size-9 items-center justify-center rounded-lg'>
                    <Link2 className='size-4' />
                  </span>
                  <div className='min-w-0 flex-1'>
                    <p className='truncate text-sm font-medium'>{endpoint.name}</p>
                    <p className='text-muted-foreground mt-1 truncate text-xs'>
                      {endpoint.target_url}
                    </p>
                    <div className='mt-2 flex flex-wrap gap-1'>
                      {endpoint.events.map((event) => (
                        <Badge variant='outline' key={event}>
                          {event}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <Badge variant={endpoint.is_active ? 'secondary' : 'outline'}>
                    {endpoint.is_active ? '启用' : '停用'}
                  </Badge>
                  <Button
                    size='icon-sm'
                    variant='ghost'
                    aria-label={`删除 ${endpoint.name}`}
                    title='删除端点'
                    onClick={() => remove.mutate(endpoint.id)}
                    disabled={remove.isPending}
                  >
                    <Trash2 className='text-destructive size-4' />
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
        <Card>
          <CardHeader className='border-b'>
            <h2 className='font-medium'>支持的事件</h2>
          </CardHeader>
          <CardContent className='flex flex-wrap gap-2 p-5'>
            {supportedEvents.map((event) => (
              <Badge variant='outline' key={event}>
                {event}
              </Badge>
            ))}
          </CardContent>
        </Card>
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加 Webhook 端点</DialogTitle>
            <DialogDescription>
              默认订阅全部支持的事件，具体投递状态可在服务端记录中查看。
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (name.trim() && url.trim())
                create.mutate({ name: name.trim(), target_url: url.trim(), events: EVENTS });
            }}
          >
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor='webhook-name'>名称</FieldLabel>
                <Input
                  id='webhook-name'
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                />
              </Field>
              <Field>
                <FieldLabel htmlFor='webhook-url'>目标 URL</FieldLabel>
                <Input
                  id='webhook-url'
                  type='url'
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder='https://example.com/hooks/bidpilot'
                  required
                />
              </Field>
            </FieldGroup>
            <DialogFooter>
              <Button type='button' variant='outline' onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button type='submit' disabled={create.isPending || !name.trim() || !url.trim()}>
                保存端点
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
