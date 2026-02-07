// Date utility functions for handling IST timestamps from backend

/**
 * Format timestamp from backend (already in IST without timezone info) to display format
 * Backend sends timestamps like "2026-01-16T12:30:36.971394" which are already in IST
 */
export function formatTimestampForDisplay(timestamp: string | undefined | null): string {
  if (!timestamp) return 'N/A'

  try {
    // Backend timestamps are already in IST format without timezone info
    // Parse as local time (which is effectively IST) and format for display
    const date = new Date(timestamp)

    // Format as IST time string
    return date.toLocaleTimeString('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch (error) {
    console.error('Error formatting timestamp:', error, timestamp)
    return 'Error'
  }
}

/**
 * Format timestamp for date and time display
 */
export function formatTimestampFull(timestamp: string | undefined | null): string {
  if (!timestamp) return 'N/A'

  try {
    const date = new Date(timestamp)
    return date.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })
  } catch (error) {
    console.error('Error formatting full timestamp:', error, timestamp)
    return 'Error'
  }
}

/**
 * Get current time in IST
 */
export function getCurrentISTTime(): string {
  return new Date().toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour12: false
  })
}