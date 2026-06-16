import { Moon, Sun } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useTheme } from "@/lib/useTheme"
import { cn } from "@/lib/utils"

interface ThemeToggleProps {
  className?: string
  variant?: "default" | "header"
}

export function ThemeToggle({
  className,
  variant = "default",
}: ThemeToggleProps) {
  const { theme, toggle } = useTheme()
  const isDark = theme === "dark"

  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      aria-label={
        isDark ? "Cambiar a modo claro" : "Cambiar a modo oscuro"
      }
      title={isDark ? "Modo claro" : "Modo oscuro"}
      onClick={toggle}
      className={cn(
        "relative overflow-hidden",
        variant === "header" &&
          "border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white",
        className
      )}
    >
      <Sun
        className={cn(
          "size-4 transition-all duration-200",
          isDark ? "-rotate-90 scale-0 opacity-0" : "rotate-0 scale-100 opacity-100"
        )}
      />
      <Moon
        className={cn(
          "absolute size-4 transition-all duration-200",
          isDark ? "rotate-0 scale-100 opacity-100" : "rotate-90 scale-0 opacity-0"
        )}
      />
    </Button>
  )
}
