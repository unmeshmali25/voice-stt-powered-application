export interface Coupon {
  id: string
  type: 'frontstore' | 'category' | 'brand'
  discountDetails: string
  categoryOrBrand?: string
  expirationDate: string
  terms?: string
}

export interface ImageExtractionResult {
  brand: string | null
  category: string | null
  confidence: 'high' | 'medium' | 'low'
  searchQuery: string
}
