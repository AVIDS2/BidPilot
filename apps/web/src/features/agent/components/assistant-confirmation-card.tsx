import { useState } from "react";
import { ShieldCheckIcon, XIcon, CheckIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AssistantConfirmationRequest } from "@/features/agent/state/agent-store";

export function AssistantConfirmationCard({
  confirmation,
  onConfirm,
  onCancel,
}: {
  confirmation: AssistantConfirmationRequest;
  onConfirm: (confirmationText?: string) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation("ai-assistant");
  const [confirmationText, setConfirmationText] = useState("");
  const requiresTypedConfirmation = Boolean(confirmation.requiresTypedConfirmation);
  const canConfirm =
    !requiresTypedConfirmation || confirmationText.trim() === (confirmation.expectedText ?? "").trim();

  return (
    <div
      className="w-full rounded-2xl rounded-bl-md border px-3 py-3 text-xs shadow-sm"
      style={{ background: "var(--card)", borderColor: "var(--border)", color: "var(--foreground)" }}
    >
      <div className="flex items-start gap-2">
        <div
          className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-md"
          style={{ background: "var(--muted)", color: "var(--primary)" }}
        >
          <ShieldCheckIcon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-medium">{t("execution.confirmAction")}</div>
          <p className="mt-1 leading-relaxed" style={{ color: "var(--muted-foreground)" }}>
            {confirmation.message}
          </p>
          {requiresTypedConfirmation ? (
            <div className="mt-3 space-y-1.5">
              <label className="text-[11px] font-medium" htmlFor="assistant-typed-confirmation">
                {t("execution.typedConfirmationLabel")}
              </label>
              <Input
                id="assistant-typed-confirmation"
                value={confirmationText}
                onChange={(event) => setConfirmationText(event.target.value)}
                placeholder={confirmation.expectedText || t("execution.typedConfirmationPlaceholder")}
                className="h-8 text-xs"
              />
              {confirmation.expectedText && (
                <p className="text-[11px]" style={{ color: "var(--muted-foreground)" }}>
                  {t("execution.typedConfirmationHint", { value: confirmation.expectedText })}
                </p>
              )}
            </div>
          ) : (
            <div
              className="mt-2 rounded-md px-2 py-1 font-mono text-[11px]"
              style={{ background: "var(--muted)", color: "var(--muted-foreground)" }}
            >
              {confirmation.toolName}
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <Button
              size="sm"
              className="h-7 px-2.5 text-xs"
              disabled={!canConfirm}
              onClick={() => onConfirm(confirmationText)}
            >
              <CheckIcon className="mr-1 h-3.5 w-3.5" />
              {t("execution.confirm")}
            </Button>
            <Button size="sm" variant="outline" className="h-7 px-2.5 text-xs" onClick={onCancel}>
              <XIcon className="mr-1 h-3.5 w-3.5" />
              {t("execution.cancel")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
