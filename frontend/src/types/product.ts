export interface Product {
  id: string
  name: string
  description?: string
  imageUrl: string
  price: number
  rating?: number
  reviewCount?: number
  category?: string
  brand?: string
  promoText?: string
  inStock?: boolean
}

