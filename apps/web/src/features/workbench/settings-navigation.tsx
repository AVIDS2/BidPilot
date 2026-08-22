import {
  Building2Icon,
  CpuIcon,
  WebhookIcon,
  Settings2Icon,
  UserRoundIcon,
  UsersRoundIcon,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const navigationItems = [
  { group: "个人", label: "账户与个性化", to: "/account", icon: UserRoundIcon },
  { group: "工作区", label: "组织设置", to: "/administration", icon: Building2Icon, adminOnly: true },
  { group: "工作区", label: "集成与模型", to: "/settings/providers", icon: CpuIcon, adminOnly: true },
  { group: "工作区", label: "Webhook", to: "/settings/webhooks", icon: WebhookIcon, adminOnly: true },
  { group: "工作区", label: "成员与权限", to: "/members", icon: UsersRoundIcon, adminOnly: true },
];

export function SettingsNavigation() {
  const { user } = useAuth();
  const visibleItems = navigationItems.filter((item) => !item.adminOnly || user?.role === "admin");
  const groups = [...new Set(visibleItems.map((item) => item.group))];

  return (
    <aside className="wb-settings-nav" aria-label="设置导航">
      <div className="wb-settings-nav-head">
        <Settings2Icon aria-hidden="true" />
        <div>
          <p className="wb-settings-nav-kicker">BidPilot</p>
          <strong>{user?.org_slug || "当前工作区"}</strong>
        </div>
      </div>
      <nav>
        {groups.map((group) => (
          <div className="wb-settings-nav-group" key={group}>
            <span className="wb-settings-nav-label">{group}</span>
            {visibleItems.filter((item) => item.group === group).map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  className={({ isActive }) => cn("wb-settings-nav-link", isActive && "is-active")}
                  key={item.to}
                  to={item.to}
                >
                  <Icon aria-hidden="true" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}
