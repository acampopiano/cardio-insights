import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { useTheme } from "./useTheme"

describe("useTheme", () => {
  it("persiste y alterna tema", () => {
    const { result } = renderHook(() => useTheme())

    act(() => {
      result.current.setTheme("dark")
    })
    expect(result.current.theme).toBe("dark")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
    expect(localStorage.getItem("cardio_insights.theme")).toBe("dark")

    act(() => {
      result.current.toggle()
    })
    expect(result.current.theme).toBe("light")
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })
})
