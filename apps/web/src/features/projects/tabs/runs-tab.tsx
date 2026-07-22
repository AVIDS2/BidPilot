import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ActivityIcon } from "lucide-react";
import type { ExecutionRunRead } from "@/lib/api";

interface RunsTabProps {
  runs: ExecutionRunRead[];
  onRetry: (runId: string) => void;
  retrying: boolean;
  onConfirm: (action: { title: string; description: string; onConfirm: () => void }) => void;
  t: (key: string, opts?: Record<string, unknown>) => string;
}

export function RunsTab({ runs, onRetry, retrying, onConfirm, t }: RunsTabProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("runs.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {runs.length === 0 && (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><ActivityIcon /></EmptyMedia>
              <EmptyTitle>{t("runs.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{t("runs.emptyDesc")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("runs.type")}</TableHead>
                <TableHead>{t("runs.status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.run_type}</TableCell>
                  <TableCell>
                    <Badge variant={r.status === "succeeded" ? "default" : r.status === "failed" ? "destructive" : "secondary"}>
                      {t(`statusValues.${r.status}`, { defaultValue: r.status })}
                    </Badge>
                    {r.status === "failed" && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="ml-2"
                        disabled={retrying}
                        onClick={() => onConfirm({
                          title: t("runs.retryTitle"),
                          description: t("runs.retryDesc", { runType: r.run_type }),
                          onConfirm: () => onRetry(r.id),
                        })}
                      >
                        {retrying && <Spinner data-icon="inline-start" />}
                        {t("runs.retry")}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
