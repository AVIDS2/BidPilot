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
              render={<Link to={item.url} />}
              className="transition-all duration-200"
              style={{
                color: isActive ? "var(--primary)" : "var(--muted-foreground)",
                background: isActive ? "rgba(132, 204, 22, 0.08)" : "transparent",
                borderLeft: isActive ? "2px solid var(--primary)" : "2px solid transparent",
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
