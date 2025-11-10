export interface Coupon {
  id: string
  type: 'frontstore' | 'category' | 'brand'
  discountDetails: string
  categoryOrBrand?: string
  expirationDate: string
  terms?: string
}
