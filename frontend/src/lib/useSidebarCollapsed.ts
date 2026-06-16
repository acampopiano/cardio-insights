import { useCallback, useEffect, useState } from "react"

const STORAGE_KEY = "cardio_insights.sidebar.collapsed"

function readStored(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true"
  } catch {
    return false
  }
}

export function useSidebarCollapsed(): [boolean, () => void, (value: boolean) => void] {
  const [collapsed, setCollapsed] = useState<boolean>(readStored)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(collapsed))
    } catch {
      /* swallow: localStorage may not be available */
    }
  }, [collapsed])

  const toggle = useCallback(() => {
    setCollapsed((prev) => !prev)
  }, [])

  return [collapsed, toggle, setCollapsed]
}
