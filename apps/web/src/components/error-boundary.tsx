import { Component, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { AlertTriangleIcon } from "lucide-react";
import i18n from "@/lib/i18n";
import { isDynamicImportError } from "@/app-route-loaders";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      const message = isDynamicImportError(this.state.error)
        ? i18n.t("error.chunk")
        : this.state.error?.message ?? i18n.t("error.fallback");
      return (
        <div className="flex min-h-svh items-center justify-center p-6">
          <Card className="max-w-md w-full">
            <CardHeader>
              <div className="flex items-center gap-2">
                <AlertTriangleIcon className="size-5 text-destructive" />
                <CardTitle>{i18n.t("error.title")}</CardTitle>
              </div>
              <CardDescription>
                {message}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.reload();
                }}
              >
                {i18n.t("error.reload")}
              </Button>
            </CardContent>
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}
