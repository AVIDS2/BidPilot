import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldLabel } from "@/components/ui/field";
import { AgentProgress } from "@/components/agent-progress";
import { useTranslation } from "react-i18next";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BotIcon } from "lucide-react";
import type { ExecutionRunRead } from "@/lib/api";

interface AgentTabProps {
  runs: ExecutionRunRead[];
}

export function AgentTab({ runs }: AgentTabProps) {
  const { t } = useTranslation("projects");
  const [agentRunId, setAgentRunId] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <BotIcon className="size-4" />
          {t("agent.tabTitle")}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Field>
          <FieldLabel>{t("agent.selectRun")}</FieldLabel>
          <Select value={agentRunId ?? ""} onValueChange={(v) => setAgentRunId(v || null)}>
            <SelectTrigger className="max-w-xs">
              <SelectValue placeholder={t("agent.selectRunPlaceholder")} />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {runs?.filter((r) => r.status === "running" || r.status === "pending").map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.run_type} &middot; {t(`statusValues.${r.status}`, { defaultValue: r.status })} &middot; {r.id.slice(0, 8)}
                  </SelectItem>
                ))}
                {runs?.filter((r) => r.status !== "running" && r.status !== "pending").map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.run_type} &middot; {t(`statusValues.${r.status}`, { defaultValue: r.status })} &middot; {r.id.slice(0, 8)}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <AgentProgress runId={agentRunId} />
      </CardContent>
    </Card>
  );
}
