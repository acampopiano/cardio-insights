import { Link } from "react-router-dom"
import { ArrowRight } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import type { NavItem } from "@/lib/navigation"
import { cn } from "@/lib/utils"

interface FeatureCardProps {
  item: NavItem
}

export function FeatureCard({ item }: FeatureCardProps) {
  const Icon = item.icon
  const isAvailable = item.available

  return (
    <Link
      to={item.path}
      className="group block rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-incc-primary)] focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <Card
        className={cn(
          "h-full gap-4 border-border/70 transition-all",
          "hover:-translate-y-0.5 hover:border-[var(--color-incc-primary)]/60 hover:shadow-md"
        )}
      >
        <CardContent className="flex h-full flex-col gap-4 p-5">
          <div className="flex items-start justify-between gap-3">
            <div
              className={cn(
                "grid size-11 shrink-0 place-items-center rounded-lg",
                "bg-[var(--color-incc-primary)]/10 text-[var(--color-incc-primary)]",
                "group-hover:bg-[var(--color-incc-primary)] group-hover:text-white",
                "transition-colors"
              )}
              aria-hidden="true"
            >
              <Icon className="size-5" />
            </div>

            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1",
                isAvailable
                  ? "bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300"
                  : "bg-muted text-muted-foreground ring-border"
              )}
            >
              {isAvailable ? "Disponible" : "Pronto"}
            </span>
          </div>

          <div className="flex-1 space-y-1.5">
            <h3 className="text-base font-semibold tracking-tight">
              {item.label}
            </h3>
            <p className="text-sm text-muted-foreground">{item.description}</p>
          </div>

          <div className="flex items-center gap-1.5 text-xs font-medium text-[var(--color-incc-primary)]">
            <span>{isAvailable ? "Abrir" : "Ver detalles"}</span>
            <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
