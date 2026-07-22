import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { FileTextIcon, RocketIcon, CheckCircleIcon } from "lucide-react";

interface Step {
  icon: React.ReactNode;
  title: string;
  description: string;
}

interface OnboardingWizardProps {
  onFinish?: () => void;
  onCreateOwnProject?: () => void;
  onCreateDemo?: () => void;
  isCreatingDemo?: boolean;
}

export function OnboardingWizard({
  onFinish,
  onCreateOwnProject,
  onCreateDemo,
  isCreatingDemo = false,
}: OnboardingWizardProps = {}) {
  const { t } = useTranslation(["onboarding"]);
  const [step, setStep] = useState(0);

  const STEPS: Step[] = [
    {
      icon: <RocketIcon className="size-8 text-primary" />,
      title: t("steps.welcome.title"),
      description: t("steps.welcome.description"),
    },
    {
      icon: <FileTextIcon className="size-8 text-primary" />,
      title: t("steps.createProject.title"),
      description: t("steps.createProject.description"),
    },
    {
      icon: <CheckCircleIcon className="size-8 text-primary" />,
      title: t("steps.allSet.title"),
      description: t("steps.allSet.description"),
    },
  ];

  const current = STEPS[step];
  const progress = ((step + 1) / STEPS.length) * 100;

  return (
    <Card className="mx-auto max-w-md">
      <CardHeader className="text-center">
        <Progress value={progress} className="mb-4" />
        <div className="flex justify-center">{current.icon}</div>
        <CardTitle className="mt-3">{current.title}</CardTitle>
        <CardDescription>{current.description}</CardDescription>
      </CardHeader>
      <CardFooter className="flex flex-wrap justify-end gap-2">
        {step < STEPS.length - 1 && (
          <Button onClick={() => setStep(step + 1)}>{t("buttons.next")}</Button>
        )}
        {step === STEPS.length - 1 && (
          <>
            {onCreateDemo && (
              <Button variant="outline" disabled={isCreatingDemo} onClick={onCreateDemo}>
                {isCreatingDemo && <Spinner data-icon="inline-start" />}
                {t("buttons.tryDemo")}
              </Button>
            )}
            <Button onClick={() => {
              setStep(0);
              onCreateOwnProject?.();
              onFinish?.();
            }}>
              {t("buttons.startOwn")}
            </Button>
          </>
        )}
      </CardFooter>
    </Card>
  );
}
