export const MAX_CSV_BYTES = 4 * 1024 * 1024
export const MISSING_FINANCIALS_MESSAGE = 'Upload your financials CSV so we can simulate your trades.'

// The CSV's contents are deliberately not checked here: the backend finds the month and profit columns.
export function validateFinancialsFile(file: File | null, required: boolean): string | null {
  if (!file) return required ? MISSING_FINANCIALS_MESSAGE : null
  if (!file.name.toLowerCase().endsWith('.csv')) return 'The file must be a CSV (.csv).'
  if (file.size === 0) return 'The file is empty.'
  if (file.size > MAX_CSV_BYTES) return 'The file is too large (max 4 MB).'
  return null
}
