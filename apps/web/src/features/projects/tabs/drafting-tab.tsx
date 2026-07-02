import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { PromptInput, PromptInputTextarea, PromptInputActions, PromptInputAction } from "@/components/ui/prompt-input";
import { Source } from "@/components/ui/source";
import { Message, MessageAvatar, MessageContent, MessageActions, MessageAction } from "@/components/ui/message";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AlertTriangleIcon, RefreshCwIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import type { SectionVersionRead, DeliverableSectionRead, EvidenceRead } from "@/lib/api";

interface DraftingTabProps {
  projectId: string;
  sectionVersions: SectionVersionRead[] | undefined;
  sections: DeliverableSectionRead[] | undefined;
  selectedSectionId: string | null;
  evidence: EvidenceRead[] | undefined;
  onDraft: (sectionKey: string) => void;
  onRedraft: (sectionKey: string) => void;
  draftPending: boolean;
  redraftPending: boolean;
}

export function DraftingTab({
  sectionVersions,
  sections,
  selectedSectionId,
  evidence,
  onDraft,
  onRedraft,
  draftPending,
  redraftPending,
}: DraftingTabProps) {
  const { t } = useTranslation("projects");
  const [sectionKey, setSectionKey] = useState("");
  const [diffVersionA, setDiffVersionA] = useState<number | null>(null);
  const [diffVersionB, setDiffVersionB] = useState<number | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("drafting.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <PromptInput
          value={sectionKey}
          onValueChange={setSectionKey}
          onSubmit={() => { if (sectionKey) onDraft(sectionKey); }}
          isLoading={draftPending}
          className="max-w-xl"
        >
          <PromptInputTextarea placeholder={t("drafting.placeholder")} />
          <PromptInputActions>
            <PromptInputAction tooltip={t("drafting.generateDraft")}>
              <Button size="sm" disabled={!sectionKey || draftPending} onClick={() => onDraft(sectionKey)}>
                {draftPending && <Spinner data-icon="inline-start" />}
                {t("drafting.generate")}
              </Button>
            </PromptInputAction>
          </PromptInputActions>
        </PromptInput>

        {selectedSectionId && sectionVersions && sectionVersions.length > 0 && (
          <div className="flex flex-col gap-3">
            <Message>
              <MessageAvatar alt={t("drafting.aiAssistant")} fallback={t("drafting.aiFallback")} />
              <div className="flex flex-col gap-3 flex-1">
                <div className="flex gap-2 text-xs text-muted-foreground">
                  <span>{t("drafting.version", { number: sectionVersions[0].version_number })}</span>
                  <span>{t("drafting.by", { actor: sectionVersions[0].created_by_actor })}</span>
                </div>
                <MessageContent markdown variant="typora" className="flex-1">
                  {sectionVersions[0].content_markdown || ""}
                </MessageContent>
                <MessageActions>
                  <MessageAction tooltip={t("drafting.redraft")}>
                    <Button
                      size="sm"
                      variant="outline"
                      aria-label={t("drafting.redraft")}
                      disabled={redraftPending}
                      onClick={() => {
                        const section = sections?.find((s) => s.id === selectedSectionId);
                        if (section) onRedraft(section.section_key);
                      }}
                    >
                      {redraftPending && <Spinner data-icon="inline-start" />}
                      <RefreshCwIcon className="size-3.5" />
                    </Button>
                  </MessageAction>
                </MessageActions>

                {evidence?.filter((ev) => ev.quote_text).length ? (
                  <div className="flex flex-col gap-2">
                    <p className="text-xs font-medium text-muted-foreground">{t("drafting.evidence")}</p>
                    {evidence?.filter((ev) => ev.quote_text).slice(0, 5).map((ev) => (
                      <Source key={ev.id} href={`#evidence-${ev.id}`}>
                        <p className="text-xs">{ev.quote_text}</p>
                        <span className="text-[10px] text-muted-foreground">
                          {t("drafting.confidence", { value: ev.confidence?.toFixed(2) ?? t("common:notAvailable") })}
                        </span>
                      </Source>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center gap-2 rounded-md border border-dashed border-yellow-500/50 bg-yellow-500/5 px-3 py-2">
                    <AlertTriangleIcon className="size-4 text-yellow-600 shrink-0" />
                    <p className="text-xs text-yellow-700 dark:text-yellow-400">{t("drafting.noEvidence")}</p>
                  </div>
                )}

                {sectionVersions.length > 1 && (
                  <div className="flex flex-col gap-2">
                    <p className="text-xs font-medium text-muted-foreground">{t("drafting.versionHistory")}</p>
                    <div className="flex gap-2 text-xs">
                      {(() => {
                        const versionItems = sectionVersions.map((v) => ({
                          label: t("drafting.versionLabel", { number: v.version_number }),
                          value: v.version_number.toString(),
                        }));
                        return (
                          <>
                            <Select items={versionItems} value={diffVersionA?.toString() ?? ""} onValueChange={(v) => setDiffVersionA(v ? Number(v) : null)}>
                              <SelectTrigger size="sm" className="w-28"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectGroup>
                                  {versionItems.map((item) => (
                                    <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                                  ))}
                                </SelectGroup>
                              </SelectContent>
                            </Select>
                            <span className="self-center">{t("drafting.vs")}</span>
                            <Select items={versionItems} value={diffVersionB?.toString() ?? ""} onValueChange={(v) => setDiffVersionB(v ? Number(v) : null)}>
                              <SelectTrigger size="sm" className="w-28"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectGroup>
                                  {versionItems.map((item) => (
                                    <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                                  ))}
                                </SelectGroup>
                              </SelectContent>
                            </Select>
                          </>
                        );
                      })()}
                    </div>
                    {diffVersionA != null && diffVersionB != null && (
                      <ScrollArea className="h-48">
                        <div className="p-2 text-xs font-mono whitespace-pre-wrap">
                          {(() => {
                            const a = sectionVersions.find((v) => v.version_number === diffVersionA);
                            const b = sectionVersions.find((v) => v.version_number === diffVersionB);
                            if (!a || !b) return t("drafting.selectTwo");
                            const linesA = (a.content_markdown || "").split("\n");
                            const linesB = (b.content_markdown || "").split("\n");
                            const maxLen = Math.max(linesA.length, linesB.length);
                            const diff: string[] = [];
                            for (let i = 0; i < maxLen; i++) {
                              const la = linesA[i] ?? "";
                              const lb = linesB[i] ?? "";
                              if (la === lb) diff.push(`  ${la}`);
                              else { if (la) diff.push(`- ${la}`); if (lb) diff.push(`+ ${lb}`); }
                            }
                            return diff.join("\n") || t("drafting.noDifferences");
                          })()}
                        </div>
                      </ScrollArea>
                    )}
                  </div>
                )}
              </div>
            </Message>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
