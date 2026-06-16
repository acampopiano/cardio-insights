import { cn } from "@/lib/utils"

interface BrandMarkProps {
  className?: string
  size?: number
  showText?: boolean
}

export function BrandMark({
  className,
  size = 48,
  showText = true,
}: BrandMarkProps) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 64 64"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Logo INCC"
        role="img"
      >
        <path
          d="M32 54 C 12 40, 8 24, 18 17 C 25 12, 30 16, 32 21 C 34 16, 39 12, 46 17 C 56 24, 52 40, 32 54 Z"
          fill="var(--color-incc-accent)"
          opacity="0.95"
        />
        <polyline
          points="10 32, 22 32, 26 24, 30 40, 34 28, 38 32, 54 32"
          fill="none"
          stroke="#ffffff"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {showText && (
        <div className="leading-tight">
          <p className="text-base font-bold tracking-tight">Cardio Insights</p>
          <p className="text-xs text-current/70">INCC</p>
        </div>
      )}
    </div>
  )
}
