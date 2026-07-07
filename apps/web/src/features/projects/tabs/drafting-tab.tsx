import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { PromptInput, PromptInputTextarea, PromptInputActions, PromptInputAction } from "@/components/ui/prompt-input";
import { Source } from "@/components/ui/source";
import { Message, MessageAvatar, MessageContent, MessageActions, MessageAction } from "@/components/ui/message";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { AlertTriangleIcon, RefreshCwIcon, GitCompareIcon } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
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

// Diff line component with color coding
function DiffLine({ type, text }: { type: "same" | "added" | "removed"; text: string }) {
  const colors = {
    same: "text-muted-foreground",
    added: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/5",
    removed: "text-red-600 dark:text-red-400 bg-red-500/5",
  };
  const prefixes = { same: "  ", added: "+ ", removed: "- " };

  return (
    <div className={`px-2 py-0.5 font-mono text-xs ${colors[type]}`}>
      <span className="select-none opacity-50">{prefixes[type]}</span>
      {text || " "}
    </div>
  );
}

// Version diff viewer with syntax-highlighted lines
function VersionDiff({
  versionA,
  versionB,
  contentA,
  contentB,
  emptyText,
}: {
  versionA: number;
  versionB: number;
  contentA: string;
  contentB: string;
  emptyText: string;
}) {
  const diffLines = useMemo(() => {
    const linesA = contentA.split("\n");
    const linesB = contentB.split("\n");
    const maxLen = Math.max(linesA.length, linesB.length);
    const result: Array<{ type: "same" | "added" | "removed"; text: string }> = [];

    for (let i = 0; i < maxLen; i++) {
      const la = linesA[i] ?? "";
      const lb = linesB[i] ?? "";
      if (la === lb) {
        result.push({ type: "same", text: la });
      } else {
        if (la) result.push({ type: "removed", text: la });
        if (lb) result.push({ type: "added", text: lb });
      }
    }
    return result;
  }, [contentA, contentB]);

  if (diffLines.every((l) => l.type === "same")) {
    return <p className="text-xs text-muted-foreground p-4 text-center">{emptyText}</p>;
  }

  return (
    <ScrollArea className="h-56 rounded-md border border-border">
      <div className="flex flex-col">
        {/* Diff header */}
        <div className="sticky top-0 flex items-center justify-between border-b border-border bg-muted/50 px-3 py-1.5 text-xs">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-red-500">v{versionA}</Badge>
            <GitCompareIcon className="size-3 text-muted-foreground" />
            <Badge variant="outline" className="text-emerald-500">v{versionB}</Badge>
          </div>
          <span className="text-muted-foreground">
            {diffLines.filter((l) => l.type === "added").length} added ·{" "}
            {diffLines.filter((l) => l.type === "removed").length} removed
          </span>
        </div>
        {/* Diff body */}
        <AnimatePresence mode="wait">
          <motion.div
            key={`${versionA}-${versionB}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
          >
            {diffLines.map((line, i) => (
              <DiffLine key={i} type={line.type} text={line.text} />
            ))}
          </motion.div>
        </AnimatePresence>
      </div>
    </ScrollArea>
  );
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
  const [showDiff, setShowDiff] = useState(false);

  const versionItems = useMemo(() =>
    (sectionVersions ?? []).map((v) => ({
      value: v.version_number.toString(),
      label: `v${v.version_number}`,
    })),
    [sectionVersions]
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("drafting.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {/* Draft input */}
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

        {/* Draft result with animated entry */}
        <AnimatePresence mode="wait">
          {selectedSectionId && sectionVersions && sectionVersions.length > 0 && (
            <motion.div
              key={selectedSectionId}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
              className="flex flex-col gap-3"
            >
              <Message>
                <MessageAvatar alt={t("drafting.aiAssistant")} fallback={t("drafting.aiFallback")} />
                <div className="flex flex-col gap-3 flex-1">
                  {/* Version meta */}
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="secondary" className="text-xs">
                      {t("drafting.version", { number: sectionVersions[0].version_number })}
                    </Badge>
                    <span>{t("drafting.by", { actor: sectionVersions[0].created_by_actor })}</span>
                  </div>

                  {/* Content */}
                  <MessageContent markdown variant="typora" className="flex-1">
                    {sectionVersions[0].content_markdown || ""}
                  </MessageContent>

                  {/* Actions */}
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
                    {sectionVersions.length > 1 && (
                      <MessageAction tooltip={t("drafting.compareVersions", { defaultValue: "Compare versions" })}>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={t("drafting.compareVersions", { defaultValue: "Compare versions" })}
                          onClick={() => setShowDiff(!showDiff)}
                        >
                          <GitCompareIcon className="size-3.5" />
                        </Button>
                      </MessageAction>
                    )}
                  </MessageActions>

                  {/* Evidence links */}
                  {evidence?.filter((ev) => ev.quote_text).length ? (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.15 }}
                      className="flex flex-col gap-2"
                    >
                      <p className="text-xs font-medium text-muted-foreground">{t("drafting.evidence")}</p>
                      {evidence?.filter((ev) => ev.quote_text).slice(0, 5).map((ev, i) => (
                        <motion.div
                          key={ev.id}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.2 + i * 0.05 }}
                        >
                          <Source href={`#evidence-${ev.id}`}>
                            <p className="text-xs">{ev.quote_text}</p>
                            <span className="text-[10px] text-muted-foreground">
                              {t("drafting.confidence", { value: ev.confidence?.toFixed(2) ?? t("common:notAvailable") })}
                            </span>
                          </Source>
                        </motion.div>
                      ))}
                    </motion.div>
                  ) : (
                    <div className="flex items-center gap-2 rounded-md border border-dashed border-yellow-500/50 bg-yellow-500/5 px-3 py-2">
                      <AlertTriangleIcon className="size-4 text-yellow-500" />
                      <p className="text-xs text-yellow-600 dark:text-yellow-500">
                        {t("drafting.missingEvidence", { defaultValue: "No evidence linked — claims may not be verified." })}
                      </p>
                    </div>
                  )}

                  {/* Version diff — collapsible */}
                  <AnimatePresence>
                    {showDiff && sectionVersions.length > 1 && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.3, ease: [0.32, 0.72, 0, 1] }}
                        className="flex flex-col gap-2 overflow-hidden"
                      >
                        <p className="text-xs font-medium text-muted-foreground">{t("drafting.versionCompare", { defaultValue: "Version comparison" })}</p>
                        <div className="flex items-center gap-2 flex-wrap">
                          {(() => {
                            if (versionItems.length < 2) return null;
                            const defaultA = diffVersionA ?? Number(versionItems[0].value);
                            const defaultB = diffVersionB ?? Number(versionItems[versionItems.length - 1].value);
                            return (
                              <>
                                <Select
                                  items={versionItems}
                                  value={(diffVersionA ?? defaultA).toString()}
                                  onValueChange={(v) => setDiffVersionA(v ? Number(v) : null)}
                                >
                                  <SelectTrigger size="sm" className="w-28"><SelectValue /></SelectTrigger>
                                  <SelectContent>
                                    <SelectGroup>
                                      {versionItems.map((item) => (
                                        <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                                      ))}
                                    </SelectGroup>
                                  </SelectContent>
                                </Select>
                                <span className="self-center text-xs text-muted-foreground">{t("drafting.vs")}</span>
                                <Select
                                  items={versionItems}
                                  value={(diffVersionB ?? defaultB).toString()}
                                  onValueChange={(v) => setDiffVersionB(v ? Number(v) : null)}
                                >
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
                        {diffVersionA != null && diffVersionB != null && (() => {
                          const a = sectionVersions?.find((v) => v.version_number === diffVersionA);
                          const b = sectionVersions?.find((v) => v.version_number === diffVersionB);
                          if (!a || !b) return <p className="text-xs text-muted-foreground p-2">{t("drafting.selectTwo")}</p>;
                          return (
                            <VersionDiff
                              versionA={diffVersionA}
                              versionB={diffVersionB}
                              contentA={a.content_markdown || ""}
                              contentB={b.content_markdown || ""}
                              emptyText={t("drafting.noDifferences")}
                            />
                          );
                        })()}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </Message>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}
