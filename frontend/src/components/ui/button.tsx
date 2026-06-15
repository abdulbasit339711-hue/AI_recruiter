import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "lg" | "sm";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    const sizes = {
      default: "h-10 px-4 py-2",
      lg: "h-12 px-6 text-base",
      sm: "h-8 px-3 text-sm",
    };
    const variants = {
      default: "bg-primary text-primary-foreground hover:opacity-90",
      outline: "border border-border bg-transparent text-foreground hover:bg-foreground/[0.06]",
      ghost: "bg-transparent text-foreground hover:bg-foreground/[0.06]",
      destructive: "bg-red-600 text-white hover:bg-red-700",
    };
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-md font-medium transition-colors disabled:opacity-50",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
