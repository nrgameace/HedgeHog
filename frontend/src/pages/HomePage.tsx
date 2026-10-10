type HomePageProps = { onStart: () => void }

function HomePage({ onStart }: HomePageProps) {
  return (
    <section className="home">
      <h1>Hedgehog</h1>
      <p>Hedge your business against the market factors that affect it.</p>
      <button type="button" className="primary" onClick={onStart}>Start</button>
    </section>
  )
}

export default HomePage
