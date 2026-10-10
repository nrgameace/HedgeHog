import type { CSSProperties } from 'react'

const RAINDROP_XS = [108, 124, 140, 156, 172, 188, 204]
const AWNING_STRIPES = 7

// A storefront under a passing rain cloud, with the sun waiting behind it.
function RainyDayGraphic() {
  return (
    <svg className="hh-graphic hh-rainy" viewBox="0 0 320 250" role="img" aria-label="A rain cloud passing over a small ice cream shop">
      <circle className="hh-rainy__sun" cx="226" cy="74" r="34" />
      <g className="hh-rainy__cloud">
        <circle cx="122" cy="84" r="28" />
        <circle cx="158" cy="66" r="38" />
        <circle cx="198" cy="86" r="26" />
        <rect x="96" y="84" width="126" height="28" rx="14" />
      </g>
      {RAINDROP_XS.map((x, i) => (
        <line key={x} className="hh-rainy__drop" x1={x} y1="122" x2={x - 4} y2="134" style={{ '--i': i } as CSSProperties} />
      ))}
      <rect className="hh-rainy__wall" x="72" y="160" width="176" height="76" rx="4" />
      {Array.from({ length: AWNING_STRIPES }, (_, i) => (
        <rect key={i} className={i % 2 ? 'hh-rainy__stripe-light' : 'hh-rainy__stripe-dark'} x={62 + i * 28} y="146" width="28" height="22" />
      ))}
      {Array.from({ length: AWNING_STRIPES }, (_, i) => (
        <circle key={i} className={i % 2 ? 'hh-rainy__stripe-light' : 'hh-rainy__stripe-dark'} cx={76 + i * 28} cy="168" r="14" />
      ))}
      <rect className="hh-rainy__window" x="90" y="188" width="76" height="40" rx="3" />
      <path className="hh-rainy__cone" d="M118 206 L128 224 L138 206 Z" />
      <circle className="hh-rainy__scoop" cx="128" cy="202" r="9" />
      <rect className="hh-rainy__door" x="186" y="186" width="42" height="50" rx="3" />
      <line className="hh-ground" x1="30" y1="236" x2="290" y2="236" />
    </svg>
  )
}

export default RainyDayGraphic
