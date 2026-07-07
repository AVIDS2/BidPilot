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
import {
  CheckCircle2Icon,
  ChevronLeft,
  ChevronRight,
  FileIcon,
  Loader2Icon,
  PackageIcon,
  UploadCloudIcon,
  XCircleIcon,
} from "lucide-react";
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
  onUploadComplete: (bundleId: string) => void;
  t: (key: string, opts?: Record<string, unknown>) => string;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadItems, setUploadItems] = useState<
    Array<{ id: string; name: string; progress: number; status: "uploading" | "done" | "failed"; error?: string }>
  >([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploading = uploadItems.some((item) => item.status === "uploading");

  const handleUploadFiles = useCallback(
    async (fileList: FileList | File[]) => {
      const files = Array.from(fileList);
      if (files.length === 0 || uploading) return;

      const items = files.map((file) => ({
        id: `${file.name}-${file.lastModified}-${file.size}`,
        name: file.name,
        progress: 0,
        status: "uploading" as const,
      }));
      setUploadItems(items);

      const results = await Promise.allSettled(
        files.map((file, index) =>
          uploadDocument(bundleId, file, (progress) => {
            setUploadItems((current) =>
              current.map((item, i) => (i === index ? { ...item, progress } : item)),
            );
          }),
        ),
      );

      let successCount = 0;
      setUploadItems((current) =>
        current.map((item, index) => {
          const result = results[index];
          if (result.status === "fulfilled") {
            successCount += 1;
            return { ...item, progress: 100, status: "done" };
          }
          return {
            ...item,
            status: "failed",
            error: result.reason instanceof Error ? result.reason.message : "Upload failed",
          };
        }),
      );

      if (successCount > 0) {
        toast.success(t("bundles.uploadedMany", { count: successCount, defaultValue: `Uploaded ${successCount} file(s)` }));
        onUploadComplete(bundleId);
      }
      if (successCount < files.length) {
        toast.error(t("bundles.uploadPartialFailed", { defaultValue: "Some files failed to upload." }));
      }

      window.setTimeout(() => {
        setUploadItems((current) => current.filter((item) => item.status === "failed"));
      }, 1800);
    },
    [bundleId, onUploadComplete, t, uploading],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files?.length) handleUploadFiles(e.dataTransfer.files);
    },
    [handleUploadFiles],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
      e.preventDefault();
      if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
        setIsDragging(false);
      }
    }, []);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files?.length) handleUploadFiles(e.target.files);
      e.target.value = "";
    },
    [handleUploadFiles],
  );

  return (
    <div className="space-y-3">
      <motion.div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !uploading && fileInputRef.current?.click()}
        animate={isDragging ? { scale: 1.01 } : { scale: 1 }}
        transition={{ duration: 0.2, ease: [0.32, 0.72, 0, 1] }}
        className={cn(
          "relative flex min-h-32 cursor-pointer flex-col items-center justify-center gap-3 overflow-hidden rounded-2xl border border-dashed p-6 text-center transition-colors duration-200",
          isDragging
            ? "border-primary bg-primary/10 shadow-[0_0_0_1px_color-mix(in_oklch,var(--primary)_26%,transparent)]"
            : "border-muted-foreground/25 bg-muted/20 hover:border-primary/45 hover:bg-muted/35",
          uploading && "cursor-wait",
        )}
      >
        <div
          className={cn(
            "absolute inset-0 -translate-x-full bg-[linear-gradient(110deg,transparent,rgba(255,255,255,.13),transparent)] transition-transform duration-700",
            isDragging && "translate-x-full",
          )}
        />
        <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileSelect} />
        <div className="relative flex size-12 items-center justify-center rounded-2xl border border-border bg-card shadow-sm">
          {uploading ? (
            <Loader2Icon className="size-5 animate-spin text-primary" />
          ) : (
            <UploadCloudIcon className={cn("size-5 transition-colors", isDragging ? "text-primary" : "text-muted-foreground")} />
          )}
        </div>
        <div className="relative space-y-1">
          <p className="text-sm font-medium text-foreground">
            {uploading
              ? t("bundles.uploading", { defaultValue: "Uploading..." })
              : isDragging
                ? t("bundles.dropHere", { defaultValue: "Drop files to upload" })
                : t("bundles.dragOrClick", { defaultValue: "Drag files here, or click to browse" })}
          </p>
          <p className="text-xs text-muted-foreground">
            {t("bundles.uploadHint", { defaultValue: "PDF, DOCX, XLSX, PNG and JPG are supported." })}
          </p>
        </div>
      </motion.div>

      <AnimatePresence>
        {uploadItems.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="space-y-2 rounded-xl border bg-card/70 p-3"
          >
            {uploadItems.map((item) => (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -8 }}
                className="space-y-2"
              >
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="min-w-0 truncate font-medium">{item.name}</span>
                  <span className="flex shrink-0 items-center gap-1 text-muted-foreground">
                    {item.status === "done" && <CheckCircle2Icon className="size-3.5 text-primary" />}
                    {item.status === "failed" && <XCircleIcon className="size-3.5 text-destructive" />}
                    {item.status === "uploading" ? `${item.progress}%` : t(`bundles.uploadStatus.${item.status}`, { defaultValue: item.status })}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <motion.div
                    className={cn("h-full rounded-full", item.status === "failed" ? "bg-destructive" : "bg-primary")}
                    initial={{ width: 0 }}
                    animate={{ width: `${item.status === "failed" ? 100 : item.progress}%` }}
                    transition={{ duration: 0.25 }}
                  />
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
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

  const invalidateDocuments = useCallback((bundleId: string) => {
    queryClient.invalidateQueries({ queryKey: ["documents", bundleId] });
    queryClient.invalidateQueries({ queryKey: ["bundles", projectId] });
  }, [projectId, queryClient]);

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
                  <DragDropUpload bundleId={b.id} onUploadComplete={invalidateDocuments} t={t} />

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
