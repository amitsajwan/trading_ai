import { createSlice, PayloadAction } from '@reduxjs/toolkit'

export interface NotificationItem {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
  timestamp: string
  read: boolean
}

export interface WidgetConfig {
  id: string
  type: string
  title: string
  position: { x: number; y: number }
  size: { width: number; height: number }
  visible: boolean
  settings: Record<string, any>
}

export interface DashboardLayout {
  widgets: WidgetConfig[]
  theme: 'light' | 'dark' | 'auto'
  compact: boolean
  autoRefresh: boolean
  refreshInterval: number // in seconds
}

interface UIState {
  theme: 'light' | 'dark' | 'auto'
  sidebarCollapsed: boolean
  notifications: NotificationItem[]
  dashboardLayout: DashboardLayout
  loading: {
    global: boolean
    sidebar: boolean
  }
  modals: {
    settings: boolean
    confirmTrade: boolean
    notifications: boolean
  }
  activeModal: string | null
  modalData: any
}

const initialState: UIState = {
  theme: 'auto',
  sidebarCollapsed: false,
  notifications: [],
  dashboardLayout: {
    widgets: [
      {
        id: 'market-overview',
        type: 'market-overview',
        title: 'Market Overview',
        position: { x: 0, y: 0 },
        size: { width: 6, height: 3 },
        visible: true,
        settings: {}
      },
      {
        id: 'current-signal',
        type: 'current-signal',
        title: 'Current Signal',
        position: { x: 6, y: 0 },
        size: { width: 6, height: 3 },
        visible: true,
        settings: {}
      },
      {
        id: 'portfolio',
        type: 'portfolio',
        title: 'Portfolio',
        position: { x: 0, y: 3 },
        size: { width: 6, height: 4 },
        visible: true,
        settings: {}
      },
      {
        id: 'recent-trades',
        type: 'recent-trades',
        title: 'Recent Trades',
        position: { x: 6, y: 3 },
        size: { width: 6, height: 4 },
        visible: true,
        settings: {}
      },
      {
        id: 'technical-indicators',
        type: 'technical-indicators',
        title: 'Technical Indicators',
        position: { x: 0, y: 7 },
        size: { width: 12, height: 3 },
        visible: true,
        settings: {}
      }
    ],
    theme: 'auto',
    compact: false,
    autoRefresh: true,
    refreshInterval: 30
  },
  loading: {
    global: false,
    sidebar: false
  },
  modals: {
    settings: false,
    confirmTrade: false,
    notifications: false
  },
  activeModal: null,
  modalData: null
}

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setTheme: (state, action: PayloadAction<'light' | 'dark' | 'auto'>) => {
      state.theme = action.payload
      state.dashboardLayout.theme = action.payload
      localStorage.setItem('theme', action.payload)
    },
    toggleSidebar: (state) => {
      state.sidebarCollapsed = !state.sidebarCollapsed
    },
    setSidebarCollapsed: (state, action: PayloadAction<boolean>) => {
      state.sidebarCollapsed = action.payload
    },
    addNotification: (state, action: PayloadAction<Omit<NotificationItem, 'id' | 'timestamp' | 'read'>>) => {
      const notification: NotificationItem = {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        read: false,
        ...action.payload
      }
      state.notifications.unshift(notification)
      // Keep only last 50 notifications
      state.notifications = state.notifications.slice(0, 50)
    },
    markNotificationRead: (state, action: PayloadAction<string>) => {
      const notification = state.notifications.find(n => n.id === action.payload)
      if (notification) {
        notification.read = true
      }
    },
    clearNotification: (state, action: PayloadAction<string>) => {
      state.notifications = state.notifications.filter(n => n.id !== action.payload)
    },
    clearAllNotifications: (state) => {
      state.notifications = []
    },
    updateWidgetConfig: (state, action: PayloadAction<{ id: string; config: Partial<WidgetConfig> }>) => {
      const widget = state.dashboardLayout.widgets.find(w => w.id === action.payload.id)
      if (widget) {
        Object.assign(widget, action.payload.config)
      }
    },
    updateDashboardLayout: (state, action: PayloadAction<Partial<DashboardLayout>>) => {
      Object.assign(state.dashboardLayout, action.payload)
    },
    setGlobalLoading: (state, action: PayloadAction<boolean>) => {
      state.loading.global = action.payload
    },
    setSidebarLoading: (state, action: PayloadAction<boolean>) => {
      state.loading.sidebar = action.payload
    },
    openModal: (state, action: PayloadAction<{ modal: string; data?: any }>) => {
      state.activeModal = action.payload.modal
      state.modalData = action.payload.data || null
      if (action.payload.modal in state.modals) {
        (state.modals as any)[action.payload.modal] = true
      }
    },
    closeModal: (state) => {
      if (state.activeModal && state.activeModal in state.modals) {
        (state.modals as any)[state.activeModal] = false
      }
      state.activeModal = null
      state.modalData = null
    },
    toggleCompactMode: (state) => {
      state.dashboardLayout.compact = !state.dashboardLayout.compact
    },
    setAutoRefresh: (state, action: PayloadAction<boolean>) => {
      state.dashboardLayout.autoRefresh = action.payload
    },
    setRefreshInterval: (state, action: PayloadAction<number>) => {
      state.dashboardLayout.refreshInterval = action.payload
    },
  },
})

export const {
  setTheme,
  toggleSidebar,
  setSidebarCollapsed,
  addNotification,
  markNotificationRead,
  clearNotification,
  clearAllNotifications,
  updateWidgetConfig,
  updateDashboardLayout,
  setGlobalLoading,
  setSidebarLoading,
  openModal,
  closeModal,
  toggleCompactMode,
  setAutoRefresh,
  setRefreshInterval,
} = uiSlice.actions

export default uiSlice.reducer