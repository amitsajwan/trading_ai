/**
 * HTTPDataService - Wraps HTTP calls using axios
 * 
 * Simple service for fetching data via HTTP.
 * Used by HybridDataService to fetch initial data or as fallback.
 */

import axios, { AxiosInstance } from 'axios'

const BASE_URL = import.meta.env.VITE_DASHBOARD_API_URL ?? ''

/**
 * HTTP Data Service
 * Wraps axios for HTTP calls
 */
export class HTTPDataService {
  private client: AxiosInstance

  constructor(baseURL: string = BASE_URL) {
    this.client = axios.create({
      baseURL,
      timeout: 10_000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Add auth header if present
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('token')
      if (token && config.headers) {
        config.headers['Authorization'] = `Bearer ${token}`
      }
      return config
    })
  }

  /**
   * Fetch data from HTTP endpoint
   * @param url Endpoint URL (relative to base URL)
   * @param options Request options (method, data, params)
   * @returns Promise with data
   */
  async fetch<T = any>(url: string, options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
    data?: any
    params?: Record<string, any>
  }): Promise<T> {
    try {
      const response = await this.client.request<T>({
        url,
        method: options?.method || 'GET',
        data: options?.data,
        params: options?.params,
      })

      return response.data
    } catch (error: any) {
      // Re-throw with more context
      if (error.response) {
        // Server responded with error status
        throw new Error(
          `HTTP ${error.response.status}: ${error.response.data?.message || error.message}`
        )
      } else if (error.request) {
        // Request made but no response
        throw new Error(`Network error: ${error.message}`)
      } else {
        // Error in request setup
        throw new Error(`Request error: ${error.message}`)
      }
    }
  }

  /**
   * GET request
   */
  async get<T = any>(url: string, params?: Record<string, any>): Promise<T> {
    return this.fetch<T>(url, { method: 'GET', params })
  }

  /**
   * POST request
   */
  async post<T = any>(url: string, data?: any): Promise<T> {
    return this.fetch<T>(url, { method: 'POST', data })
  }

  /**
   * PUT request
   */
  async put<T = any>(url: string, data?: any): Promise<T> {
    return this.fetch<T>(url, { method: 'PUT', data })
  }

  /**
   * DELETE request
   */
  async delete<T = any>(url: string): Promise<T> {
    return this.fetch<T>(url, { method: 'DELETE' })
  }
}

// Singleton instance
export const httpDataService = new HTTPDataService()
