import React, { Suspense } from 'react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useSelector } from 'react-redux'
import { RootState } from '../../store'
import { ErrorBoundary } from '../ErrorBoundary'
import { FullPageLoader } from '../FullPageLoader'

interface DashboardLayoutProps {
  children: React.ReactNode
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
  const sidebarCollapsed = useSelector((state: RootState) => state.ui.sidebarCollapsed)

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className={`flex-1 flex flex-col transition-all duration-300 ${
        sidebarCollapsed ? 'ml-16' : 'ml-64'
      }`}>
        {/* Header */}
        <Header />

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            <ErrorBoundary>
              <Suspense fallback={<FullPageLoader />}>
                {children}
              </Suspense>
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  )
}