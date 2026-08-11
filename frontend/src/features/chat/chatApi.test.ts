import { afterEach, describe, expect, it, vi } from "vitest"

import * as api from "@/lib/api"
import { askChat } from "./chatApi"

describe("chatApi", () => {
  afterEach(() => vi.restoreAllMocks())

  it("posta la pregunta al endpoint /chat", async () => {
    const spy = vi.spyOn(api, "apiRequest").mockResolvedValue({
      question: "q",
      answer: "a",
      resolved: true,
      sql: null,
      rows: [],
      row_count: 0,
      error: null,
    })

    await askChat({ question: "cuantas cirugias?", history: [] })
    expect(spy).toHaveBeenCalledWith("/chat", {
      method: "POST",
      body: { question: "cuantas cirugias?", history: [] },
    })
  })
})
