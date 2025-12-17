import { supabase } from './supabase'

const SELECTED_STORE_PREFIX = 'selected_store_id'
const SHOPPING_SESSION_PREFIX = 'shopping_session_id'

function safeRandomUUID(): string {
  // Prefer the native generator when available
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }

  // Fallback UUIDv4-ish (good enough for client-side correlation IDs)
  // eslint-disable-next-line no-bitwise
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    // eslint-disable-next-line no-bitwise
    const r = (Math.random() * 16) | 0
    // eslint-disable-next-line no-bitwise
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export function getSelectedStoreStorageKey(userId: string): string {
  return `${SELECTED_STORE_PREFIX}:${userId}`
}

export function setSelectedStoreIdForUser(userId: string, storeId: string | null) {
  if (typeof window === 'undefined') return
  const key = getSelectedStoreStorageKey(userId)
  if (!storeId) {
    window.localStorage.removeItem(key)
    return
  }
  window.localStorage.setItem(key, storeId)
}

export function getSelectedStoreIdForUser(userId: string): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(getSelectedStoreStorageKey(userId))
}

export function getShoppingSessionStorageKey(userId: string, storeId: string | null): string {
  return `${SHOPPING_SESSION_PREFIX}:${userId}:${storeId || 'no_store'}`
}

export function getShoppingSessionId(userId: string, storeId: string | null): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(getShoppingSessionStorageKey(userId, storeId))
}

export function getOrCreateShoppingSessionId(userId: string, storeId: string | null): string {
  if (typeof window === 'undefined') return safeRandomUUID()
  const key = getShoppingSessionStorageKey(userId, storeId)
  const existing = window.localStorage.getItem(key)
  if (existing) return existing
  const next = safeRandomUUID()
  window.localStorage.setItem(key, next)
  return next
}

export function clearShoppingSessionId(userId: string, storeId: string | null) {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(getShoppingSessionStorageKey(userId, storeId))
}

export function shouldAttachShoppingSessionHeader(pathname: string): boolean {
  // Create/attach session only for search/cart/checkout flows
  return (
    pathname.startsWith('/api/cart') ||
    pathname.startsWith('/api/orders') ||
    pathname.startsWith('/api/products/search') ||
    pathname.startsWith('/api/coupons/search') ||
    pathname.startsWith('/api/coupons/eligible')
  )
}

export async function clearCurrentShoppingSession(): Promise<void> {
  const {
    data: { session },
  } = await supabase.auth.getSession()
  const userId = session?.user?.id
  if (!userId) return
  const storeId = getSelectedStoreIdForUser(userId)
  clearShoppingSessionId(userId, storeId)
}


