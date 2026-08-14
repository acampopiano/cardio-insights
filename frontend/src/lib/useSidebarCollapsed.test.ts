import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { useSidebarCollapsed } from "./useSidebarCollapsed"

describe("useSidebarCollapsed", () => {
  it("lee, togglea y persiste", () => {
    localStorage.setItem("cardio_insights.sidebar.collapsed", "true")
    const { result } = renderHook(() => useSidebarCollapsed())
    expect(result.current[0]).toBe(true)

    act(() => {
      result.current[1]()
    })
    expect(result.current[0]).toBe(false)
    expect(localStorage.getItem("cardio_insights.sidebar.collapsed")).toBe("false")

    act(() => {
      result.current[2](true)
    })
    expect(result.current[0]).toBe(true)
  })
})
