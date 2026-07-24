import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { formatDistanceToNow } from "date-fns";
import { zhCN, enUS } from "date-fns/locale";
import {
  BellIcon,
  BotIcon,
  CheckCheckIcon,
  FileTextIcon,
  ShieldCheckIcon,
  DownloadIcon,
  AlertTriangleIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useNotifications } from "@/hooks/use-notifications";

const typeIcon: Record<string, React.ReactNode> = {
  draft_completed: <FileTextIcon className="size-4 text-blue-500" />,
  review_approved: <ShieldCheckIcon className="size-4 text-green-500" />,
  export_ready: <DownloadIcon className="size-4 text-purple-500" />,
  hitl_required: <AlertTriangleIcon className="size-4 text-amber-500" />,
  agent_task: <BotIcon className="size-4 text-sky-500" />,
};

export function NotificationBell() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { notifications, unreadCount, loading, markAsRead, markAllAsRead } =
    useNotifications();

  const dateLocale = i18n.language === "zh-CN" ? zhCN : enUS;

  const handleNotificationClick = async (id: string, link?: string) => {
    await markAsRead(id);
    if (link) navigate(link);
  };

  return (
    <Popover>
      <PopoverTrigger
        className="relative rounded-md p-1 text-muted-foreground hover:text-foreground"
        aria-label={t("notifications.title")}
      >
        <BellIcon className="size-4" />
        {unreadCount > 0 && (
          <Badge
            variant="destructive"
            className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full p-0 text-[10px]"
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </Badge>
        )}
      </PopoverTrigger>
      <PopoverContent side="bottom" align="end" sideOffset={8} className="w-80 p-0">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-sm font-medium">
            {t("notifications.title")}
          </span>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="xs"
              onClick={markAllAsRead}
              className="gap-1 text-xs"
            >
              <CheckCheckIcon className="size-3" />
              {t("notifications.markAllRead")}
            </Button>
          )}
        </div>
        <ScrollArea className="max-h-80">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              {t("actions.loading")}
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              {t("notifications.empty")}
            </div>
          ) : (
            <div className="flex flex-col">
              {notifications.map((notification) => (
                <button
                  key={notification.id}
                  onClick={() =>
                    handleNotificationClick(notification.id, notification.link)
                  }
                  className={`flex items-start gap-3 px-3 py-2.5 text-left transition-colors hover:bg-muted ${
                    !notification.read ? "bg-muted/50" : ""
                  }`}
                >
                  <div className="mt-0.5 shrink-0">
                    {typeIcon[notification.type] ?? <BellIcon className="size-4 text-muted-foreground" />}
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      <span
                        className={`truncate text-sm ${
                          !notification.read
                            ? "font-medium text-foreground"
                            : "text-muted-foreground"
                        }`}
                      >
                        {notification.title}
                      </span>
                      {!notification.read && (
                        <span className="size-1.5 shrink-0 rounded-full bg-blue-500" />
                      )}
                    </div>
                    <span className="line-clamp-2 text-xs text-muted-foreground">
                      {notification.description}
                    </span>
                    <span className="text-[11px] text-muted-foreground/70">
                      {formatDistanceToNow(new Date(notification.created_at), {
                        addSuffix: true,
                        locale: dateLocale,
                      })}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
