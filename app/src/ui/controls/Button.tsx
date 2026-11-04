import { type ButtonHTMLAttributes, type FC } from "react";

const SIZES = {
  sm: "gap-1.5 px-2.5 py-1 text-caption rounded-control",
  md: "gap-2 px-3.5 py-1.5 text-body rounded-control",
  lg: "gap-2 px-5 py-3.5 text-lead rounded-field",
} as const;

const VARIANTS = {
  primary: "bg-accent text-on-accent hover:bg-accent-hover active:bg-accent-active font-semibold shadow-control",
  secondary: "bg-raised text-fg hover:bg-raised-hover",
  outline: "border border-line-strong text-fg hover:bg-raised",
  ghost: "text-muted hover:text-fg hover:bg-raised/70",
} as const;

type Variant = keyof typeof VARIANTS;
type Size = keyof typeof SIZES;

export const buttonClass = (variant: Variant, size: Size): string =>
  `inline-flex items-center justify-center font-medium transition-colors whitespace-nowrap shrink-0 `
    + `disabled:opacity-50 disabled:pointer-events-none cursor-pointer ${SIZES[size]} ${VARIANTS[variant]}`;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button: FC<ButtonProps> = ({ variant = "secondary", size = "md", className = "", children, ...props }) => (
  <button className={`${buttonClass(variant, size)} ${className}`} {...props}>
    {children}
  </button>
);
