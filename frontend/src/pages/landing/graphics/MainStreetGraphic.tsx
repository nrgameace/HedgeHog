import type { CSSProperties } from 'react'
import hedgehogLogo from '../assets/hedgehog-logo.png'

type Storefront = { x: number, width: number, height: number, tone: string }

const STOREFRONTS: Storefront[] = [
  { x: 20, width: 84, height: 112, tone: 'pumpkin' },
  { x: 110, width: 70, height: 140, tone: 'bark' },
  { x: 186, width: 92, height: 100, tone: 'mustard' },
  { x: 284, width: 74, height: 126, tone: 'cocoa' },
]
const GROUND_Y = 214

// A row of neighborhood shops rising into place, with a hedgehog out front.
function MainStreetGraphic() {
  return (
    <svg className="hh-graphic hh-street" viewBox="0 0 500 236" role="img" aria-label="A row of neighborhood storefronts beside an autumn tree">
      {STOREFRONTS.map(({ x, width, height, tone }, i) => {
        const top = GROUND_Y - height
        return (
          <g key={x} className="hh-street__shop" style={{ '--i': i } as CSSProperties}>
            <rect className="hh-street__wall" x={x} y={top} width={width} height={height} rx="4" />
            <rect className={`hh-street__awning hh-fill--${tone}`} x={x - 4} y={top + height * 0.42} width={width + 8} height="14" rx="3" />
            <rect className="hh-street__window" x={x + 10} y={top + 14} width={width - 20} height={height * 0.28} rx="3" />
            <rect className={`hh-street__door hh-fill--${tone}`} x={x + width / 2 - 11} y={GROUND_Y - 34} width="22" height="34" rx="2" />
          </g>
        )
      })}
      <g className="hh-street__tree">
        <rect className="hh-fill--bark" x="389" y="150" width="8" height="64" rx="3" />
        <circle className="hh-fill--pumpkin" cx="393" cy="128" r="30" />
        <circle className="hh-fill--mustard" cx="376" cy="146" r="18" />
        <circle className="hh-fill--cocoa" cx="410" cy="142" r="16" />
      </g>
      <image className="hh-street__hedgehog" href={hedgehogLogo} x="438" y="180" width="48" height="36" />
      <line className="hh-ground" x1="8" y1={GROUND_Y} x2="492" y2={GROUND_Y} />
    </svg>
  )
}

export default MainStreetGraphic
