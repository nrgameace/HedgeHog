// Layered autumn hills along the bottom of the hero: the "steady ground" motif.
function RollingHills() {
  return (
    <svg className="hh-hills" viewBox="0 0 1440 220" preserveAspectRatio="none" aria-hidden="true">
      <path className="hh-hills__back" d="M0 120 C 240 40, 480 160, 720 100 S 1200 30, 1440 110 V220 H0 Z" />
      <path className="hh-hills__middle" d="M0 160 C 300 90, 560 190, 860 140 S 1280 100, 1440 150 V220 H0 Z" />
      <path className="hh-hills__front" d="M0 196 C 360 160, 720 220, 1080 186 S 1360 176, 1440 190 V220 H0 Z" />
    </svg>
  )
}

export default RollingHills
