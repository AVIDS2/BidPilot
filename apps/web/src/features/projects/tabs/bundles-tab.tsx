import { useState, useCallback, useRef } from "react";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { FieldGroup, Field, FieldLabel } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { toast } from "sonner";
import { motion, AnimatePresence } from "motion/react";
import { ChevronLeft, ChevronRight, PackageIcon, UploadIcon, FileIcon, Loader2Icon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import {
  createBundle,
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

// Drag-and-drop upload zone component
function DragDropUpload({
  bundleId,
  onUploadComplete,
  t,
}: {
  bundleId: string;
  onUploadComplete: () => void;
  t: (key: string, opts?: Record<string, unknown>) => string;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        await uploadDocument(bundleId, file);
        toast.success(t("bundles.uploaded", { filename: file.name }));
        onUploadComplete();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        toast.error(t("bundles.uploadFailed", { message: msg }));
      } finally {
        setUploading(false);
      }
    },
    [bundleId, onUploadComplete, t]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleUpload(file);
    },
    [handleUpload]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleUpload(file);
    },
    [handleUpload]
  );

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={() => fileInputRef.current?.click()}
      className={cn(
        "relative flex flex-col items-center justify-center gap-2 p-6 rounded-lg border-2 border-dashed cursor-pointer transition-all duration-200",
        isDragging
          ? "border-primary bg-primary/5 scale-[1.01]"
          : "border-muted-foreground/20 hover:border-primary/40 hover:bg-muted/30",
        uploading && "pointer-events-none opacity-60"
      )}
    >
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={handleFileSelect}
      />
      {uploading ? (
        <Loader2Icon className="size-6 text-muted-foreground animate-spin" />
      ) : (
        <UploadIcon className={cn("size-6 transition-colors", isDragging ? "text-primary" : "text-muted-foreground")} />
      )}
      <p className="text-sm text-muted-foreground">
        {uploading ? t("bundles.uploading") : isDragging ? t("bundles.dropHere", { defaultValue: "释放文件开始上传" }) : t("bundles.dragOrClick", { defaultValue: "拖拽文件到此处，或点击选择" })}
      </p>
    </div>
  );
}

// Document list item with animated entry
function DocumentItem({ doc, index }: { doc: { id: string; original_filename: string; parse_status: string }; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.04, ease: [0.32, 0.72, 0, 1] }}
      className="flex items-center gap-2 text-xs"
    >
      <FileIcon className="size-3 text-muted-foreground shrink-0" />
      <a href={getDocumentDownloadUrl(doc.id)} className="text-primary hover:underline truncate">
        {doc.original_filename}
      </a>
      <Badge variant="outline" className="shrink-0 text-[10px]">
        {doc.parse_status}
      </Badge>
    </motion.div>
  );
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

  const invalidateDocuments = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["documents", selectedBundleId] });
  }, [queryClient, selectedBundleId]);

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
                <div className="flex flex-col gap-3">
                  {/* Drag-and-drop upload zone */}
                  <DragDropUpload
                    bundleId={b.id}
                    onUploadComplete={invalidateDocuments}
                    t={t}
                  />

                  {/* Document list */}
                  <AnimatePresence>
                    {documents?.items.map((d, i) => (
                      <DocumentItem key={d.id} doc={d} index={i} />
                    ))}
                  </AnimatePresence>
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
