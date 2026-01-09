import React from 'react'

interface ErrorBoundaryState {
  hasError: boolean
  error?: Error | null
}

export class ErrorBoundary extends React.Component<{}, ErrorBoundaryState> {
  constructor(props: {}) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: any) {
    // TODO: send to logging service
    console.error('Uncaught error:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div role="alert" className="p-6 bg-red-50 dark:bg-red-900 rounded">
          <h2 className="text-lg font-semibold text-red-800 dark:text-red-200">Something went wrong</h2>
          <p className="text-sm text-red-700 dark:text-red-100 mt-2">An unexpected error occurred. Please refresh the page or contact support if the problem persists.</p>
        </div>
      )
    }

    return this.props.children
  }
}
