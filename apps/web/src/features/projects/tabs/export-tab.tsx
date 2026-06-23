import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { DownloadIcon } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { exportDeliverableDocx, exportDeliverablePdf, type DeliverableRead } from "@/lib/api";

interface ExportTabProps {
  deliverables: DeliverableRead[];
}

export function ExportTab({ deliverables }: ExportTabProps) {
  const { t } = useTranslation("projects");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("export.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {deliverables.length === 0 ? (
          <Empty className="min-h-40">
            <EmptyHeader>
              <EmptyMedia variant="icon"><DownloadIcon /></EmptyMedia>
              <EmptyTitle>{t("export.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{t("export.emptyDesc")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          deliverables.map((d) => (
            <div key={d.id} className="flex items-center justify-between border rounded-md p-4">
              <div>
                <p className="font-medium">{d.title}</p>
                <p className="text-xs text-muted-foreground">
                  {d.type} &middot; {t(`statusValues.${d.status}`, { defaultValue: d.status })}
                  {d.export_status && d.export_status !== "none" && ` · ${t("export.statusLabel", { status: t(`statusValues.${d.export_status}`, { defaultValue: d.export_status }) })}`}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={d.status !== "approved"}
                  onClick={async () => {
                    try { await exportDeliverableDocx(d.id); toast.success(t("export.docxStarted")); }
                    catch { toast.error(t("export.docxFailed")); }
                  }}
                >
                  {t("export.exportDocx")}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={d.status !== "approved"}
                  onClick={async () => {
                    try { await exportDeliverablePdf(d.id); toast.success(t("export.pdfStarted")); }
                    catch { toast.error(t("export.pdfFailed")); }
                  }}
                >
                  {t("export.exportPdf")}
                </Button>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
