import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  Home,
  BarChart3,
  TrendingUp,
  Settings,
  Menu,
  X,
  Zap,
  Newspaper,
  Users,
  Activity
} from 'lucide-react'
import { RootState } from '../../store'
import { toggleSidebar } from '../../store/slices/uiSlice'

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home, current: true },
  { name: 'Market Data', href: '/market-data', icon: BarChart3, current: false },
  { name: 'Trading', href: '/trading', icon: TrendingUp, current: false },
  { name: 'Analytics', href: '/analytics', icon: Activity, current: false },
  { name: 'News', href: '/news', icon: Newspaper, current: false },
  { name: 'Settings', href: '/settings', icon: Settings, current: false },
]

export const Sidebar: React.FC = () => {
  const dispatch = useDispatch()
  const location = useLocation()
  const { sidebarCollapsed, loading } = useSelector((state: RootState) => state.ui)

  const handleToggleSidebar = () => {
    dispatch(toggleSidebar())
  }

  return (
    <>
      {/* Mobile sidebar backdrop */}
      {!sidebarCollapsed && (
        <div
          className="fixed inset-0 z-40 bg-black bg-opacity-50 lg:hidden"
          onClick={handleToggleSidebar}
        />
      )}

      {/* Sidebar */}
      <div className={`fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transform transition-transform duration-300 ease-in-out ${
        sidebarCollapsed ? '-translate-x-full lg:translate-x-0 lg:w-16' : 'translate-x-0'
      }`}>
        <div className="flex flex-col h-full">
          {/* Logo and Toggle */}
          <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center">
              <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" />
              </div>
              {!sidebarCollapsed && (
                <span className="ml-3 text-lg font-semibold text-gray-900 dark:text-white">
                  Zerodha
                </span>
              )}
            </div>
            <button
              onClick={handleToggleSidebar}
              className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              {sidebarCollapsed ? (
                <Menu className="w-5 h-5" />
              ) : (
                <X className="w-5 h-5" />
              )}
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-2 py-4 space-y-1">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors duration-200 ${
                    isActive
                      ? 'bg-primary-50 text-primary-700 border-r-2 border-primary-500 dark:bg-primary-900/20 dark:text-primary-300'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-white'
                  }`}
                  title={sidebarCollapsed ? item.name : undefined}
                >
                  <item.icon
                    className={`flex-shrink-0 w-5 h-5 ${
                      isActive ? 'text-primary-500' : 'text-gray-400 group-hover:text-gray-600'
                    }`}
                  />
                  {!sidebarCollapsed && (
                    <span className="ml-3">{item.name}</span>
                  )}
                </Link>
              )
            })}
          </nav>

          {/* Status Indicator */}
          <div className="p-4 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center space-x-3">
              <div className={`w-3 h-3 rounded-full ${
                loading.sidebar ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'
              }`} />
              {!sidebarCollapsed && (
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white">
                    System Status
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {loading.sidebar ? 'Loading...' : 'All systems operational'}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}