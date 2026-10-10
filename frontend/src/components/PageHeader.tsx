import hedgehogLogo from '../assets/hedgehog-logo.png'

// Small logo + wordmark shown above the questionnaire and results pages.
function PageHeader() {
  return (
    <header className="page-header">
      <img className="page-header__logo" src={hedgehogLogo} alt="hedgehog logo" />
      <span className="page-header__wordmark">hedgehog</span>
    </header>
  )
}

export default PageHeader
