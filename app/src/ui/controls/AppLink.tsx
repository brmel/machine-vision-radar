import { type FC, type MouseEvent, type ReactNode } from "react";

interface AppLinkProps {
  href: string;
  onOpen: () => void;
  className: string;
  children: ReactNode;
}

export const AppLink: FC<AppLinkProps> = ({ href, onOpen, className, children }) => (
  <a
    href={href}
    className={className}
    onClick={(e: MouseEvent<HTMLAnchorElement>) => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      onOpen();
    }}
  >
    {children}
  </a>
);
