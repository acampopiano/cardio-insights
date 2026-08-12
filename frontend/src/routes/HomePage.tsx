import { FeatureCard } from "@/components/FeatureCard"
import { PageShell } from "@/components/layout/PageShell"
import { useAuth } from "@/features/auth/useAuth"
import { getNavItemsForRole } from "@/lib/navigation"

export function HomePage() {
  const { user } = useAuth()
  const firstName =
    user?.full_name.split(" ").find((p) => !p.endsWith(".")) ?? ""

  const features = getNavItemsForRole(user?.role).filter(
    (item) => item.path !== "/dashboard"
  )

  return (
    <PageShell>
      <header className="mb-6 space-y-1">
        <p className="text-sm font-medium text-[var(--color-incc-primary)]">
          Bienvenido{firstName ? `, ${firstName}` : ""}
        </p>
        <h1 className="text-xl font-semibold">
          Plataforma de analisis clinico
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Explora los KPIs, modelos predictivos y el asistente con IA para la
          actividad cardiovascular del INCC.
        </p>
      </header>

      <section aria-label="Herramientas disponibles">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Herramientas
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {features.map((item) => (
            <FeatureCard key={item.path} item={item} />
          ))}
        </div>
      </section>
    </PageShell>
  )
}
