// Small line icons for the "how it works" steps.
export function NotebookIcon() {
  return (
    <svg className="hh-step-icon" viewBox="0 0 48 48" aria-hidden="true">
      <rect x="10" y="6" width="28" height="36" rx="4" />
      <line x1="17" y1="16" x2="31" y2="16" />
      <line x1="17" y1="24" x2="31" y2="24" />
      <line x1="17" y1="32" x2="26" y2="32" />
    </svg>
  )
}

export function TrendLensIcon() {
  return (
    <svg className="hh-step-icon" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="21" cy="21" r="13" />
      <line x1="31" y1="31" x2="41" y2="41" />
      <polyline points="13,25 18,19 23,23 29,15" />
    </svg>
  )
}

export function BalanceIcon() {
  return (
    <svg className="hh-step-icon" viewBox="0 0 48 48" aria-hidden="true">
      <line x1="24" y1="8" x2="24" y2="40" />
      <line x1="10" y1="14" x2="38" y2="14" />
      <path d="M10 14 L4 28 H16 Z" />
      <path d="M38 14 L32 28 H44 Z" />
      <line x1="16" y1="40" x2="32" y2="40" />
    </svg>
  )
}
