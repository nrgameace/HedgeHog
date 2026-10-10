export const MAX_CSV_BYTES = 5 * 1024 * 1024

// The upload is optional while the app runs on simulated data, and the CSV's contents
// are deliberately not checked: any shape of financials is accepted.
export function validateFinancialsFile(file: File | null): string | null {
  if (!file) return null
  if (!file.name.toLowerCase().endsWith('.csv')) return 'The file must be a CSV (.csv).'
  if (file.size === 0) return 'The file is empty.'
  if (file.size > MAX_CSV_BYTES) return 'The file is too large (max 5 MB).'
  return null
}
