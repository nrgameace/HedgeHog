// Fraction of the scrollable page the reader has passed, clamped to [0, 1].
export function scrollProgress(scrollY: number, pageHeight: number, viewportHeight: number) {
  const scrollableDistance = pageHeight - viewportHeight
  if (scrollableDistance <= 0) return 0
  return Math.min(Math.max(scrollY / scrollableDistance, 0), 1)
}
