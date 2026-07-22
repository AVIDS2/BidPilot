import * as React from "react"

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
  navGroups: {
    title: string
    items: { title: string; url: string; icon: React.ReactNode; isActive?: boolean }[]
  }[]
  teams: { name: string; logo: React.ReactNode; plan: string }[]
  user: { name: string; email: string; avatar: string }
} & React.ComponentProps<typeof Sidebar>

export function AppSidebar({
  navGroups,
  teams,
  user,
  ...props
}: AppSidebarProps) {
  return (
    <Sidebar
      collapsible="icon"
      className="border-r dark:bg-[var(--surface-1)]"
      style={{
        borderColor: "var(--border)",
      }}
      {...props}
    >
      <SidebarHeader
        className="p-4 transition-[padding] duration-200 group-data-[collapsible=icon]:p-2"
        style={{
          borderBottom: "1px solid var(--border)",
        }}
      >
        <TeamSwitcher teams={teams} />
      </SidebarHeader>
      <SidebarContent className="px-2 py-3 transition-[padding] duration-200 group-data-[collapsible=icon]:px-2">
        {navGroups.map((group) => (
          <SidebarGroup key={group.title}>
            <SidebarGroupLabel
              className="mb-2 px-2 text-xs font-medium uppercase tracking-widest group-data-[collapsible=icon]:hidden"
              style={{ color: "var(--text-quaternary)" }}
            >
              {group.title}
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <NavMain items={group.items} />
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter
        className="p-3 transition-[padding] duration-200 group-data-[collapsible=icon]:p-2"
        style={{
          borderTop: "1px solid var(--border)",
        }}
      >
        <NavUser user={user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
