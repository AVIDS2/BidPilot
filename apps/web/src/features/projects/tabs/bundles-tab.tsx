import { useState } from "react";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { FieldGroup, Field, FieldLabel } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, PackageIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  createBundle,
  reingestBundle,
  listDocuments,
  uploadDocument,
  getDocumentDownloadUrl,
  type BundleRead,
  type DocumentsPaginatedResponse,
} from "@/lib/api";

interface BundlesTabProps {
  projectId: string;
  bundles: BundleRead[];
  onReingest: (bundleId: string) => void;
  onConfirm: (action: { title: string; description: string; onConfirm: () => void }) => void;
}

export function BundlesTab({ projectId, bundles, onReingest, onConfirm }: BundlesTabProps) {
  const { t } = useTranslation(["projects", "common"]);
  const queryClient = useQueryClient();
  const [bundleLabel, setBundleLabel] = useState("");
  const [selectedBundleId, setSelectedBundleId] = useState<string | null>(null);
  const [docPage, setDocPage] = useState(1);
  const [docTotalPages, setDocTotalPages] = useState(0);
  const DOC_PAGE_SIZE = 20;

  const { data: documents } = useQuery<DocumentsPaginatedResponse>({
    queryKey: ["documents", selectedBundleId, docPage],
    queryFn: async () => {
      const result = await listDocuments(selectedBundleId!, docPage, DOC_PAGE_SIZE);
      setDocTotalPages(result.pages);
      return result;
    },
    enabled: !!selectedBundleId,
    staleTime: 30 * 1000,
  });

  const handleCreateBundle = () => {
    createBundle({ project_id: projectId, label: bundleLabel, source_type: "upload" })
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ["bundles", projectId] });
        toast.success(t("bundles.registered"));
        setBundleLabel("");
      })
      .catch(() => toast.error(t("bundles.registerFailed")));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("bundles.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="bundle-label">{t("bundles.label")}</FieldLabel>
            <Input
              id="bundle-label"
              value={bundleLabel}
              onChange={(e) => setBundleLabel(e.target.value)}
              placeholder={t("bundles.labelPlaceholder")}
              className="max-w-xs"
            />
          </Field>
          <Button size="sm" disabled={!bundleLabel} onClick={handleCreateBundle}>
            {t("bundles.register")}
          </Button>
        </FieldGroup>
        {bundles.length === 0 && (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><PackageIcon /></EmptyMedia>
              <EmptyTitle>{t("bundles.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{t("bundles.emptyDesc")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
        <Accordion
          multiple
          onValueChange={(v) => {
            const newId = v[v.length - 1] ?? null;
            if (newId !== selectedBundleId) setDocPage(1);
            setSelectedBundleId(newId);
          }}
        >
          {bundles.map((b) => (
            <AccordionItem key={b.id} value={b.id}>
              <AccordionTrigger className="hover:no-underline">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">{b.label}</span>
                  <Badge variant={b.ingest_status === "ingested" ? "default" : "secondary"}>
                    {t(`statusValues.${b.ingest_status}`, { defaultValue: b.ingest_status })}
                  </Badge>
                  {b.ingest_status !== "ingested" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation();
                        onConfirm({
                          title: t("bundles.reingestTitle"),
                          description: t("bundles.reingestDesc", { label: b.label }),
                          onConfirm: () => onReingest(b.id),
                        });
                      }}
                    >
                      {t("bundles.reingest")}
                    </Button>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="flex flex-col gap-2">
                  <Field>
                    <FieldLabel htmlFor={`file-upload-${b.id}`} className="text-xs">
                      {t("bundles.uploadDocument")}
                    </FieldLabel>
                    <Input
                      id={`file-upload-${b.id}`}
                      type="file"
                      className="cursor-pointer file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1 file:text-xs file:font-medium file:text-primary-foreground hover:file:bg-primary/90"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          uploadDocument(b.id, file)
                            .then(() => {
                              toast.success(t("bundles.uploaded", { filename: file.name }));
                              queryClient.invalidateQueries({ queryKey: ["documents", b.id] });
                            })
                            .catch((err) => {
                              const msg = err instanceof Error ? err.message : "Upload failed";
                              toast.error(t("bundles.uploadFailed", { message: msg }));
                            });
                        }
                      }}
                    />
                  </Field>
                  {documents?.items.map((d) => (
                    <div key={d.id} className="flex items-center gap-2 text-xs ml-2">
                      <a href={getDocumentDownloadUrl(d.id)} className="text-primary hover:underline">
                        {d.original_filename}
                      </a>
                      <Badge variant="outline">
                        {t(`statusValues.${d.parse_status}`, { defaultValue: d.parse_status })}
                      </Badge>
                    </div>
                  ))}
                  {documents?.items.length === 0 && (
                    <p className="text-xs text-muted-foreground ml-2">{t("bundles.noDocuments")}</p>
                  )}
                  {docTotalPages > 1 && (
                    <div className="flex items-center gap-2 mt-2">
                      <Button size="sm" variant="outline" disabled={docPage <= 1} onClick={() => setDocPage((p) => p - 1)}>
                        <ChevronLeft className="size-4" />
                      </Button>
                      <span className="text-sm text-muted-foreground">
                        {t("common:pagination.pageInfo", { page: docPage, totalPages: docTotalPages, total: documents?.total ?? 0 })}
                      </span>
                      <Button size="sm" variant="outline" disabled={docPage >= docTotalPages} onClick={() => setDocPage((p) => p + 1)}>
                        <ChevronRight className="size-4" />
                      </Button>
                    </div>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  );
}
