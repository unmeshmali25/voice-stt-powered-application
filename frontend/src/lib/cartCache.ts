/**
 * Cart caching utilities to improve performance
 * Uses sessionStorage for temporary caching (cleared on tab close)
 */

interface CacheData {
  eligibleCoupons: any[];
  ineligibleCoupons: any[];
  summary: any;
  timestamp: number;
  cartHash: string; // Hash of cart items to detect changes
}

const CACHE_KEY = 'cart_cache';
const CACHE_TTL = 30 * 1000; // 30 seconds

/**
 * Generate a simple hash from cart items
 */
function generateCartHash(items: any[]): string {
  return items
    .map(item => `${item.product_id}-${item.quantity}`)
    .sort()
    .join('|');
}

/**
 * Check if cache is valid (not expired and cart hasn't changed)
 */
export function isCacheValid(items: any[]): boolean {
  try {
    const cached = sessionStorage.getItem(CACHE_KEY);
    if (!cached) return false;

    const data: CacheData = JSON.parse(cached);
    const now = Date.now();

    // Check age
    if (now - data.timestamp > CACHE_TTL) {
      return false;
    }

    // Check if cart has changed
    const currentHash = generateCartHash(items);
    if (data.cartHash !== currentHash) {
      return false;
    }

    return true;
  } catch {
    return false;
  }
}

/**
 * Get cached cart data
 */
export function getCache(): CacheData | null {
  try {
    const cached = sessionStorage.getItem(CACHE_KEY);
    if (!cached) return null;

    return JSON.parse(cached);
  } catch {
    return null;
  }
}

/**
 * Set cache data
 */
export function setCache(
  eligibleCoupons: any[],
  ineligibleCoupons: any[],
  summary: any,
  items: any[]
): void {
  try {
    const data: CacheData = {
      eligibleCoupons,
      ineligibleCoupons,
      summary,
      timestamp: Date.now(),
      cartHash: generateCartHash(items),
    };

    sessionStorage.setItem(CACHE_KEY, JSON.stringify(data));
  } catch (error) {
    console.error('Failed to cache cart data:', error);
  }
}

/**
 * Clear cache
 */
export function clearCache(): void {
  try {
    sessionStorage.removeItem(CACHE_KEY);
  } catch (error) {
    console.error('Failed to clear cache:', error);
  }
}
