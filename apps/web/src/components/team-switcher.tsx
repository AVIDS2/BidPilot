"use client"

import * as React from "react"
import { useTranslation } from "react-i18next"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { ChevronDownIcon } from "lucide-react"

export function TeamSwitcher({
  teams,
}: {
  teams: {
    name: string
    logo: React.ReactNode
    plan: string
  }[]
}) {
  const { t } = useTranslation()
  const [activeTeam, setActiveTeam] = React.useState(teams[0])
  if (!activeTeam) {
    return null
  }
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                className="w-full justify-start px-2 transition-all duration-200 group-data-[collapsible=icon]:justify-center"
                style={{
                  color: "var(--foreground)",
                }}
              />
            }
          >
            <div className="flex aspect-square size-7 items-center justify-center rounded-lg">
              {activeTeam.logo}
            </div>
            <span className="truncate font-medium text-sm group-data-[collapsible=icon]:hidden">{activeTeam.name}</span>
            <ChevronDownIcon className="opacity-50 size-3.5 group-data-[collapsible=icon]:hidden" style={{ color: "var(--text-tertiary)" }} />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-64 rounded-lg"
            align="start"
            side="bottom"
            sideOffset={4}
            style={{
              background: "var(--card)",
              borderColor: "var(--border)",
            }}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel
                className="text-xs font-medium tracking-widest uppercase"
                style={{ color: "var(--text-quaternary)" }}
              >
                {t("nav.teams")}
              </DropdownMenuLabel>
              {teams.map((team, index) => (
                <DropdownMenuItem
                  key={team.name}
                  onClick={() => setActiveTeam(team)}
                  className="gap-2 p-2 text-muted-foreground focus:text-white focus:bg-[rgba(163,163,163,0.08)]"
                >
                  <div className="flex size-7 items-center justify-center rounded-lg">
                    {team.logo}
                  </div>
                  {team.name}
                  <DropdownMenuShortcut style={{ color: "var(--text-quaternary)" }}>⌘{index + 1}</DropdownMenuShortcut>
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
