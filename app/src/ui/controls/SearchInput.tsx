import { type FC, type InputHTMLAttributes } from "react";
import { Sparkles, X } from "lucide-react";

interface SearchInputProps extends InputHTMLAttributes<HTMLInputElement> {
  onClear: () => void;
  compact?: boolean;
  clearLabel: string;
}

export const SearchInput: FC<SearchInputProps> =
  ({ value, onClear, compact = false, className = "", placeholder, clearLabel, "aria-label": ariaLabel, ...props }) => (
  <div
    className={`relative flex items-center w-full bg-surface border-line-strong focus-within:border-focus `
      + `transition-colors ${compact ? "border rounded-control"
        : "max-w-2xl border-2 rounded-field shadow-field"} ${className}`}
  >
    <Sparkles className={`absolute text-muted pointer-events-none ${compact ? "left-3 w-4 h-4"
      : "left-4 w-5 h-5"}`}
      aria-hidden="true" />
    <input
      type="text"
      value={value}
      placeholder={placeholder}
      aria-label={ariaLabel ?? placeholder}
      className={`w-full pr-10 bg-transparent text-fg placeholder:text-muted focus:outline-none ${compact
        ? "py-2 pl-9 text-body" : "py-3.5 pl-12 text-lead"}`}
      {...props}
    />
    {value && (
      <button
        type="button"
        onClick={onClear}
        className="absolute right-3 p-1 text-muted hover:text-fg transition-colors cursor-pointer"
        aria-label={clearLabel}
      >
        <X className="w-5 h-5" aria-hidden="true" />
      </button>
    )}
  </div>
);
