"use client"

import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { useAuth } from "@/lib/auth"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { ChevronsUpDownIcon, BadgeCheckIcon, LogOutIcon } from "lucide-react"

export function NavUser({
  user,
}: {
  user: {
    name: string
    email: string
    avatar: string
  }
}) {
  const { isMobile } = useSidebar()
  const { logout } = useAuth()
  const navigate = useNavigate()
  const { t } = useTranslation()

  const handleLogout = () => {
    logout()
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="lg"
                className="justify-start transition-all duration-200 group-data-[collapsible=icon]:justify-center"
                style={{
                  background: "var(--muted)",
                  borderColor: "var(--border)",
                }}
              />
            }
          >
            <Avatar className="size-8">
              <AvatarImage src={user.avatar} alt={user.name} />
              <AvatarFallback
                className="text-xs"
                style={{
                  background: "rgba(132, 204, 22, 0.15)",
                  color: "var(--primary)",
                }}
              >
                {user.name?.charAt(0)?.toUpperCase() || "U"}
              </AvatarFallback>
            </Avatar>
            <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
              <span className="truncate font-medium text-white text-xs">{user.name}</span>
              <span className="truncate text-xs" style={{ color: "var(--text-tertiary)" }}>{user.email}</span>
            </div>
            <ChevronsUpDownIcon className="ml-auto size-3.5 group-data-[collapsible=icon]:hidden" style={{ color: "var(--text-quaternary)" }} />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="start"
            sideOffset={4}
            style={{
              background: "var(--card)",
              borderColor: "var(--border)",
            }}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className="p-0 font-normal">
                <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                  <Avatar className="size-8">
                    <AvatarImage src={user.avatar} alt={user.name} />
                    <AvatarFallback
                      className="text-xs"
                      style={{
                        background: "rgba(132, 204, 22, 0.15)",
                        color: "var(--primary)",
                      }}
                    >
                      {user.name?.charAt(0)?.toUpperCase() || "U"}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium text-white">{user.name}</span>
                    <span className="truncate text-xs" style={{ color: "var(--text-tertiary)" }}>{user.email}</span>
                  </div>
                </div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator style={{ background: "var(--border)" }} />
            <DropdownMenuGroup>
              <DropdownMenuItem
                onClick={() => navigate("/account")}
                className="text-muted-foreground focus:text-white focus:bg-[rgba(163,163,163,0.08)]"
              >
                <BadgeCheckIcon className="size-4" />
                {t("user.account")}
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator style={{ background: "var(--border)" }} />
            <DropdownMenuGroup>
              <DropdownMenuItem
                onClick={handleLogout}
                className="text-muted-foreground focus:text-red-400 focus:bg-[rgba(239,68,68,0.08)]"
              >
                <LogOutIcon className="size-4" />
                {t("user.logOut")}
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
