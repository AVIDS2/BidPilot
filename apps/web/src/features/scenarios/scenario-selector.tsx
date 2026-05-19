import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Field, FieldLabel } from "@/components/ui/field";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { listScenarios, type ScenarioRead } from "@/lib/api";

interface ScenarioSelectorProps {
  value: string;
  onChange: (key: string) => void;
}

export function ScenarioSelector({ value, onChange }: ScenarioSelectorProps) {
  const { data: scenarios, isLoading } = useQuery<ScenarioRead[]>({
    queryKey: ["scenarios"],
    queryFn: listScenarios,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <Field>
      <FieldLabel>Scenario Package</FieldLabel>
      <div className="grid grid-cols-2 gap-3">
        {isLoading && (
          <>
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </>
        )}
        {!isLoading && scenarios?.length === 0 && (
          <div className="col-span-2">
            <Empty className="min-h-28">
              <EmptyHeader>
                <EmptyTitle>No scenario packages</EmptyTitle>
                <EmptyDescription>Scenario packages will appear here after the API is seeded.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          </div>
        )}
        {!isLoading && scenarios?.map((s) => (
          <Card
            key={s.key}
            role="button"
            tabIndex={0}
            aria-pressed={value === s.key}
            className={cn(
              "cursor-pointer transition-colors hover:border-primary focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
              value === s.key && "border-primary ring-1 ring-primary",
            )}
            onClick={() => onChange(s.key)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onChange(s.key);
              }
            }}
          >
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-sm flex items-center gap-2">
                {s.label}
                {value === s.key && <Badge variant="default">Selected</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-4 px-4">
              <p className="text-xs text-muted-foreground">{s.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </Field>
  );
}
