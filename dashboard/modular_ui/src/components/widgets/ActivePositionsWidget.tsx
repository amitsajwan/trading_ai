import React from 'react'
import { TrendingUp, TrendingDown, DollarSign, PieChart } from 'lucide-react'

export const ActivePositionsWidget: React.FC = () => {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Active Positions</h3>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          0 positions
        </div>
      </div>

      {/* No Positions State */}
      <div className="text-center py-8">
        <PieChart className="w-12 h-12 mx-auto mb-4 text-gray-400" />
        <p className="text-gray-600 dark:text-gray-400 mb-2">No active positions</p>
        <p className="text-sm text-gray-500 dark:text-gray-500">
          Positions will appear here when trades are executed
        </p>
      </div>

      {/* Placeholder for future positions */}
      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 border-2 border-dashed border-gray-200 dark:border-gray-600">
        <div className="text-center text-gray-400">
          <TrendingUp className="w-8 h-8 mx-auto mb-2" />
          <p className="text-sm">Position data will be displayed here</p>
        </div>
      </div>
    </div>
  )
}