import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import type { RuntimeSummary } from "@/lib/api";

type RuntimeSummaryCardsProps = {
  summary?: RuntimeSummary;
};

function isHealthy(summary: RuntimeSummary) {
  return summary.failed_runs === 0 && summary.queue_depth < 10 && summary.draft_success_rate >= 0.95;
}

export function RuntimeSummaryCards({ summary }: RuntimeSummaryCardsProps) {
  if (!summary) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">System Status</CardTitle>
        </CardHeader>
        <CardContent aria-label="Loading runtime summary" className="flex flex-col gap-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </CardContent>
      </Card>
    );
  }

  const healthy = isHealthy(summary);
  const draftSuccessPercent = Math.round(summary.draft_success_rate * 100);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">System Status</CardTitle>
        <CardDescription>Runtime health from ops telemetry</CardDescription>
        <CardAction>
          <Badge variant={healthy ? "default" : "destructive"}>
            {healthy ? "Healthy" : "Attention needed"}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-4 text-center sm:grid-cols-3">
          <div>
            <p className="text-2xl font-bold">{summary.queue_depth}</p>
            <p className="text-xs text-muted-foreground">Queue Depth</p>
            <Progress value={Math.min(summary.queue_depth * 10, 100)} className="mt-2" />
          </div>
          <div>
            <p className="text-2xl font-bold">{summary.failed_runs}</p>
            <p className="text-xs text-muted-foreground">Failed Runs</p>
            <Progress value={Math.min(summary.failed_runs * 20, 100)} className="mt-2" />
          </div>
          <div>
            <p className="text-2xl font-bold">{draftSuccessPercent}%</p>
            <p className="text-xs text-muted-foreground">Draft Success</p>
            <Progress value={draftSuccessPercent} className="mt-2" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
