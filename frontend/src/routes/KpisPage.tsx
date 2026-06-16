import { FeatureStub } from "@/routes/FeatureStub"
import { getNavItem } from "@/lib/navigation"

export function KpisPage() {
  const item = getNavItem("/kpis")!
  return <FeatureStub item={item} />
}
