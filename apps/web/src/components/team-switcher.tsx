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
                className="w-fit px-2 transition-all duration-200"
                style={{
                  color: "#ffffff",
                }}
              />
            }
          >
            <div
              className="flex aspect-square size-6 items-center justify-center rounded-md"
              style={{
                background: "#84cc16",
                color: "#0a0a0a",
              }}
            >
              {activeTeam.logo}
            </div>
            <span className="truncate font-medium text-sm">{activeTeam.name}</span>
            <ChevronDownIcon className="opacity-50 size-3.5" style={{ color: "#737373" }} />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-64 rounded-lg"
            align="start"
            side="bottom"
            sideOffset={4}
            style={{
              background: "#171717",
              borderColor: "rgba(163, 163, 163, 0.1)",
            }}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel
                className="text-xs font-medium tracking-widest uppercase"
                style={{ color: "#525252" }}
              >
                {t("nav.teams")}
              </DropdownMenuLabel>
              {teams.map((team, index) => (
                <DropdownMenuItem
                  key={team.name}
                  onClick={() => setActiveTeam(team)}
                  className="gap-2 p-2 text-[#a3a3a3] focus:text-white focus:bg-[rgba(163,163,163,0.08)]"
                >
                  <div
                    className="flex size-6 items-center justify-center rounded-xs"
                    style={{
                      background: "rgba(132, 204, 22, 0.1)",
                      border: "1px solid rgba(132, 204, 22, 0.2)",
                    }}
                  >
                    {team.logo}
                  </div>
                  {team.name}
                  <DropdownMenuShortcut style={{ color: "#525252" }}>⌘{index + 1}</DropdownMenuShortcut>
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
