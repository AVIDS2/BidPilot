import { useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { Field, FieldLabel } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Markdown } from "@/components/ui/markdown";
import { cn } from "@/lib/utils";
import { CheckCircle2Icon, FileTextIcon, GripVerticalIcon, MessageCircleIcon, XCircleIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { DeliverableSectionRead, ReviewThreadRead, ReviewCommentRead, SectionVersionRead } from "@/lib/api";

interface ReviewTabProps {
  sections: DeliverableSectionRead[] | undefined;
  sectionVersions: SectionVersionRead[] | undefined;
  reviewThreads: ReviewThreadRead[] | undefined;
  reviewComments: ReviewCommentRead[] | undefined;
  selectedSectionId: string | null;
  selectedThreadId: string | null;
  onSelectSection: (id: string) => void;
  onSelectThread: (id: string | null) => void;
  onAddComment: (threadId: string, body: string) => void;
  onSubmitDecision: (sectionId: string, decision: string, comment: string | null) => void;
  addCommentPending: boolean;
  submitDecisionPending: boolean;
}

function getInitials(value: string) {
  return value
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "U";
}

export function ReviewTab({
  sections,
  sectionVersions,
  reviewThreads,
  reviewComments,
  selectedSectionId,
  selectedThreadId,
  onSelectSection,
  onSelectThread,
  onAddComment,
  onSubmitDecision,
  addCommentPending,
  submitDecisionPending,
}: ReviewTabProps) {
  const { t } = useTranslation("projects");
  const [reviewCommentBody, setReviewCommentBody] = useState("");
  const [reviewDecisionComment, setReviewDecisionComment] = useState("");
  const [leftPane, setLeftPane] = useState(56);
  const shellRef = useRef<HTMLDivElement>(null);

  const selectedSection = useMemo(
    () => sections?.find((section) => section.id === selectedSectionId) ?? null,
    [sections, selectedSectionId],
  );

  const latestVersion = useMemo(
    () =>
      [...(sectionVersions ?? [])].sort(
        (a, b) => b.version_number - a.version_number,
      )[0] ?? null,
    [sectionVersions],
  );

  const selectedThread = useMemo(
    () => reviewThreads?.find((thread) => thread.id === selectedThreadId) ?? null,
    [reviewThreads, selectedThreadId],
  );

  const startResize = (event: React.PointerEvent<HTMLButtonElement>) => {
    const shell = shellRef.current;
    if (!shell) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const bounds = shell.getBoundingClientRect();

    const handleMove = (moveEvent: PointerEvent) => {
      const next = ((moveEvent.clientX - bounds.left) / bounds.width) * 100;
      setLeftPane(Math.min(68, Math.max(38, next)));
    };

    const handleUp = () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp, { once: true });
  };

  return (
    <div
      ref={shellRef}
      className="grid min-h-[34rem] grid-cols-1 gap-4 lg:grid-cols-[var(--review-left)_0.75rem_1fr]"
      style={{ "--review-left": `${leftPane}%` } as React.CSSProperties}
    >
      <Card className="min-w-0 overflow-hidden">
        <CardHeader className="gap-3 border-b">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle className="text-lg">{t("review.draftPreview")}</CardTitle>
              <p className="text-sm text-muted-foreground">{t("review.draftPreviewDesc")}</p>
            </div>
            {selectedSection && (
              <Badge variant={selectedSection.status === "approved" ? "default" : "secondary"}>
                {t(`statusValues.${selectedSection.status}`, { defaultValue: selectedSection.status })}
              </Badge>
            )}
          </div>
          <Field>
            <FieldLabel>{t("review.section")}</FieldLabel>
            <Select
              value={selectedSectionId ?? ""}
              onValueChange={(value) => {
                onSelectSection(value);
                onSelectThread(null);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder={t("review.selectSection")} />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {sections?.map((section) => (
                    <SelectItem key={section.id} value={section.id}>
                      {section.title || section.section_key}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
        </CardHeader>
        <CardContent className="p-0">
          {!selectedSection ? (
            <Empty className="min-h-96">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FileTextIcon />
                </EmptyMedia>
                <EmptyTitle>{t("review.noSectionSelected")}</EmptyTitle>
                <EmptyDescription>{t("review.noSectionDesc")}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <ScrollArea className="h-[34rem]">
              <div className="space-y-4 p-5">
                <div className="rounded-2xl border bg-muted/20 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                        {selectedSection.section_key}
                      </p>
                      <h3 className="mt-2 break-words text-xl font-semibold">
                        {selectedSection.title || selectedSection.section_key}
                      </h3>
                    </div>
                    {latestVersion && (
                      <Badge variant="outline">
                        {t("drafting.versionLabel", { number: latestVersion.version_number })}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-4 grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
                    <span>{t("review.assignee")}: {selectedSection.assignee_type || "-"}</span>
                    <span>{t("review.threadsCount", { count: reviewThreads?.length ?? 0 })}</span>
                    <span>{latestVersion ? t("review.generatedBy", { actor: latestVersion.created_by_actor }) : t("review.noDraftYet")}</span>
                  </div>
                </div>

                {latestVersion?.content_markdown ? (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.24, ease: [0.32, 0.72, 0, 1] }}
                  >
                    <Markdown variant="typora">
                      {latestVersion.content_markdown}
                    </Markdown>
                  </motion.div>
                ) : (
                  <Empty className="min-h-72 rounded-2xl border bg-muted/20">
                    <EmptyHeader>
                      <EmptyMedia variant="icon">
                        <FileTextIcon />
                      </EmptyMedia>
                      <EmptyTitle>{t("review.noDraftYet")}</EmptyTitle>
                      <EmptyDescription>{t("review.noDraftDesc")}</EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                )}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

      <button
        type="button"
        aria-label={t("review.resizePane")}
        onPointerDown={startResize}
        className="hidden cursor-col-resize items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground lg:flex"
      >
        <GripVerticalIcon className="size-4" />
      </button>

      <Card className="min-w-0 overflow-hidden">
        <CardHeader className="border-b">
          <CardTitle className="text-lg">{t("review.comments")}</CardTitle>
          <p className="text-sm text-muted-foreground">{t("review.commentsDesc")}</p>
        </CardHeader>
        <CardContent className="grid h-[34rem] grid-rows-[auto_1fr_auto] gap-4 p-5">
          <div className="space-y-2">
            {reviewThreads?.length === 0 && (
              <Empty className="min-h-28 rounded-xl border bg-muted/20">
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <MessageCircleIcon />
                  </EmptyMedia>
                  <EmptyTitle>{t("review.emptyTitle")}</EmptyTitle>
                  <EmptyDescription>{t("review.emptyDesc")}</EmptyDescription>
                </EmptyHeader>
              </Empty>
            )}
            {reviewThreads?.map((thread) => (
              <button
                key={thread.id}
                className={cn(
                  "flex w-full items-center justify-between rounded-xl border p-3 text-left text-sm transition-all hover:bg-accent",
                  selectedThreadId === thread.id && "border-primary bg-accent shadow-sm",
                )}
                onClick={() => onSelectThread(thread.id)}
              >
                <span className="font-medium">{t("review.thread", { id: thread.id.slice(0, 8) })}</span>
                <Badge variant={thread.status === "resolved" ? "default" : "secondary"}>
                  {t(`statusValues.${thread.status}`, { defaultValue: thread.status })}
                </Badge>
              </button>
            ))}
          </div>

          {!selectedThreadId ? (
            <Empty className="min-h-52 rounded-2xl border bg-muted/20">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <MessageCircleIcon />
                </EmptyMedia>
                <EmptyTitle>{t("review.noThreadSelected")}</EmptyTitle>
                <EmptyDescription>{t("review.noThreadDesc")}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <ScrollArea className="min-h-0">
              <div className="flex flex-col gap-3 pr-4">
                {selectedThread && (
                  <div className="rounded-xl border bg-muted/20 p-3 text-xs text-muted-foreground">
                    {t("review.selectedThread", { id: selectedThread.id.slice(0, 8), status: selectedThread.status })}
                  </div>
                )}
                {reviewComments?.map((comment, index) => (
                  <motion.div
                    key={comment.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.22, delay: index * 0.035 }}
                    className="rounded-2xl border bg-card p-3"
                  >
                    <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="flex size-7 items-center justify-center rounded-full bg-muted font-semibold text-foreground">
                        {getInitials(comment.author_id || comment.author_type)}
                      </span>
                      <Badge variant={comment.author_type === "ai" ? "secondary" : "default"}>
                        {comment.author_type}
                      </Badge>
                      <span className="truncate">{comment.author_id}</span>
                      <span className="ml-auto shrink-0">{new Date(comment.created_at).toLocaleString()}</span>
                    </div>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">{comment.body}</p>
                  </motion.div>
                ))}
                {reviewComments?.length === 0 && (
                  <Empty className="min-h-32">
                    <EmptyHeader>
                      <EmptyMedia variant="icon">
                        <MessageCircleIcon />
                      </EmptyMedia>
                      <EmptyTitle>{t("review.noComments")}</EmptyTitle>
                      <EmptyDescription>{t("review.noCommentsDesc")}</EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                )}
              </div>
            </ScrollArea>
          )}

          <div className="space-y-3 border-t pt-4">
            {selectedThreadId && (
              <div className="flex gap-2">
                <Input
                  value={reviewCommentBody}
                  onChange={(event) => setReviewCommentBody(event.target.value)}
                  placeholder={t("review.addComment")}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && reviewCommentBody.trim() && !addCommentPending) {
                      onAddComment(selectedThreadId, reviewCommentBody.trim());
                      setReviewCommentBody("");
                    }
                  }}
                />
                <Button
                  size="sm"
                  disabled={!reviewCommentBody.trim() || addCommentPending}
                  onClick={() => {
                    onAddComment(selectedThreadId, reviewCommentBody.trim());
                    setReviewCommentBody("");
                  }}
                >
                  {addCommentPending && <Spinner data-icon="inline-start" />}
                  {t("review.send")}
                </Button>
              </div>
            )}

            {selectedSectionId && (
              <div className="rounded-2xl border bg-muted/20 p-3">
                <p className="mb-2 text-xs font-medium text-muted-foreground">{t("review.submitDecision")}</p>
                <div className="flex flex-col gap-2">
                  <Input
                    value={reviewDecisionComment}
                    onChange={(event) => setReviewDecisionComment(event.target.value)}
                    placeholder={t("review.commentPlaceholder")}
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      disabled={submitDecisionPending}
                      onClick={() => onSubmitDecision(selectedSectionId, "approved", reviewDecisionComment || null)}
                    >
                      {submitDecisionPending && <Spinner data-icon="inline-start" />}
                      <CheckCircle2Icon />
                      {t("review.approve")}
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={submitDecisionPending}
                      onClick={() => onSubmitDecision(selectedSectionId, "rejected", reviewDecisionComment || null)}
                    >
                      {submitDecisionPending && <Spinner data-icon="inline-start" />}
                      <XCircleIcon />
                      {t("review.reject")}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
