import React from 'react'
import { useGetPortfolioQuery } from '../../api/dashboardApi'
import { Activity } from 'lucide-react'

export const PortfolioWidget: React.FC = () => {
  const { data, error, isLoading, isFetching } = useGetPortfolioQuery()

  if (isLoading) {
    return (
      <section aria-labelledby="portfolio-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="portfolio-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Portfolio</h3>
        <div className="mt-4 animate-pulse">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-3"></div>
          <div className="h-40 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </section>
    )
  }

  if (error || !data) {
    return (
      <section aria-labelledby="portfolio-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="portfolio-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Portfolio</h3>
        <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
          <Activity className="w-6 h-6 inline-block mr-2 opacity-50" />
          Unable to load portfolio
        </div>
      </section>
    )
  }

  const positions = data.positions ?? []

  return (
    <section aria-labelledby="portfolio-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between">
        <h3 id="portfolio-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Portfolio</h3>
        {isFetching && <span className="text-xs text-gray-500">Refreshing…</span>}
      </div>

      {positions.length === 0 ? (
        <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">No positions</div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm" role="table" aria-label="portfolio table">
            <thead>
              <tr>
                <th className="font-medium text-gray-600 dark:text-gray-300">Instrument</th>
                <th className="font-medium text-gray-600 dark:text-gray-300">Qty</th>
                <th className="font-medium text-gray-600 dark:text-gray-300">Avg Price</th>
                <th className="font-medium text-gray-600 dark:text-gray-300">P&L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p: any) => (
                <tr key={p.id} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="py-2">{p.instrument}</td>
                  <td className="py-2">{p.quantity}</td>
                  <td className="py-2">₹{Number(p.avg_price).toFixed(2)}</td>
                  <td className={`py-2 ${p.unrealized_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>₹{Number(p.unrealized_pl).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-3 text-xs text-gray-500">Updated: {new Date(data.updated_at ?? Date.now()).toLocaleTimeString()}</div>
    </section>
  )
}
