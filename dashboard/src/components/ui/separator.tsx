"use client"

import * as React from "react"

export interface SeparatorProps extends React.HTMLAttributes<HTMLDivElement> {}

const Separator = React.forwardRef<HTMLDivElement, SeparatorProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={`shrink-0 bg-border h-[1px] w-full ${className || ''}`}
      {...props}
    />
  )
)
Separator.displayName = "Separator"

export { Separator }
