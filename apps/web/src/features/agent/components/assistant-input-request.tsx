import { useMemo, useState } from "react";
import { ArrowRightIcon, ListChecksIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AssistantInputRequest } from "@/features/agent/state/agent-store";

const FIELD_LABELS: Record<string, string> = {
  name: "项目名称",
  project_id: "项目",
  section_id: "章节",
  section_key: "章节标识",
  section_version_id: "章节版本",
  deliverable_id: "交付物",
  requirement_id: "需求项",
  memory_id: "知识记录",
  memory_record_id: "知识记录",
  body_markdown: "内容",
  url: "公开资料链接",
};

function fieldLabel(field: string) {
  return FIELD_LABELS[field] ?? field.replace(/_/g, " ");
}

function answerFromValues(fields: string[], values: Record<string, string>) {
  return fields
    .map((field) => `${fieldLabel(field)}：${values[field]?.trim() ?? ""}`)
    .filter((line) => !line.endsWith("："))
    .join("\n");
}

export function AssistantInputRequestForm({
  request,
  onSubmit,
}: {
  request: AssistantInputRequest;
  onSubmit: (content: string) => void;
}) {
  const fields = useMemo(
    () => request.missingFields.length > 0 ? request.missingFields : ["details"],
    [request.missingFields],
  );
  const [values, setValues] = useState<Record<string, string>>({});
  const canSubmit = fields.every((field) => Boolean(values[field]?.trim()));

  return (
    <form
      className="mx-auto w-full max-w-[760px] border-t border-border/70 py-4"
      onSubmit={(event) => {
        event.preventDefault();
        const content = answerFromValues(fields, values);
        if (content) onSubmit(content);
      }}
    >
      <div className="flex items-start gap-2">
        <ListChecksIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground">需要补充信息</p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{request.message}</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {fields.map((field) => (
              <label className="grid gap-1.5 text-xs font-medium text-foreground" key={field}>
                {fieldLabel(field)}
                <Input
                  autoComplete="off"
                  value={values[field] ?? ""}
                  onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))}
                  placeholder={`填写${fieldLabel(field)}`}
                />
              </label>
            ))}
          </div>
          <div className="mt-3 flex justify-end">
            <Button className="gap-1.5" disabled={!canSubmit} size="sm" type="submit">
              继续执行 <ArrowRightIcon className="size-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}
