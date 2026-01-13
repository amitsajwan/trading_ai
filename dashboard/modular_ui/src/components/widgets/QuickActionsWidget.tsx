import React from 'react'
import { Zap, Play, Pause, Settings, RefreshCw } from 'lucide-react'

export const QuickActionsWidget: React.FC = () => {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Quick Actions</h3>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          Trading Controls
        </div>
      </div>

      {/* Action Buttons Grid */}
      <div className="grid grid-cols-2 gap-3">
        <button className="flex flex-col items-center justify-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors group">
          <Play className="w-6 h-6 text-blue-600 dark:text-blue-400 mb-2 group-hover:scale-110 transition-transform" />
          <span className="text-sm font-medium text-blue-900 dark:text-blue-100">Start Trading</span>
        </button>

        <button className="flex flex-col items-center justify-center p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg hover:bg-yellow-100 dark:hover:bg-yellow-900/30 transition-colors group">
          <Pause className="w-6 h-6 text-yellow-600 dark:text-yellow-400 mb-2 group-hover:scale-110 transition-transform" />
          <span className="text-sm font-medium text-yellow-900 dark:text-yellow-100">Pause All</span>
        </button>

        <button className="flex flex-col items-center justify-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg hover:bg-green-100 dark:hover:bg-green-900/30 transition-colors group">
          <RefreshCw className="w-6 h-6 text-green-600 dark:text-green-400 mb-2 group-hover:scale-110 transition-transform" />
          <span className="text-sm font-medium text-green-900 dark:text-green-100">Refresh Data</span>
        </button>

        <button className="flex flex-col items-center justify-center p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg hover:bg-purple-100 dark:hover:bg-purple-900/30 transition-colors group">
          <Settings className="w-6 h-6 text-purple-600 dark:text-purple-400 mb-2 group-hover:scale-110 transition-transform" />
          <span className="text-sm font-medium text-purple-900 dark:text-purple-100">Settings</span>
        </button>
      </div>

      {/* System Status */}
      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <span className="text-sm font-medium text-gray-900 dark:text-white">System Status</span>
          </div>
          <span className="text-xs text-green-600 dark:text-green-400 font-medium">Active</span>
        </div>

        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
          <div className="text-gray-600 dark:text-gray-400">
            WebSocket: <span className="text-green-600">Connected</span>
          </div>
          <div className="text-gray-600 dark:text-gray-400">
            Signals: <span className="text-blue-600">Ready</span>
          </div>
        </div>
      </div>

      {/* Note */}
      <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
        <p className="text-xs text-blue-700 dark:text-blue-300 text-center">
          Quick action buttons will be functional when backend APIs are connected
        </p>
      </div>
    </div>
  )
}