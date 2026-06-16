import { Link } from "react-router-dom"
import { ChevronDown, LogOut, Menu, Settings, UserCircle } from "lucide-react"

import { BrandMark } from "@/components/BrandMark"
import { ThemeToggle } from "@/components/ThemeToggle"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "@/features/auth/useAuth"
import { cn, getInitials } from "@/lib/utils"

const ROLE_BADGE: Record<string, { label: string; className: string }> = {
  clinician: {
    label: "Clinician",
    className: "bg-[var(--color-incc-primary)]/15 text-[var(--color-incc-primary)] ring-1 ring-[var(--color-incc-primary)]/30",
  },
  admin: {
    label: "Admin",
    className:
      "bg-[var(--color-incc-accent)]/15 text-[var(--color-incc-accent)] ring-1 ring-[var(--color-incc-accent)]/30",
  },
}

function RoleBadge({ role }: { role: string }) {
  const entry = ROLE_BADGE[role] ?? {
    label: role,
    className: "bg-muted text-muted-foreground ring-1 ring-border",
  }
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        entry.className
      )}
    >
      {entry.label}
    </span>
  )
}

function UserAvatar({
  fullName,
  role,
  size = 40,
  surface = "onDark",
}: {
  fullName: string
  role: string
  size?: number
  surface?: "onDark" | "onLight"
}) {
  const initials = getInitials(fullName)
  const ring =
    role === "admin"
      ? "ring-[var(--color-incc-accent)]/70"
      : "ring-[var(--color-incc-primary)]/70"
  return (
    <div
      className={cn(
        "grid place-items-center rounded-full font-semibold text-white ring-2",
        surface === "onDark"
          ? "bg-white/15"
          : "bg-[var(--color-incc-primary)]",
        ring
      )}
      style={{ width: size, height: size, fontSize: size * 0.34 }}
      aria-hidden="true"
    >
      {initials}
    </div>
  )
}

function ComingSoonBadge() {
  return (
    <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
      Pronto
    </span>
  )
}

interface HeaderProps {
  onMenuClick?: () => void
}

export function Header({ onMenuClick }: HeaderProps) {
  const { user, logout } = useAuth()
  const firstName = user?.full_name.split(" ").find((p) => !p.endsWith(".")) ?? ""

  return (
    <header className="z-30 shrink-0 bg-[var(--color-incc-deep)] text-white shadow-sm">
      <div className="flex h-14 items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onMenuClick}
            className="grid size-9 place-items-center rounded-md text-white/85 hover:bg-white/10 hover:text-white md:hidden"
            aria-label="Abrir menu"
          >
            <Menu className="size-5" />
          </button>

          <Link
            to="/dashboard"
            className="flex items-center gap-2 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-white/40 md:hidden"
            aria-label="Ir al inicio del dashboard"
          >
            <BrandMark size={28} showText={false} />
            <span className="text-sm font-semibold">Cardio Insights</span>
          </Link>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <ThemeToggle variant="header" />

          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger
                className={cn(
                  "group flex items-center gap-2 rounded-full py-1 pl-1 pr-2 text-white outline-none transition-colors",
                  "hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-white/40 sm:pr-3"
                )}
                aria-label={`Menu de ${user.full_name}`}
              >
                <UserAvatar fullName={user.full_name} role={user.role} size={36} />
                <span className="hidden text-sm font-medium sm:inline">
                  {firstName}
                </span>
                <ChevronDown
                  className="size-4 text-white/70 transition-transform group-data-[state=open]:rotate-180"
                  aria-hidden="true"
                />
              </DropdownMenuTrigger>

              <DropdownMenuContent
                align="end"
                className="w-72"
                onCloseAutoFocus={(e) => e.preventDefault()}
              >
                <div className="flex items-center gap-3 px-2 py-2">
                  <UserAvatar
                    fullName={user.full_name}
                    role={user.role}
                    size={40}
                    surface="onLight"
                  />
                  <div className="min-w-0 flex-1 leading-tight">
                    <p className="truncate text-sm font-semibold text-foreground">
                      {user.full_name}
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      <RoleBadge role={user.role} />
                      <span className="truncate text-[11px] text-muted-foreground">
                        @{user.username}
                      </span>
                    </div>
                  </div>
                </div>

                <DropdownMenuSeparator />

                <DropdownMenuLabel>Permisos</DropdownMenuLabel>
                {user.permissions.length > 0 ? (
                  <ul className="px-2 pb-1.5 space-y-0.5">
                    {user.permissions.map((p) => (
                      <li
                        key={p}
                        className="flex items-center gap-2 text-xs text-foreground/85"
                      >
                        <span className="size-1.5 rounded-full bg-[var(--color-incc-primary)]" />
                        <code className="font-mono text-[11px]">{p}</code>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="px-2 pb-1.5 text-xs text-muted-foreground">
                    Sin permisos asignados
                  </p>
                )}

                <DropdownMenuSeparator />

                <DropdownMenuItem disabled>
                  <UserCircle />
                  <span>Mi perfil</span>
                  <ComingSoonBadge />
                </DropdownMenuItem>
                <DropdownMenuItem disabled>
                  <Settings />
                  <span>Preferencias</span>
                  <ComingSoonBadge />
                </DropdownMenuItem>

                <DropdownMenuSeparator />

                <DropdownMenuItem
                  variant="destructive"
                  onSelect={(e) => {
                    e.preventDefault()
                    void logout()
                  }}
                >
                  <LogOut />
                  <span>Cerrar sesion</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </header>
  )
}
