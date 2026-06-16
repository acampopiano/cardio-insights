import { useEffect, useRef, useState } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { Header } from "@/components/layout/Header"
import { Sidebar } from "@/components/layout/Sidebar"
import { useSidebarCollapsed } from "@/lib/useSidebarCollapsed"

function useCloseOnRouteChange(pathname: string, close: () => void) {
  const prev = useRef(pathname)
  useEffect(() => {
    if (prev.current !== pathname) {
      prev.current = pathname
      close()
    }
  }, [pathname, close])
}

export function AppLayout() {
  const [collapsed, toggleCollapsed] = useSidebarCollapsed()
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  useCloseOnRouteChange(location.pathname, () => setMobileOpen(false))

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[var(--color-incc-soft)] dark:bg-background">
      <Header onMenuClick={() => setMobileOpen(true)} />
      <div className="flex min-h-0 flex-1">
        <Sidebar
          collapsed={collapsed}
          onToggleCollapse={toggleCollapsed}
          mobileOpen={mobileOpen}
          onCloseMobile={() => setMobileOpen(false)}
        />
        <main className="min-w-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
