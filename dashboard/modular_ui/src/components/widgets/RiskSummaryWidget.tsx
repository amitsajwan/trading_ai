import React from 'react'
import { Shield, AlertTriangle, TrendingUp, DollarSign } from 'lucide-react'

export const RiskSummaryWidget: React.FC = () => {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Risk Summary</h3>
        <div className="flex items-center space-x-2">
          <Shield className="w-4 h-4 text-green-500" />
          <span className="text-sm text-green-600 dark:text-green-400">Low Risk</span>
        </div>
      </div>

      {/* Risk Metrics Grid */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Portfolio Value</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">₹0</p>
            </div>
            <DollarSign className="w-6 h-6 text-green-500" />
          </div>
        </div>

        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Daily P&L</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">₹0</p>
            </div>
            <TrendingUp className="w-6 h-6 text-gray-500" />
          </div>
        </div>

        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Max Drawdown</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">0%</p>
            </div>
            <Shield className="w-6 h-6 text-blue-500" />
          </div>
        </div>

        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Margin Used</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">0%</p>
            </div>
            <AlertTriangle className="w-6 h-6 text-yellow-500" />
          </div>
        </div>
      </div>

      {/* Risk Status */}
      <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4">
        <div className="flex items-center space-x-3">
          <Shield className="w-6 h-6 text-green-600 dark:text-green-400" />
          <div>
            <p className="text-sm font-semibold text-green-900 dark:text-green-100">Risk Status: Healthy</p>
            <p className="text-xs text-green-700 dark:text-green-300">No active positions, all risk limits within bounds</p>
          </div>
        </div>
      </div>
    </div>
  )
}