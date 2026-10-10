import hedgehogLogo from '../assets/hedgehog-logo.png'

type PageHeaderProps = { onHome: () => void }

// Small logo + wordmark shown above the questionnaire and results pages; pressing it goes back home.
function PageHeader({ onHome }: PageHeaderProps) {
  return (
    <header className="page-header">
      <button type="button" className="page-header__home" aria-label="hedgehog: back to home" onClick={onHome}>
        <img className="page-header__logo" src={hedgehogLogo} alt="hedgehog logo" />
        <span className="page-header__wordmark">hedgehog</span>
      </button>
    </header>
  )
}

export default PageHeader
