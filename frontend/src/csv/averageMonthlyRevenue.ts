function splitCsvLine(line: string): string[] {
  const cells: string[] = []
  let current = ''
  let inQuotes = false
  for (const char of line) {
    if (char === '"') inQuotes = !inQuotes
    else if (char === ',' && !inQuotes) {
      cells.push(current)
      current = ''
    } else current += char
  }
  cells.push(current)
  return cells.map((cell) => cell.trim())
}

function findRevenueColumn(headers: string[]): number {
  const names = headers.map((name) => name.toLowerCase().replace(/[\s_]+/g, ' '))
  const exact = names.findIndex((name) => name === 'total revenue' || name === 'revenue')
  return exact !== -1 ? exact : names.findIndex((name) => name.includes('revenue'))
}

// Reads the total revenue column (or else the first column mentioning "revenue"); cells that aren't numbers are skipped.
export function averageMonthlyRevenue(csvText: string): number | null {
  const [header, ...rows] = csvText.split(/\r?\n/).filter((line) => line.trim() !== '')
  if (!header) return null
  const column = findRevenueColumn(splitCsvLine(header))
  if (column === -1) return null
  const values = rows
    .map((row) => Number(splitCsvLine(row)[column]?.replace(/[$,\s]/g, '')))
    .filter((value) => Number.isFinite(value) && value !== 0)
  if (values.length === 0) return null
  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
}
