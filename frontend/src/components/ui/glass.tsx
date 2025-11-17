import * as React from "react"
import { cn } from "@/lib/utils"

interface GlassProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

export function Glass({ className, children, ...props }: GlassProps) {
  return (
    <div
      className={cn(
        "backdrop-blur-lg bg-gray-200/40 border border-white/20 rounded-2xl shadow-lg",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

