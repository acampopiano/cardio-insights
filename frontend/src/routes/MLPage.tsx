import { FeatureStub } from "@/routes/FeatureStub"
import { getNavItem } from "@/lib/navigation"

export function MLPage() {
  const item = getNavItem("/ml")!
  return <FeatureStub item={item} />
}
