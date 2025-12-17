import { supabase, isSupabaseConfigured } from './supabase'

// API base URL from environment variables
// In development: uses Vite proxy (/api -> localhost:8000)
// In staging/production: uses actual backend URL
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

let hasWarnedAboutEmptyApiBaseUrl = false

function warnIfLikelyMisconfiguredApiBaseUrl(requestPath: string) {
  if (hasWarnedAboutEmptyApiBaseUrl) return
  if (API_BASE_URL) return
  if (typeof window === 'undefined') return

  const hostname = window.location?.hostname || ''
  const isLocalhost =
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname === '0.0.0.0' ||
    hostname.endsWith('.local')

  // In production-like environments, a missing VITE_API_URL usually means
  // the frontend will try to call its own origin for /api/*, which will fail
  // unless you have a reverse proxy/rewrites configured.
  if (!isLocalhost && requestPath.startsWith('/api')) {
    hasWarnedAboutEmptyApiBaseUrl = true
    // eslint-disable-next-line no-console
    console.warn(
      'VITE_API_URL is empty. API requests will be sent to the frontend origin unless you configure Vercel rewrites or set VITE_API_URL.',
      { requestPath, frontendOrigin: window.location.origin }
    )
  }
}

/**
 * Unauthenticated fetch helper for public endpoints (e.g. listing stores).
 * Uses the same base URL resolution as apiFetch but does NOT attach auth headers.
 */
export async function publicApiFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  warnIfLikelyMisconfiguredApiBaseUrl(url)
  const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`
  return fetch(fullUrl, options)
}

/**
 * Authenticated fetch helper that automatically adds Authorization header
 * and handles token refresh and 401 errors
 */
export async function apiFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  warnIfLikelyMisconfiguredApiBaseUrl(url)
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

