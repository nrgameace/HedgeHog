type Leaf = { left: number, delay: number, duration: number, size: number, tone: string }

const LEAVES: Leaf[] = [
  { left: 6, delay: 0, duration: 17, size: 22, tone: 'pumpkin' },
  { left: 18, delay: 6, duration: 21, size: 16, tone: 'mustard' },
  { left: 33, delay: 11, duration: 19, size: 20, tone: 'cocoa' },
  { left: 52, delay: 3, duration: 23, size: 14, tone: 'tan' },
  { left: 67, delay: 9, duration: 18, size: 24, tone: 'pumpkin' },
  { left: 80, delay: 14, duration: 22, size: 16, tone: 'mustard' },
  { left: 92, delay: 5, duration: 20, size: 18, tone: 'cocoa' },
]

// Decorative leaves drifting down behind the page content.
function FallingLeaves() {
  return (
    <div className="hh-leaves" aria-hidden="true">
      {LEAVES.map(({ left, delay, duration, size, tone }) => (
        <svg
          key={left}
          className={`hh-leaf hh-fill--${tone}`}
          viewBox="0 0 24 24"
          style={{ left: `${left}%`, width: size, height: size, animationDelay: `${-delay}s`, animationDuration: `${duration}s` }}
        >
          <path d="M12 2 C 19 6, 21 14, 12 22 C 3 14, 5 6, 12 2 Z" />
          <path className="hh-leaf__vein" d="M12 4 V21" />
        </svg>
      ))}
    </div>
  )
}

export default FallingLeaves
