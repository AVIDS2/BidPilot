import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { InputGroup, InputGroupInput, InputGroupAddon } from "@/components/ui/input-group";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { listReviewComments, createReviewComment, type ReviewCommentRead } from "@/lib/api";
import { MessageCircleIcon } from "lucide-react";
import { toast } from "sonner";

interface ReviewPageProps {
  threadId: string | null;
}

export function ReviewPage({ threadId }: ReviewPageProps) {
  const queryClient = useQueryClient();
  const [commentBody, setCommentBody] = useState("");

  const { data: comments, isLoading } = useQuery<ReviewCommentRead[]>({
    queryKey: ["review-comments", threadId],
    queryFn: () => listReviewComments(threadId!),
    enabled: !!threadId,
    staleTime: 15 * 1000,
  });

  const addCommentMut = useMutation({
    mutationFn: createReviewComment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-comments", threadId] });
      setCommentBody("");
      toast.success("Comment added");
    },
    onError: () => {
      toast.error("Failed to add comment");
    },
  });

  if (!threadId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Review Comments</CardTitle>
        </CardHeader>
        <CardContent>
          <Empty className="min-h-40">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <MessageCircleIcon />
              </EmptyMedia>
              <EmptyTitle>No thread selected</EmptyTitle>
              <EmptyDescription>Select a review thread to view and add comments.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Review Comments</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isLoading ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        ) : comments?.length ? (
          comments.map((c) => (
            <div key={c.id} className="border rounded-md p-3 flex flex-col gap-1">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Badge variant={c.author_type === "ai" ? "secondary" : "default"}>
                  {c.author_type}
                </Badge>
                <span>{c.author_id}</span>
                <span>{new Date(c.created_at).toLocaleString()}</span>
              </div>
              <p className="text-sm whitespace-pre-wrap">{c.body}</p>
            </div>
          ))
        ) : (
          <Empty className="min-h-32">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <MessageCircleIcon />
              </EmptyMedia>
              <EmptyTitle>No comments yet</EmptyTitle>
              <EmptyDescription>Add the first comment to start the review discussion.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}

        <InputGroup>
          <InputGroupInput
            value={commentBody}
            onChange={(e) => setCommentBody(e.target.value)}
            placeholder="Add a comment..."
            onKeyDown={(e) => {
              if (e.key === "Enter" && commentBody.trim() && !addCommentMut.isPending) {
                addCommentMut.mutate({ thread_id: threadId, body: commentBody.trim() });
              }
            }}
          />
          <InputGroupAddon align="inline-end">
            <Button
              size="sm"
              disabled={!commentBody.trim() || addCommentMut.isPending}
              onClick={() => {
                addCommentMut.mutate({ thread_id: threadId, body: commentBody.trim() });
              }}
            >
              {addCommentMut.isPending && <Spinner data-icon="inline-start" />}
              Send
            </Button>
          </InputGroupAddon>
        </InputGroup>
      </CardContent>
    </Card>
  );
}
