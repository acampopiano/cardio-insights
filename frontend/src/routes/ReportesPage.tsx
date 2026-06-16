import { FeatureStub } from "@/routes/FeatureStub"
import { getNavItem } from "@/lib/navigation"

export function ReportesPage() {
  const item = getNavItem("/reportes")!
  return <FeatureStub item={item} />
}
