const UNHEDGED_PATH = 'M24 118 L54 58 L84 150 L114 76 L144 166 L174 66 L204 142 L234 52 L264 152 L294 88 L318 128'
const HEDGED_PATH = 'M24 112 C 70 98, 112 120, 160 106 S 262 96, 318 104'

// Revenue swinging wildly on its own vs. evened out with a hedge; both lines draw in on reveal.
function SteadyCashflowGraphic() {
  return (
    <svg className="hh-graphic hh-cashflow" viewBox="0 0 340 236" role="img" aria-label="Chart: revenue swings sharply without a hedge and stays steady with hedgehog">
      <rect className="hh-cashflow__card" x="4" y="4" width="332" height="228" rx="18" />
      {[58, 108, 158].map((y) => <line key={y} className="hh-cashflow__grid" x1="24" y1={y} x2="318" y2={y} />)}
      <path className="hh-cashflow__line hh-cashflow__line--unhedged" d={UNHEDGED_PATH} pathLength={1} />
      <path className="hh-cashflow__line hh-cashflow__line--hedged" d={HEDGED_PATH} pathLength={1} />
      <g className="hh-cashflow__legend">
        <line className="hh-cashflow__line--unhedged" x1="34" y1="204" x2="54" y2="204" />
        <text x="60" y="208">Without a hedge</text>
        <line className="hh-cashflow__line--hedged" x1="184" y1="204" x2="204" y2="204" />
        <text x="210" y="208">With hedgehog</text>
      </g>
    </svg>
  )
}

export default SteadyCashflowGraphic
