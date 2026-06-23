import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ClipboardCheckIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { AuditEventRead } from "@/lib/api";

interface AuditTabProps {
  auditEvents: AuditEventRead[];
}

export function AuditTab({ auditEvents }: AuditTabProps) {
  const { t } = useTranslation("projects");
  const [expandedEvent, setExpandedEvent] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("audit.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {auditEvents.length === 0 ? (
          <Empty className="min-h-40">
            <EmptyHeader>
              <EmptyMedia variant="icon"><ClipboardCheckIcon /></EmptyMedia>
              <EmptyTitle>{t("audit.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{t("audit.emptyDesc")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ScrollArea className="max-h-[500px]">
            <div className="flex flex-col gap-3 pr-4">
              {auditEvents.map((e) => (
                <div key={e.id} className="border rounded-md p-3 flex flex-col gap-1">
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant="outline">{e.event_type}</Badge>
                    <span className="text-muted-foreground">{e.actor_id}</span>
                    <span className="text-muted-foreground ml-auto">
                      {new Date(e.created_at).toLocaleString()}
                    </span>
                  </div>
                  {e.payload && (
                    <button
                      className="text-left"
                      onClick={() => setExpandedEvent(expandedEvent === e.id ? null : e.id)}
                    >
                      <p className="text-xs text-muted-foreground font-mono bg-muted rounded p-2 mt-1 cursor-pointer hover:bg-muted/80 transition-colors">
                        {expandedEvent === e.id
                          ? JSON.stringify(e.payload, null, 2)
                          : JSON.stringify(e.payload).slice(0, 120) + (JSON.stringify(e.payload).length > 120 ? "..." : "")}
                      </p>
                      <span className="text-[10px] text-muted-foreground/60 ml-2">
                        {expandedEvent === e.id ? t("audit.collapse", { defaultValue: "Click to collapse" }) : t("audit.expand", { defaultValue: "Click to expand" })}
                      </span>
                    </button>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
