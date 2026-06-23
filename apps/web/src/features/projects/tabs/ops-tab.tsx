import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { RuntimeSummaryCards } from "@/features/ops/runtime-summary";
import { ActivityIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ExecutionRunRead, RuntimeSummary } from "@/lib/api";

interface OpsTabProps {
  runs: ExecutionRunRead[];
  ops: RuntimeSummary | undefined;
}

export function OpsTab({ runs, ops }: OpsTabProps) {
  const { t } = useTranslation("projects");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <RuntimeSummaryCards summary={ops} />
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t("system.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {runs.length === 0 ? (
            <Empty className="min-h-40">
              <EmptyHeader>
                <EmptyMedia variant="icon"><ActivityIcon /></EmptyMedia>
                <EmptyTitle>{t("system.emptyTitle")}</EmptyTitle>
                <EmptyDescription>{t("system.emptyDesc")}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <ScrollArea className="max-h-80">
              <div className="flex flex-col gap-2 pr-4">
                {runs.map((r) => (
                  <div key={r.id} className="border rounded-md p-3 text-sm">
                    <div className="flex items-center justify-between mb-1">
                      <Badge variant="outline">{r.run_type}</Badge>
                      <Badge variant={r.status === "succeeded" ? "default" : r.status === "failed" ? "destructive" : "secondary"}>
                        {t(`statusValues.${r.status}`, { defaultValue: r.status })}
                      </Badge>
                    </div>
                    {r.input_json && (
                      <p className="text-xs text-muted-foreground font-mono bg-muted rounded p-1.5 mt-1 line-clamp-2">
                        {t("system.input")} {JSON.stringify(r.input_json)}
                      </p>
                    )}
                    {r.output_json && (
                      <p className="text-xs text-muted-foreground font-mono bg-muted rounded p-1.5 mt-1 line-clamp-2">
                        {t("system.output")} {JSON.stringify(r.output_json)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
