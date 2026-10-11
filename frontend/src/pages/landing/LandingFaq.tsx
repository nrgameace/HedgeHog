const FAQS = [
  {
    question: 'Is this gambling?',
    answer: 'No more than insurance is. A bet adds risk; a hedge offsets a risk you already have. Every position is tied to something that hurts your business, so when that bad thing happens, the payout helps cover it.',
  },
  {
    question: 'What is Kalshi?',
    answer: 'Kalshi is a U.S. exchange, regulated by the CFTC, where people trade on the outcomes of real-world events. Hedgehog looks through its markets to find the ones that match your risks.',
  },
  {
    question: 'Does Hedgehog transfer money?',
    answer: 'No; Hedgehog recommends a plan and simulates how it will increase your margins. No trades are placed and no money changes hands until you go to Kalshi and place them yourself.',
  },
  {
    question: 'How much does it cost me?',
    answer: 'You decide. Tell us how much you can set aside for protection, and every position is sized to fit within that budget.',
  },
]

// Accordion of common questions, using native <details> so it works without extra state.
function LandingFaq() {
  return (
    <div className="landing-faq">
      {FAQS.map(({ question, answer }) => (
        <details key={question} className="landing-faq__item">
          <summary>{question}</summary>
          <p>{answer}</p>
        </details>
      ))}
    </div>
  )
}

export default LandingFaq
