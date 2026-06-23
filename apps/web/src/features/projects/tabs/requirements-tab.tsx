import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { FieldGroup, Field, FieldLabel } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { ClipboardCheckIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { RequirementItemRead } from "@/lib/api";

interface RequirementsTabProps {
  requirements: RequirementItemRead[];
  onCreateRequirement: (data: { section_key: string; requirement_text: string }) => void;
  onUpdateRequirement: (id: string, data: { requirement_text?: string; status?: string }) => void;
}

export function RequirementsTab({ requirements, onCreateRequirement, onUpdateRequirement }: RequirementsTabProps) {
  const { t } = useTranslation("projects");
  const [reqSectionKey, setReqSectionKey] = useState("");
  const [reqText, setReqText] = useState("");
  const [editingReqId, setEditingReqId] = useState<string | null>(null);
  const [editingReqText, setEditingReqText] = useState("");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("requirements.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="req-section-key">{t("requirements.sectionKey")}</FieldLabel>
            <Input
              id="req-section-key"
              value={reqSectionKey}
              onChange={(e) => setReqSectionKey(e.target.value)}
              placeholder={t("requirements.sectionKeyPlaceholder")}
              className="max-w-[140px]"
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="req-text">{t("requirements.requirementText")}</FieldLabel>
            <Input
              id="req-text"
              value={reqText}
              onChange={(e) => setReqText(e.target.value)}
              placeholder={t("requirements.requirementTextPlaceholder")}
              className="flex-1 min-w-[200px]"
            />
          </Field>
          <Button
            size="sm"
            disabled={!reqText || !reqSectionKey}
            onClick={() => {
              onCreateRequirement({ section_key: reqSectionKey, requirement_text: reqText });
              setReqText("");
            }}
          >
            {t("requirements.add")}
          </Button>
        </FieldGroup>
        {requirements.length === 0 && (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><ClipboardCheckIcon /></EmptyMedia>
              <EmptyTitle>{t("requirements.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{t("requirements.emptyDesc")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
        <div className="flex flex-col gap-2">
          {requirements.map((r) => (
            <div key={r.id} className="border rounded-md p-3 flex flex-col gap-1">
              {editingReqId === r.id ? (
                <div className="flex gap-2">
                  <Input
                    value={editingReqText}
                    onChange={(e) => setEditingReqText(e.target.value)}
                    className="flex-1"
                  />
                  <Button size="sm" onClick={() => { onUpdateRequirement(r.id, { requirement_text: editingReqText }); setEditingReqId(null); }}>
                    {t("requirements.save")}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setEditingReqId(null)}>
                    {t("requirements.cancel")}
                  </Button>
                </div>
              ) : (
                <>
                  <p className="text-sm">{r.requirement_text}</p>
                  <div className="flex gap-2 text-xs text-muted-foreground">
                    <Badge variant="outline">{r.section_key}</Badge>
                    <Badge variant={r.priority === "high" ? "destructive" : r.priority === "normal" ? "secondary" : "default"}>
                      {t(`statusValues.${r.priority}`, { defaultValue: r.priority })}
                    </Badge>
                    <Badge variant={r.status === "confirmed" ? "default" : "secondary"}>
                      {t(`statusValues.${r.status}`, { defaultValue: r.status })}
                    </Badge>
                    <Button size="sm" variant="ghost" className="h-5 px-1 text-xs" onClick={() => { setEditingReqId(r.id); setEditingReqText(r.requirement_text); }}>
                      {t("requirements.edit")}
                    </Button>
                    {r.status !== "confirmed" && (
                      <Button size="sm" variant="ghost" className="h-5 px-1 text-xs" onClick={() => onUpdateRequirement(r.id, { status: "confirmed" })}>
                        {t("requirements.confirm")}
                      </Button>
                    )}
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
