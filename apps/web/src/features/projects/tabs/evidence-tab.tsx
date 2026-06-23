import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Source } from "@/components/ui/source";
import { FileIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { EvidenceRead, KnowledgeChunkRead } from "@/lib/api";

interface EvidenceTabProps {
  evidence: EvidenceRead[];
  knowledgeChunks: KnowledgeChunkRead[];
}

export function EvidenceTab({ evidence, knowledgeChunks }: EvidenceTabProps) {
  const { t } = useTranslation("projects");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("evidence.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {evidence.length === 0 && knowledgeChunks.length === 0 && (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><FileIcon /></EmptyMedia>
              <EmptyTitle>{t("evidence.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{t("evidence.emptyDesc")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
        {evidence.length > 0 && (
          <div className="flex flex-col gap-3 mb-6">
            <h3 className="text-sm font-semibold">{t("evidence.citationEvidence")}</h3>
            {evidence.map((e) => (
              <Source key={e.id} href={`#evidence-${e.id}`}>
                <p className="text-sm">{e.quote_text}</p>
                <div className="flex gap-2 text-xs text-muted-foreground">
                  <span>{t("evidence.confidence", { value: e.confidence?.toFixed(2) ?? t("common:notAvailable") })}</span>
                </div>
              </Source>
            ))}
          </div>
        )}
        {knowledgeChunks.length > 0 && (
          <div className="flex flex-col gap-3">
            <h3 className="text-sm font-semibold">{t("evidence.knowledgeChunks", { count: knowledgeChunks.length })}</h3>
            <ScrollArea className="h-96">
              <div className="flex flex-col gap-2">
                {knowledgeChunks.map((chunk) => (
                  <div key={chunk.id} className="rounded-md border p-3 text-sm">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                      <FileIcon className="size-3" />
                      <span>{t("evidence.chunkLabel", { index: chunk.chunk_index })}</span>
                    </div>
                    <p className="text-xs whitespace-pre-wrap line-clamp-4">{chunk.content}</p>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
