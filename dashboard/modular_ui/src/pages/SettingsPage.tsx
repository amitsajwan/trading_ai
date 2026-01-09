import React from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { RootState } from '../store'
import { setAutoRefresh, setRefreshInterval, setTheme } from '../store/slices/uiSlice'

export const SettingsPage: React.FC = () => {
  const dispatch = useDispatch()
  const { dashboardLayout, theme } = useSelector((s: RootState) => ({ dashboardLayout: s.ui.dashboardLayout, theme: s.ui.theme }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h1>
        <p className="text-gray-600 dark:text-gray-400">Configure dashboard preferences and integrations</p>
      </div>

      <section className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">General</h2>

        <div className="mt-4 space-y-4">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Theme</label>
            <select value={theme} onChange={(e) => dispatch(setTheme(e.target.value as any))} className="border rounded p-2 bg-white dark:bg-gray-700">
              <option value="auto">Auto</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </div>

          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Auto Refresh</label>
            <input type="checkbox" aria-label="auto-refresh" checked={dashboardLayout.autoRefresh} onChange={(e) => dispatch(setAutoRefresh(e.target.checked))} />
          </div>

          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Refresh Interval (seconds)</label>
            <input type="number" min={5} value={dashboardLayout.refreshInterval} onChange={(e) => dispatch(setRefreshInterval(Number(e.target.value)))} className="w-24 border rounded p-1" />
          </div>
        </div>
      </section>
    </div>
  )
}
