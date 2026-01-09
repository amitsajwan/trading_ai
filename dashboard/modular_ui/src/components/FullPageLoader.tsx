import React from 'react'

export const FullPageLoader: React.FC<{ message?: string }> = ({ message = 'Loading…' }) => {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-primary-300 border-t-transparent rounded-full animate-spin mx-auto mb-4" role="status" aria-label="loading" />
        <div className="text-sm text-gray-600 dark:text-gray-400">{message}</div>
      </div>
    </div>
  )
}
