import { afterEach, describe, expect, it, vi } from "vitest"

import * as api from "@/lib/api"
import { getMetabaseEmbedUrl } from "./metabaseApi"

describe("metabaseApi", () => {
  afterEach(() => vi.restoreAllMocks())

  it("pide embed token con y sin dashboard", async () => {
    const spy = vi.spyOn(api, "apiRequest").mockResolvedValue({
      iframe_url: "http://x",
      dashboard_id: 2,
      expires_in: 60,
    })
    await getMetabaseEmbedUrl()
    await getMetabaseEmbedUrl(42)
    expect(spy).toHaveBeenCalledWith("/metabase/embed-token", { method: "GET" })
    expect(spy).toHaveBeenCalledWith("/metabase/embed-token?dashboard_id=42", {
      method: "GET",
    })
  })
})
