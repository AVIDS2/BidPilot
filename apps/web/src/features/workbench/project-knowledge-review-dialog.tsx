'use client';

import { useState, type FormEvent } from 'react';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { Textarea } from '@/components/ui/textarea';
import type { MemoryRead, MemorySupersedePayload, MemoryUpdatePayload } from '@/lib/bidpilot-api';

export type ProjectKnowledgeReviewMode = 'edit' | 'reject' | 'supersede';

interface ProjectKnowledgeReviewDialogProps {
  item: MemoryRead | null;
  mode: ProjectKnowledgeReviewMode | null;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: (payload: MemoryUpdatePayload) => void;
  onReject: (reason: string) => void;
  onSupersede: (payload: MemorySupersedePayload) => void;
}

export function ProjectKnowledgeReviewDialog({
  item,
  mode,
  pending,
  onOpenChange,
  onEdit,
  onReject,
  onSupersede
}: ProjectKnowledgeReviewDialogProps) {
  const [title, setTitle] = useState(item?.title ?? '');
  const [body, setBody] = useState(item?.body_markdown ?? '');
  const [expiryDate, setExpiryDate] = useState(toDateInputValue(item?.expires_at ?? null));
  const [reason, setReason] = useState('');

  const open = Boolean(item && mode);
  const editingActive = mode === 'edit' && item?.status === 'active';

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const expiresAt = expiryDate ? `${expiryDate}T23:59:59` : null;
    if (mode === 'edit') {
      const payload: MemoryUpdatePayload = { expires_at: expiresAt };
      if (!editingActive) {
        payload.title = title.trim();
        payload.body_markdown = body.trim();
      }
      onEdit(payload);
      return;
    }
    if (mode === 'reject') {
      onReject(reason.trim());
      return;
    }
    onSupersede({
      title: title.trim(),
      body_markdown: body.trim(),
      expires_at: expiresAt
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-xl'>
        <DialogHeader>
          <DialogTitle>{dialogTitle(mode, editingActive)}</DialogTitle>
          <DialogDescription>{dialogDescription(mode, editingActive)}</DialogDescription>
        </DialogHeader>
        <form className='flex flex-col gap-5' onSubmit={submit}>
          {mode === 'reject' ? (
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor='memory-reject-reason'>退回说明（可选）</FieldLabel>
                <Textarea
                  id='memory-reject-reason'
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder='告诉提交人还需要补充或修正什么'
                  rows={5}
                />
                <FieldDescription>
                  退回后，这条内容不会进入项目知识，也不会被助手引用。
                </FieldDescription>
              </Field>
            </FieldGroup>
          ) : (
            <FieldGroup>
              {!editingActive ? (
                <>
                  <Field>
                    <FieldLabel htmlFor='memory-review-title'>标题</FieldLabel>
                    <Input
                      id='memory-review-title'
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      required
                      maxLength={240}
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor='memory-review-body'>内容</FieldLabel>
                    <Textarea
                      id='memory-review-body'
                      value={body}
                      onChange={(event) => setBody(event.target.value)}
                      required
                      maxLength={12000}
                      rows={7}
                    />
                    <FieldDescription>
                      保留清晰、可核对的表述，来源依据会继续沿用。
                    </FieldDescription>
                  </Field>
                </>
              ) : null}
              <Field>
                <FieldLabel htmlFor='memory-review-expiry'>有效期（可选）</FieldLabel>
                <Input
                  id='memory-review-expiry'
                  type='date'
                  value={expiryDate}
                  onChange={(event) => setExpiryDate(event.target.value)}
                />
                <FieldDescription>
                  {editingActive
                    ? '到期后，助手将不再把这条知识带入新的工作。'
                    : '留空表示长期有效，之后仍可在这里调整。'}
                </FieldDescription>
              </Field>
            </FieldGroup>
          )}
          <DialogFooter>
            <DialogClose render={<Button type='button' variant='outline' />}>取消</DialogClose>
            <Button
              type='submit'
              disabled={pending || (mode === 'supersede' && (!title.trim() || !body.trim()))}
            >
              {pending ? <Spinner data-icon='inline-start' /> : null}
              {submitLabel(mode, editingActive)}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function toDateInputValue(value: string | null) {
  return value ? value.slice(0, 10) : '';
}

function dialogTitle(mode: ProjectKnowledgeReviewMode | null, editingActive: boolean) {
  if (mode === 'reject') return '退回知识建议';
  if (mode === 'supersede') return '创建替代版本';
  return editingActive ? '调整知识有效期' : '编辑知识建议';
}

function dialogDescription(mode: ProjectKnowledgeReviewMode | null, editingActive: boolean) {
  if (mode === 'reject') return '退回后原建议会保留在审核记录中，但不会进入项目知识。';
  if (mode === 'supersede') return '原知识会保留为历史版本，新版本确认后才会生效。';
  return editingActive
    ? '只调整这条已生效知识的有效期，不会改变它的内容和来源。'
    : '修改后的建议仍需要确认，确认前不会影响助手的工作。';
}

function submitLabel(mode: ProjectKnowledgeReviewMode | null, editingActive: boolean) {
  if (mode === 'reject') return '退回建议';
  if (mode === 'supersede') return '创建替代版本';
  return editingActive ? '保存有效期' : '保存修改';
}
