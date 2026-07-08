import { useLocation, Link } from "react-router-dom"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

export function NavMain({
  items,
}: {
  items: {
    title: string
    url: string
    icon: React.ReactNode
    isActive?: boolean
  }[]
}) {
  const location = useLocation()

  return (
    <SidebarMenu>
      {items.map((item) => {
        const isActive = item.isActive ?? (location.pathname === item.url || location.pathname.startsWith(item.url + "/"))
        return (
          <SidebarMenuItem key={item.title}>
            <SidebarMenuButton
              isActive={isActive}
              tooltip={item.title}
              render={<Link to={item.url} />}
              className="justify-start transition-all duration-200 group-data-[collapsible=icon]:justify-center"
              style={{
                color: isActive ? "var(--primary)" : "var(--muted-foreground)",
                background: isActive ? "rgba(132, 204, 22, 0.08)" : "transparent",
                boxShadow: isActive ? "inset 2px 0 0 var(--primary)" : "inset 2px 0 0 transparent",
              }}
            >
              {item.icon}
              <span className="text-sm">{item.title}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        )
      })}
    </SidebarMenu>
  )
}
