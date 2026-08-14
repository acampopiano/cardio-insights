import { afterEach, describe, expect, it, vi } from "vitest"

import * as api from "@/lib/api"
import { listModels, predict } from "./predictionsApi"

describe("predictionsApi", () => {
  afterEach(() => vi.restoreAllMocks())

  it("lista modelos y predice por cohort", async () => {
    const spy = vi.spyOn(api, "apiRequest").mockResolvedValue([])
    await listModels()
    await predict("ptca", { edad: 70 })
    expect(spy).toHaveBeenCalledWith("/predictions/models", { method: "GET" })
    expect(spy).toHaveBeenCalledWith("/predictions/ptca", {
      method: "POST",
      body: { values: { edad: 70 } },
    })
  })
})
