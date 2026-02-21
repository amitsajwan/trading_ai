import React, { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Bell, Moon, Sun, User, Settings } from 'lucide-react'
import { RootState } from '../../store'
import { useTheme } from '../../hooks/useTheme'
import { openModal } from '../../store/slices/uiSlice'

const MODE_INFO_URL = '/api/control/mode/info'

type RuntimeModeInfo = {
  mode: string
  run_id: string
  instrument: string
  source?: string
}

export const Header: React.FC = () => {
  const dispatch = useDispatch()
  const { theme, setTheme } = useTheme()
  const { notifications } = useSelector((state: RootState) => state.ui)
  const { currentUser } = useSelector((state: RootState) => state.user)
  const executionMode = useSelector((state: RootState) => state.ui.executionMode)

  const runtimeCacheKey = 'runtime_mode_info'
  const cachedRuntimeInfo = React.useMemo(() => {
    try {
      const raw = localStorage.getItem(runtimeCacheKey)
      if (!raw) return null
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object') return null
      return parsed as RuntimeModeInfo
    } catch {
      return null
    }
  }, [])

  const [runtimeInfo, setRuntimeInfo] = useState<RuntimeModeInfo>({
    mode: String(cachedRuntimeInfo?.mode || executionMode.mode || import.meta.env.VITE_EXECUTION_MODE || 'UNKNOWN').toUpperCase(),
    run_id: String(cachedRuntimeInfo?.run_id || executionMode.runId || ''),
    instrument: String(cachedRuntimeInfo?.instrument || executionMode.instrument || import.meta.env.VITE_INSTRUMENT_SYMBOL || ''),
    source: 'unknown'
  })
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string>(new Date().toISOString())

  const unreadCount = notifications.filter((n) => !n.read).length

  useEffect(() => {
    let isMounted = true

    const fetchRuntimeInfo = async () => {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 8000)
      try {
        const response = await fetch(MODE_INFO_URL, { signal: controller.signal })
        if (!response.ok) return
        const data = await response.json()
        if (!isMounted) return
        const nextRuntimeInfo = {
          mode: String(data?.mode || 'UNKNOWN').toUpperCase(),
          run_id: String(data?.run_id || ''),
          instrument: String(data?.instrument || ''),
          source: String(data?.source || 'unknown')
        }
        setRuntimeInfo(nextRuntimeInfo)
        try {
          localStorage.setItem(runtimeCacheKey, JSON.stringify(nextRuntimeInfo))
        } catch {
          // ignore storage failures
        }
        setLastUpdatedAt(new Date().toISOString())
      } catch {
        // Keep previous values when endpoint is unavailable.
      } finally {
        clearTimeout(timer)
      }
    }

    fetchRuntimeInfo()
    const timer = setInterval(fetchRuntimeInfo, 15000)
    return () => {
      isMounted = false
      clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    // Keep runtime badges meaningful even if mode endpoint is transiently unavailable.
    if (!runtimeInfo.instrument && executionMode.instrument) {
      setRuntimeInfo((prev) => ({ ...prev, instrument: executionMode.instrument }))
    }
    if ((!runtimeInfo.mode || runtimeInfo.mode === 'UNKNOWN') && executionMode.mode) {
      setRuntimeInfo((prev) => ({ ...prev, mode: String(executionMode.mode).toUpperCase() }))
    }
    if (!runtimeInfo.run_id && executionMode.runId) {
      setRuntimeInfo((prev) => ({ ...prev, run_id: executionMode.runId }))
    }
  }, [executionMode.instrument, executionMode.mode, executionMode.runId, runtimeInfo.instrument, runtimeInfo.mode, runtimeInfo.run_id])

  const formattedUpdatedTime = useMemo(
    () =>
      new Date(lastUpdatedAt).toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }),
    [lastUpdatedAt]
  )

  const handleThemeToggle = () => {
    const newTheme = theme === 'light' ? 'dark' : theme === 'dark' ? 'auto' : 'light'
    setTheme(newTheme)
  }

  const handleNotificationsClick = () => {
    dispatch(openModal({ modal: 'notifications' }))
  }

  const handleSettingsClick = () => {
    dispatch(openModal({ modal: 'settings' }))
  }

  const getThemeIcon = () => {
    switch (theme) {
      case 'light':
        return <Sun className="w-5 h-5" />
      case 'dark':
        return <Moon className="w-5 h-5" />
      default:
        return <Sun className="w-5 h-5" />
    }
  }

  return (
    <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Trading Dashboard</h1>
          <div className="hidden md:flex items-center space-x-2 text-sm text-gray-500 dark:text-gray-400">
            <span>Zerodha</span>
            <span>-</span>
            <span>AI Trading System</span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleThemeToggle}
            className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-700 transition-colors"
            title={`Current theme: ${theme}`}
          >
            {getThemeIcon()}
          </button>

          <button
            onClick={handleNotificationsClick}
            className="relative p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          <button
            onClick={handleSettingsClick}
            className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            <Settings className="w-5 h-5" />
          </button>

          <div className="relative">
            <button className="flex items-center space-x-2 p-2 rounded-lg text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700 transition-colors">
              <div className="w-8 h-8 bg-primary-500 rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-white" />
              </div>
              <span className="hidden md:block text-sm font-medium">{currentUser?.username || 'User'}</span>
            </button>
          </div>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between text-sm gap-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-gray-600 dark:text-gray-400">Market Open</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
            <span className="text-gray-600 dark:text-gray-400">AI Active</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse-slow"></div>
            <span className="text-gray-600 dark:text-gray-400">Real-time Data</span>
          </div>
          <div className="px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200">
            Mode: <span className="font-semibold">{runtimeInfo.mode || 'UNKNOWN'}</span>
          </div>
          <div className="px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200">
            Instrument: <span className="font-semibold">{runtimeInfo.instrument || 'N/A'}</span>
          </div>
          <div className="px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200">
            Run: <span className="font-semibold">{runtimeInfo.run_id || 'N/A'}</span>
          </div>
        </div>

        <div className="text-gray-500 dark:text-gray-400">Last updated: {formattedUpdatedTime}</div>
      </div>
    </header>
  )
}
