import React from 'react'
import { useGetRecentTradesQuery } from '../../api/dashboardApi'

export const RecentTradesWidget: React.FC = () => {
  const { data = [], isLoading, isError, isFetching } = useGetRecentTradesQuery({ limit: 20 })

  if (isLoading) {
    return (
      <section aria-labelledby="recent-trades-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="recent-trades-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Recent Trades</h3>
        <div className="mt-4 animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-2"></div>
          <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </section>
    )
  }

  if (isError) {
    return (
      <section aria-labelledby="recent-trades-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="recent-trades-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Recent Trades</h3>
        <div className="mt-4 text-sm text-gray-500">Unable to load recent trades</div>
      </section>
    )
  }

  return (
    <section aria-labelledby="recent-trades-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between">
        <h3 id="recent-trades-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Recent Trades</h3>
        {isFetching && <span className="text-xs text-gray-500">Refreshing…</span>}
      </div>

      {data.length === 0 ? (
        <div className="mt-4 text-sm text-gray-500">No trades yet</div>
      ) : (
        <ul className="mt-3 space-y-2 max-h-56 overflow-auto" aria-live="polite">
          {data.map((t: any) => (
            <li key={t.id} className="flex items-center justify-between p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700">
              <div>
                <div className="text-sm font-medium text-gray-900 dark:text-white">{t.instrument}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">{t.side} {t.quantity} @ ₹{Number(t.price).toFixed(2)}</div>
                {t.signal_id && (
                  <div className="mt-1 text-xs text-gray-400 dark:text-gray-500 flex items-center gap-2">
                    <span className="font-mono">Signal: {String(t.signal_id).slice(0,8)}</span>
                    <button
                      onClick={() => navigator.clipboard?.writeText(String(t.signal_id))}
                      className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded"
                      title="Copy signal id"
                    >Copy</button>
                  </div>
                )}
              </div>
              <div className={`text-sm font-medium ${t.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>₹{Number(t.pnl).toFixed(2)}</div>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 text-xs text-gray-500">Showing latest {data.length} trades</div>
    </section>
  )
}
