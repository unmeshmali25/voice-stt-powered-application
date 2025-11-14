import { supabase, isSupabaseConfigured } from './supabase'

// API base URL from environment variables
// In development: uses Vite proxy (/api -> localhost:8000)
// In staging/production: uses actual backend URL
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

/**
 * Authenticated fetch helper that automatically adds Authorization header
 * and handles token refresh and 401 errors
 */
export async function apiFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  if (!isSupabaseConfigured) {
    throw new Error('Supabase is not configured. Please set up your environment variables.')
  }

  // Construct full URL
  const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`

  // Get current session
  const { data: { session } } = await supabase.auth.getSession()
  
  if (!session) {
    throw new Error('No active session. Please sign in.')
  }

  // Add Authorization header
  const headers = new Headers(options.headers)
  headers.set('Authorization', `Bearer ${session.access_token}`)

  // Don't set Content-Type for FormData - browser will set it with boundary
  const isFormData = options.body instanceof FormData
  if (isFormData && headers.has('Content-Type')) {
    headers.delete('Content-Type')
  }

  // Make the request
  const response = await fetch(fullUrl, {
    ...options,
    headers,
  })

  // Handle 401 Unauthorized - session expired
  if (response.status === 401) {
    // Try to refresh the session
    const { data: { session: newSession }, error } = await supabase.auth.refreshSession()
    
    if (error || !newSession) {
      // Refresh failed, clear session and throw error
      await supabase.auth.signOut()
      throw new Error('Session expired. Please sign in again.')
    }

    // Retry the request with new token
    const retryHeaders = new Headers(options.headers)
    retryHeaders.set('Authorization', `Bearer ${newSession.access_token}`)
    if (isFormData && retryHeaders.has('Content-Type')) {
      retryHeaders.delete('Content-Type')
    }
    return fetch(fullUrl, {
      ...options,
      headers: retryHeaders,
    })
  }

  return response
}

/**
 * Get the current API base URL (useful for debugging)
 */
export function getApiBaseUrl(): string {
  return API_BASE_URL
}

