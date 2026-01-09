import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import { Newspaper, Clock, ExternalLink } from 'lucide-react'

export const NewsPage: React.FC = () => {
  const dispatch = useDispatch()
  // Mock news data for now - can be connected to actual news API later
  const newsItems = [
    {
      id: 1,
      title: 'Market Opens Strong on Positive Economic Indicators',
      summary: 'Indian markets opened higher today following better-than-expected GDP data and positive global cues.',
      source: 'Economic Times',
      timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      sentiment: 'positive',
      url: '#'
    },
    {
      id: 2,
      title: 'RBI Maintains Status Quo on Interest Rates',
      summary: 'The Reserve Bank of India kept the repo rate unchanged at 6.5%, in line with market expectations.',
      source: 'Business Standard',
      timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
      sentiment: 'neutral',
      url: '#'
    },
    {
      id: 3,
      title: 'BANKNIFTY Sees Increased Volatility',
      summary: 'Banking sector stocks experience heightened volatility amid mixed quarterly results and sector rotation.',
      source: 'Moneycontrol',
      timestamp: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
      sentiment: 'neutral',
      url: '#'
    }
  ]

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'positive':
        return 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20'
      case 'negative':
        return 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20'
      default:
        return 'text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-700'
    }
  }

  const formatTimeAgo = (timestamp: string) => {
    const now = Date.now()
    const then = new Date(timestamp).getTime()
    const diffMs = now - then
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 60) {
      return `${diffMins} minutes ago`
    } else if (diffHours < 24) {
      return `${diffHours} hours ago`
    } else {
      return `${diffDays} days ago`
    }
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Market News
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Latest financial news and market updates
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full text-sm font-medium">
            <Newspaper className="inline w-4 h-4 mr-1" />
            News Feed Active
          </div>
        </div>
      </div>

      {/* News Items List */}
      <div className="space-y-4">
        {newsItems.map((item) => (
          <div
            key={item.id}
            className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-2">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {item.title}
                  </h3>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSentimentColor(item.sentiment)}`}>
                    {item.sentiment}
                  </span>
                </div>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  {item.summary}
                </p>
                <div className="flex items-center space-x-4 text-sm text-gray-500 dark:text-gray-400">
                  <div className="flex items-center space-x-1">
                    <Newspaper className="w-4 h-4" />
                    <span>{item.source}</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Clock className="w-4 h-4" />
                    <span>{formatTimeAgo(item.timestamp)}</span>
                  </div>
                </div>
              </div>
              <a
                href={item.url}
                className="ml-4 p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                aria-label="Read full article"
              >
                <ExternalLink className="w-5 h-5" />
              </a>
            </div>
          </div>
        ))}
      </div>

      {/* Empty State (if no news) */}
      {newsItems.length === 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-12 text-center">
          <Newspaper className="w-16 h-16 mx-auto mb-4 text-gray-400" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            No News Available
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            Check back later for the latest market news and updates.
          </p>
        </div>
      )}
    </div>
  )
}
