import { Link } from "react-router-dom"
import { ArrowLeft, Construction } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { NavItem } from "@/lib/navigation"

interface FeatureStubProps {
  item: NavItem
}

export function FeatureStub({ item }: FeatureStubProps) {
  const Icon = item.icon

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 lg:py-10">
      <div className="mb-6">
        <Button
          asChild
          variant="ghost"
          size="sm"
          className="-ml-2 text-muted-foreground hover:text-foreground"
        >
          <Link to="/dashboard">
            <ArrowLeft className="size-4" />
            Volver al inicio
          </Link>
        </Button>
      </div>

      <Card>
        <CardHeader className="gap-3">
          <div className="flex items-center gap-3">
            <div
              className="grid size-12 place-items-center rounded-xl bg-[var(--color-incc-primary)]/10 text-[var(--color-incc-primary)]"
              aria-hidden="true"
            >
              <Icon className="size-6" />
            </div>
            <div className="space-y-1">
              <CardTitle className="text-2xl">{item.label}</CardTitle>
              <p className="text-sm text-muted-foreground">{item.description}</p>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          <div className="flex items-start gap-3 rounded-lg border border-dashed border-[var(--color-incc-primary)]/40 bg-[var(--color-incc-primary)]/5 p-4">
            <Construction
              className="mt-0.5 size-5 shrink-0 text-[var(--color-incc-primary)]"
              aria-hidden="true"
            />
            <div className="space-y-1">
              <p className="text-sm font-medium">En desarrollo</p>
              {item.comingSoonHint && (
                <p className="text-sm text-muted-foreground">
                  {item.comingSoonHint}
                </p>
              )}
            </div>
          </div>

          {item.features && item.features.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Que vamos a incluir
              </h3>
              <ul className="grid gap-2 sm:grid-cols-2">
                {item.features.map((feature) => (
                  <li
                    key={feature}
                    className="flex items-start gap-2 rounded-md border bg-muted/40 px-3 py-2 text-sm"
                  >
                    <span
                      className="mt-1.5 size-1.5 shrink-0 rounded-full bg-[var(--color-incc-primary)]"
                      aria-hidden="true"
                    />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
