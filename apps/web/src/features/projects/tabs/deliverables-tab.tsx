import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { FieldGroup, Field, FieldLabel } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { cn } from "@/lib/utils";
import { LayersIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { DeliverableRead, DeliverableSectionRead } from "@/lib/api";

interface DeliverablesTabProps {
  projectId: string;
  deliverables: DeliverableRead[];
  sections: DeliverableSectionRead[] | undefined;
  selectedSectionId: string | null;
  onSelectSection: (id: string | null) => void;
  onCreateDeliverable: (title: string) => void;
}

export function DeliverablesTab({
  deliverables,
  sections,
  selectedSectionId,
  onSelectSection,
  onCreateDeliverable,
}: DeliverablesTabProps) {
  const { t } = useTranslation("projects");
  const [deliverableTitle, setDeliverableTitle] = useState("");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("deliverables.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="deliverable-title">{t("deliverables.label")}</FieldLabel>
            <Input
              id="deliverable-title"
              value={deliverableTitle}
              onChange={(e) => setDeliverableTitle(e.target.value)}
              placeholder={t("deliverables.labelPlaceholder")}
              className="max-w-xs"
            />
          </Field>
          <Button
            size="sm"
            disabled={!deliverableTitle}
            onClick={() => {
              onCreateDeliverable(deliverableTitle);
              setDeliverableTitle("");
            }}
          >
            {t("deliverables.add")}
          </Button>
        </FieldGroup>
        {deliverables.length === 0 && (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><LayersIcon /></EmptyMedia>
              <EmptyTitle>{t("deliverables.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{t("deliverables.emptyDesc")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
        <Accordion multiple>
          {deliverables.map((d) => (
            <AccordionItem key={d.id} value={d.id}>
              <AccordionTrigger className="hover:no-underline">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">{d.title}</span>
                  <Badge variant="outline">{d.type}</Badge>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                {sections?.map((s) => (
                  <div
                    key={s.id}
                    role="button"
                    tabIndex={0}
                    aria-pressed={selectedSectionId === s.id}
                    className={cn(
                      "flex items-center gap-2 text-sm cursor-pointer rounded p-1",
                      selectedSectionId === s.id ? "bg-accent" : "hover:bg-accent",
                    )}
                    onClick={() => onSelectSection(s.id === selectedSectionId ? null : s.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onSelectSection(s.id === selectedSectionId ? null : s.id);
                      }
                    }}
                  >
                    <span>{s.title}</span>
                    <Badge variant={s.status === "draft" ? "secondary" : "default"}>
                      {t(`statusValues.${s.status}`, { defaultValue: s.status })}
                    </Badge>
                  </div>
                ))}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  );
}
