import { FeatureCard } from "@/components/FeatureCard"
import { useAuth } from "@/features/auth/useAuth"
import { NAV_ITEMS } from "@/lib/navigation"

export function HomePage() {
  const { user } = useAuth()
  const firstName =
    user?.full_name.split(" ").find((p) => !p.endsWith(".")) ?? ""

  const features = NAV_ITEMS.filter((item) => item.path !== "/dashboard")

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
      <header className="mb-8 space-y-1">
        <p className="text-sm font-medium text-[var(--color-incc-primary)]">
          Bienvenida{firstName ? `, ${firstName}` : ""}
        </p>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          Plataforma de analisis clinico
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Explora los reportes, KPIs, modelos predictivos y el asistente con IA
          que vamos a integrar para la actividad cardiovascular del INCC.
        </p>
      </header>

      <section aria-label="Herramientas disponibles">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Herramientas
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {features.map((item) => (
            <FeatureCard key={item.path} item={item} />
          ))}
        </div>
      </section>
    </div>
  )
}
