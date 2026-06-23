import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { Field, FieldLabel } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { MessageCircleIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { DeliverableSectionRead, ReviewThreadRead, ReviewCommentRead } from "@/lib/api";

interface ReviewTabProps {
  sections: DeliverableSectionRead[] | undefined;
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

export function ReviewTab({
  sections,
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t("review.title")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field>
            <FieldLabel>{t("review.section")}</FieldLabel>
            <Select
              value={selectedSectionId ?? ""}
              onValueChange={(v) => { onSelectSection(v); onSelectThread(null); }}
            >
              <SelectTrigger><SelectValue placeholder={t("review.selectSection")} /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {sections?.map((s) => (
                    <SelectItem key={s.id} value={s.id}>{s.title || s.section_key}</SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>

          {reviewThreads?.length === 0 && (
            <Empty className="min-h-32">
              <EmptyHeader>
                <EmptyMedia variant="icon"><MessageCircleIcon /></EmptyMedia>
                <EmptyTitle>{t("review.emptyTitle")}</EmptyTitle>
                <EmptyDescription>{t("review.emptyDesc")}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
          {reviewThreads?.map((thread) => (
            <button
              key={thread.id}
              className={cn(
                "flex items-center justify-between rounded-md border p-3 text-left text-sm hover:bg-accent transition-colors",
                selectedThreadId === thread.id && "border-primary bg-accent"
              )}
              onClick={() => onSelectThread(thread.id)}
            >
              <span className="font-medium">{t("review.thread", { id: thread.id.slice(0, 8) })}</span>
              <Badge variant={thread.status === "resolved" ? "default" : "secondary"}>
                {t(`statusValues.${thread.status}`, { defaultValue: thread.status })}
              </Badge>
            </button>
          ))}

          {selectedSectionId && (
            <div className="flex flex-col gap-2 pt-2 border-t">
              <p className="text-xs font-medium text-muted-foreground">{t("review.submitDecision")}</p>
              <Input
                value={reviewDecisionComment}
                onChange={(e) => setReviewDecisionComment(e.target.value)}
                placeholder={t("review.commentPlaceholder")}
              />
              <div className="flex gap-2">
                <Button size="sm" disabled={submitDecisionPending} onClick={() => onSubmitDecision(selectedSectionId, "approved", reviewDecisionComment || null)}>
                  {submitDecisionPending && <Spinner data-icon="inline-start" />}
                  {t("review.approve")}
                </Button>
                <Button size="sm" variant="destructive" disabled={submitDecisionPending} onClick={() => onSubmitDecision(selectedSectionId, "rejected", reviewDecisionComment || null)}>
                  {submitDecisionPending && <Spinner data-icon="inline-start" />}
                  {t("review.reject")}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t("review.comments")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {!selectedThreadId ? (
            <Empty className="min-h-40">
              <EmptyHeader>
                <EmptyMedia variant="icon"><MessageCircleIcon /></EmptyMedia>
                <EmptyTitle>{t("review.noThreadSelected")}</EmptyTitle>
                <EmptyDescription>{t("review.noThreadDesc")}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <>
              <ScrollArea className="max-h-96">
                <div className="flex flex-col gap-3 pr-4">
                  {reviewComments?.map((c) => (
                    <div key={c.id} className="border rounded-md p-3 flex flex-col gap-1">
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Badge variant={c.author_type === "ai" ? "secondary" : "default"}>{c.author_type}</Badge>
                        <span>{c.author_id}</span>
                        <span>{new Date(c.created_at).toLocaleString()}</span>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{c.body}</p>
                    </div>
                  ))}
                  {reviewComments?.length === 0 && (
                    <Empty className="min-h-32">
                      <EmptyHeader>
                        <EmptyMedia variant="icon"><MessageCircleIcon /></EmptyMedia>
                        <EmptyTitle>{t("review.noComments")}</EmptyTitle>
                        <EmptyDescription>{t("review.noCommentsDesc")}</EmptyDescription>
                      </EmptyHeader>
                    </Empty>
                  )}
                </div>
              </ScrollArea>
              <div className="flex gap-2">
                <Input
                  value={reviewCommentBody}
                  onChange={(e) => setReviewCommentBody(e.target.value)}
                  placeholder={t("review.addComment")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && reviewCommentBody.trim() && !addCommentPending) {
                      onAddComment(selectedThreadId, reviewCommentBody.trim());
                      setReviewCommentBody("");
                    }
                  }}
                />
                <Button
                  size="sm"
                  disabled={!reviewCommentBody.trim() || addCommentPending}
                  onClick={() => { onAddComment(selectedThreadId, reviewCommentBody.trim()); setReviewCommentBody(""); }}
                >
                  {addCommentPending && <Spinner data-icon="inline-start" />}
                  {t("review.send")}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
