import { apiRequest } from "@/lib/api"

export interface EmbedTokenResponse {
  iframe_url: string
  dashboard_id: number
  expires_in: number
}

export function getMetabaseEmbedUrl(dashboardId?: number) {
  const query =
    dashboardId !== undefined ? `?dashboard_id=${dashboardId}` : ""
  return apiRequest<EmbedTokenResponse>(`/metabase/embed-token${query}`, {
    method: "GET",
  })
}
