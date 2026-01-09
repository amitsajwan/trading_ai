import React from 'react'
import { Link } from 'react-router-dom'

export const NotFoundPage: React.FC = () => {
  return (
    <div className="py-16 text-center">
      <h1 className="text-4xl font-bold text-gray-900 dark:text-white">404</h1>
      <p className="mt-2 text-gray-600 dark:text-gray-400">Page not found</p>
      <div className="mt-6">
        <Link to="/" className="px-4 py-2 bg-primary-600 text-white rounded">Go back home</Link>
      </div>
    </div>
  )
}
