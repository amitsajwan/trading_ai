import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import axios from 'axios'

export interface User {
  id: string
  username: string
  email: string
  role: string
  preferences: Record<string, any>
}

export interface UserSettings {
  theme: 'light' | 'dark' | 'auto'
  notifications: {
    email: boolean
    push: boolean
    tradeAlerts: boolean
    systemAlerts: boolean
  }
  trading: {
    defaultQuantity: number
    maxPositionSize: number
    riskLimit: number
    autoExecute: boolean
  }
}

interface UserState {
  currentUser: User | null
  settings: UserSettings | null
  authenticated: boolean
  loading: boolean
  error: string | null
}

const initialState: UserState = {
  currentUser: null,
  settings: null,
  authenticated: false,
  loading: false,
  error: null,
}

export const fetchUserProfile = createAsyncThunk(
  'user/fetchUserProfile',
  async () => {
    const response = await axios.get('/api/user/profile')
    return response.data
  }
)

export const fetchUserSettings = createAsyncThunk(
  'user/fetchUserSettings',
  async () => {
    const response = await axios.get('/api/user/settings')
    return response.data
  }
)

export const updateUserSettings = createAsyncThunk(
  'user/updateUserSettings',
  async (settings: Partial<UserSettings>) => {
    const response = await axios.put('/api/user/settings', settings)
    return response.data
  }
)

const userSlice = createSlice({
  name: 'user',
  initialState,
  reducers: {
    setAuthenticated: (state, action) => {
      state.authenticated = action.payload
    },
    clearError: (state) => {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchUserProfile.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchUserProfile.fulfilled, (state, action) => {
        state.loading = false
        state.currentUser = action.payload
        state.authenticated = true
      })
      .addCase(fetchUserProfile.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to fetch user profile'
        state.authenticated = false
      })
      .addCase(fetchUserSettings.fulfilled, (state, action) => {
        state.settings = action.payload
      })
      .addCase(updateUserSettings.fulfilled, (state, action) => {
        state.settings = action.payload
      })
  },
})

export const { setAuthenticated, clearError } = userSlice.actions
export default userSlice.reducer