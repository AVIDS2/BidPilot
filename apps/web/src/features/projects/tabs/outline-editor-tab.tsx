import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  createDeliverableSection,
  deleteDeliverableSection,
  reorderDeliverableSections,
  updateDeliverableSection,
  type DeliverableRead,
  type DeliverableSectionRead,
} from "@/lib/api";
import { ArrowDownIcon, ArrowUpIcon, ListTreeIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";

interface OutlineEditorTabProps {
  projectId: string;
  deliverableId: string | null;
  deliverables: DeliverableRead[];
  sections: DeliverableSectionRead[] | undefined;
}

function slugifySectionKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9一-鿿]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "section";
}

export function OutlineEditorTab({
  projectId,
  deliverableId,
  deliverables,
  sections,
}: OutlineEditorTabProps) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [sectionKey, setSectionKey] = useState("");
  const ordered = useMemo(
    () =>
      [...(sections ?? [])].sort(
        (a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.section_key.localeCompare(b.section_key),
      ),
    [sections],
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["sections", deliverableId] });
    queryClient.invalidateQueries({ queryKey: ["deliverables", projectId] });
  };

  const createMut = useMutation({
    mutationFn: createDeliverableSection,
    onSuccess: () => {
      invalidate();
      setTitle("");
      setSectionKey("");
      toast.success("章节已加入大纲");
    },
    onError: () => toast.error("添加章节失败"),
  });

  const renameMut = useMutation({
    mutationFn: ({ id, title: nextTitle }: { id: string; title: string }) =>
      updateDeliverableSection(id, { title: nextTitle }),
    onSuccess: () => {
      invalidate();
      toast.success("章节标题已更新");
    },
    onError: () => toast.error("更新标题失败"),
  });

  const reorderMut = useMutation({
    mutationFn: (sectionIds: string[]) => {
      if (!deliverableId) throw new Error("missing deliverable");
      return reorderDeliverableSections(deliverableId, sectionIds);
    },
    onSuccess: () => {
      invalidate();
      toast.success("大纲顺序已更新");
    },
    onError: () => toast.error("调整顺序失败"),
  });

  const deleteMut = useMutation({
    mutationFn: (sectionId: string) => deleteDeliverableSection(sectionId, false),
    onSuccess: () => {
      invalidate();
      toast.success("章节已删除");
    },
    onError: (error: unknown) => {
      const detail =
        typeof error === "object" && error && "message" in error
          ? String((error as { message?: string }).message)
          : "";
      if (detail.includes("section_has_content") || detail.includes("409")) {
        toast.error("章节已有正文，暂不可直接删除");
      } else {
        toast.error("删除章节失败");
      }
    },
  });

  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= ordered.length) return;
    const next = ordered.map((item) => item.id);
    const [removed] = next.splice(index, 1);
    next.splice(target, 0, removed);
    reorderMut.mutate(next);
  };

  if (!deliverableId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">大纲编辑台</CardTitle>
          <CardDescription>先创建交付物，再维护章节大纲。</CardDescription>
        </CardHeader>
        <CardContent>
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <ListTreeIcon />
              </EmptyMedia>
              <EmptyTitle>还没有可编辑的大纲</EmptyTitle>
              <EmptyDescription>
                {deliverables.length === 0
                  ? "请先在「交付物」页签创建一个提案交付物。"
                  : "正在加载交付物章节…"}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">大纲编辑台</CardTitle>
        <CardDescription>
          增删改章节、调整顺序。写前大纲决定后续分章起草与导出结构。
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <FieldGroup className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <Field>
            <FieldLabel htmlFor="outline-title">章节标题</FieldLabel>
            <Input
              id="outline-title"
              value={title}
              onChange={(event) => {
                const next = event.target.value;
                setTitle(next);
                if (!sectionKey || sectionKey === slugifySectionKey(title)) {
                  setSectionKey(slugifySectionKey(next));
                }
              }}
              placeholder="例如：技术方案"
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="outline-key">section_key</FieldLabel>
            <Input
              id="outline-key"
              value={sectionKey}
              onChange={(event) => setSectionKey(slugifySectionKey(event.target.value))}
              placeholder="technical-approach"
            />
          </Field>
          <Button
            size="sm"
            disabled={!title.trim() || !sectionKey.trim() || createMut.isPending}
            onClick={() =>
              createMut.mutate({
                deliverable_id: deliverableId,
                section_key: sectionKey.trim(),
                title: title.trim(),
              })
            }
          >
            <PlusIcon className="size-4" />
            添加章节
          </Button>
        </FieldGroup>

        {ordered.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <ListTreeIcon />
              </EmptyMedia>
              <EmptyTitle>大纲为空</EmptyTitle>
              <EmptyDescription>添加首个章节后即可开始 outline-first 起草。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ol className="flex flex-col gap-2">
            {ordered.map((section, index) => (
              <li
                key={section.id}
                className="flex flex-col gap-2 rounded-lg border bg-card/40 p-3 md:flex-row md:items-center"
              >
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <span className="text-muted-foreground w-6 text-sm tabular-nums">{index + 1}</span>
                  <Input
                    defaultValue={section.title}
                    className="max-w-md"
                    onBlur={(event) => {
                      const next = event.target.value.trim();
                      if (next && next !== section.title) {
                        renameMut.mutate({ id: section.id, title: next });
                      }
                    }}
                  />
                  <Badge variant="outline">{section.section_key}</Badge>
                  <Badge variant={section.status === "approved" ? "default" : "secondary"}>
                    {section.status}
                  </Badge>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    disabled={index === 0 || reorderMut.isPending}
                    onClick={() => move(index, -1)}
                    aria-label="上移"
                  >
                    <ArrowUpIcon className="size-4" />
                  </Button>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    disabled={index === ordered.length - 1 || reorderMut.isPending}
                    onClick={() => move(index, 1)}
                    aria-label="下移"
                  >
                    <ArrowDownIcon className="size-4" />
                  </Button>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    disabled={deleteMut.isPending || section.status === "approved"}
                    onClick={() => deleteMut.mutate(section.id)}
                    aria-label="删除"
                  >
                    <Trash2Icon className="size-4" />
                  </Button>
                </div>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
