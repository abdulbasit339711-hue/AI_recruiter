import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-10 w-full rounded-lg border border-border bg-foreground/[0.03] px-3 py-2 text-sm outline-none focus:border-ring focus:ring-1 focus:ring-ring disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
