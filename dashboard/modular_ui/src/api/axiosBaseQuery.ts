import axios, { AxiosRequestConfig } from 'axios'
import type { BaseQueryFn } from '@reduxjs/toolkit/query/react'

type AxiosBaseQueryArgs = {
  url: string
  method?: AxiosRequestConfig['method']
  data?: AxiosRequestConfig['data']
  params?: AxiosRequestConfig['params']
}

export const axiosBaseQuery = ({ baseUrl }: { baseUrl: string } = { baseUrl: '' }): BaseQueryFn<AxiosBaseQueryArgs, unknown, unknown> =>
  async ({ url, method = 'get', data, params }, _api, _extraOptions) => {
    try {
      const result = await axios({ url: baseUrl + url, method, data, params })
      return { data: result.data }
    } catch (axiosError: any) {
      const err = axiosError
      return {
        error: {
          status: err.response?.status ?? 500,
          data: err.response?.data ?? { message: err.message },
        },
      }
    }
  }

export const defaultAxios = axios.create({
  timeout: 10_000,
})

// Example interceptor for auth or logging (can be extended)
defaultAxios.interceptors.request.use((config) => {
  // Add auth header if present in localStorage
  const token = localStorage.getItem('token')
  if (token && config.headers) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

defaultAxios.interceptors.response.use(
  (resp) => resp,
  (error) => {
    // Global error handling hook point
    return Promise.reject(error)
  }
)
