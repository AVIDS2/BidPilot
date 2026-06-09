import * as React from "react"
import { useTranslation } from "react-i18next"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"
import { NavMain } from "@/components/nav-main"
import { NavUser } from "@/components/nav-user"
import { TeamSwitcher } from "@/components/team-switcher"

export type AppSidebarProps = {
  navItems: { title: string; url: string; icon: React.ReactNode; isActive?: boolean }[]
  teams: { name: string; logo: React.ReactNode; plan: string }[]
  user: { name: string; email: string; avatar: string }
} & React.ComponentProps<typeof Sidebar>

export function AppSidebar({
  navItems,
  teams,
  user,
  ...props
}: AppSidebarProps) {
  const { t } = useTranslation()

  return (
    <Sidebar
      collapsible="icon"
      className="border-r"
      style={{
        borderColor: "rgba(163, 163, 163, 0.06)",
        background: "#0a0a0a",
      }}
      {...props}
    >
      <SidebarHeader
        className="p-4"
        style={{
          borderBottom: "1px solid rgba(163, 163, 163, 0.06)",
        }}
      >
        <TeamSwitcher teams={teams} />
      </SidebarHeader>
      <SidebarContent className="px-2 py-3">
        <SidebarGroup>
          <SidebarGroupLabel
            className="text-xs font-medium tracking-widest uppercase mb-2 px-2"
            style={{ color: "#525252" }}
          >
            {t("nav.navigation")}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <NavMain items={navItems} />
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter
        className="p-3"
        style={{
          borderTop: "1px solid rgba(163, 163, 163, 0.06)",
        }}
      >
        <NavUser user={user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
