import { Link, useLocation } from "react-router-dom"
import { ChevronsLeft, ChevronsRight, X } from "lucide-react"

import { BrandMark } from "@/components/BrandMark"
import { NAV_ITEMS } from "@/lib/navigation"
import { cn } from "@/lib/utils"

interface SidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
  mobileOpen: boolean
  onCloseMobile: () => void
}

export function Sidebar({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const location = useLocation()

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity md:hidden",
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0"
        )}
        onClick={onCloseMobile}
        aria-hidden="true"
      />

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 shrink-0 flex-col bg-[var(--color-incc-deep)] text-white shadow-2xl",
          "transition-transform duration-200 ease-in-out",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
          "md:relative md:translate-x-0 md:shadow-none md:transition-[width]",
          collapsed ? "md:w-16" : "md:w-60"
        )}
        aria-label="Navegacion principal"
      >
        <div className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-white/10 px-3">
          <Link
            to="/dashboard"
            onClick={onCloseMobile}
            className={cn(
              "flex items-center gap-2 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-white/40",
              collapsed && "md:justify-center"
            )}
            aria-label="Ir al inicio"
          >
            <BrandMark size={28} showText={false} />
            <span
              className={cn(
                "text-sm font-semibold",
                collapsed && "md:hidden"
              )}
            >
              Cardio Insights
            </span>
          </Link>

          <button
            type="button"
            onClick={onCloseMobile}
            className="grid size-8 place-items-center rounded-md text-white/80 hover:bg-white/10 hover:text-white md:hidden"
            aria-label="Cerrar menu"
          >
            <X className="size-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path

            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onCloseMobile}
                title={collapsed ? item.label : undefined}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "group flex items-center gap-3 rounded-md px-3 py-2 text-sm outline-none transition-colors",
                  "focus-visible:ring-2 focus-visible:ring-white/40",
                  isActive
                    ? "bg-white/15 text-white"
                    : "text-white/75 hover:bg-white/10 hover:text-white",
                  collapsed && "md:justify-center md:px-2"
                )}
              >
                <Icon
                  className="size-4 shrink-0"
                  aria-hidden="true"
                />
                <span
                  className={cn(
                    "flex-1 truncate",
                    collapsed && "md:hidden"
                  )}
                >
                  {item.label}
                </span>
                {!item.available && (
                  <span
                    className={cn(
                      "rounded-full bg-white/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-white/70",
                      collapsed && "md:hidden"
                    )}
                  >
                    Pronto
                  </span>
                )}
              </Link>
            )
          })}
        </nav>

        <div className="hidden border-t border-white/10 p-2 md:block">
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Expandir sidebar" : "Colapsar sidebar"}
            title={collapsed ? "Expandir" : "Colapsar"}
            className={cn(
              "flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs text-white/70 transition-colors hover:bg-white/10 hover:text-white",
              collapsed && "justify-center px-2"
            )}
          >
            {collapsed ? (
              <ChevronsRight className="size-4" />
            ) : (
              <>
                <ChevronsLeft className="size-4" />
                <span>Colapsar</span>
              </>
            )}
          </button>
        </div>
      </aside>
    </>
  )
}
