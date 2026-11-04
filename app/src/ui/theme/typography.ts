export const TYPE = {
  display: "text-display sm:text-display-md lg:text-display-lg font-heading tracking-tight text-fg",
  title: "text-title font-heading tracking-tight break-words text-fg",
  section: "text-section font-heading tracking-tight text-fg",
  label: "text-body font-heading text-fg",
} as const;

export const CONTROL =
  "w-full min-w-0 rounded-control border border-line-strong bg-surface px-3 py-2 text-body text-fg "
    + "placeholder:text-muted focus:outline-none focus-visible:border-focus";
