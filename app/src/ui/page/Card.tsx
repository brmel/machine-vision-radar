import { type HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: "div" | "article" | "li";
  interactive?: boolean;
}

export const Card = ({ as: Element = "div", interactive = false, className = "", children, ...props }: CardProps) => (
  <Element className={`p-3 rounded-card border border-line bg-surface transition-colors ${interactive
    ? "hover:border-line-hover" : ""} ${className}`} {...props}>
    {children}
  </Element>
);
