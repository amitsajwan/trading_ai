import { configureStore } from '@reduxjs/toolkit'
import marketDataReducer from './slices/marketDataSlice'
import tradingReducer from './slices/tradingSlice'
import userReducer from './slices/userSlice'
import uiReducer from './slices/uiSlice'
import newsReducer from './slices/newsSlice'
import analyticsReducer from './slices/analyticsSlice'
import { dashboardApi } from '../api/dashboardApi'

export const store = configureStore({
  reducer: {
    marketData: marketDataReducer,
    trading: tradingReducer,
    user: userReducer,
    ui: uiReducer,
    news: newsReducer,
    analytics: analyticsReducer,
    [dashboardApi.reducerPath]: dashboardApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: ['persist/PERSIST'],
      },
    }).concat(dashboardApi.middleware),
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch