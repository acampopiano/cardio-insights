import { describe, expect, it } from "vitest"

import { cn, getInitials } from "./utils"

describe("cn", () => {
  it("mergea clases de Tailwind", () => {
    const hidden = false as boolean
    expect(cn("px-2", "px-4")).toContain("px-4")
    expect(cn("text-sm", hidden && "hidden", "font-bold")).toContain("font-bold")
  })
})

describe("getInitials", () => {
  it("devuelve ?? para vacío", () => {
    expect(getInitials(null)).toBe("??")
    expect(getInitials("")).toBe("??")
    expect(getInitials("Dr.")).toBe("??")
  })

  it("toma iniciales filtrando títulos", () => {
    expect(getInitials("Dr. Ana Pereira")).toBe("AP")
    expect(getInitials("Ana")).toBe("AN")
    expect(getInitials("juan carlos")).toBe("JC")
  })
})
