import { FeatureStub } from "@/routes/FeatureStub"
import { getNavItem } from "@/lib/navigation"

export function AgentePage() {
  const item = getNavItem("/agente")!
  return <FeatureStub item={item} />
}
