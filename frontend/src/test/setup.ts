import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement scrolling; tests spy on this when they care.
window.scrollTo = () => {}
