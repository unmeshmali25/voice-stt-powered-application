import { Card, CardContent, CardHeader } from './ui/card'
import { Button } from './ui/button'
import { Product } from '../types/product'
import { ShoppingCart, Star } from 'lucide-react'

interface ProductCardProps {
  product: Product
}

export function ProductCard({ product }: ProductCardProps) {
  return (
    <Card className="shadow-[0_4px_12px_rgba(0,0,0,0.5)] hover:shadow-[0_12px_32px_rgba(255,215,0,0.4)] hover:scale-110 hover:z-30 hover:border-amber-400/60 transition-all duration-300 border-border/50 backdrop-blur-sm">
      <CardHeader className="p-0">
        <div className="relative w-full h-20 overflow-hidden rounded-t-lg bg-gray-100">
          <img
            src={product.imageUrl}
            alt={product.name}
            className="w-full h-full object-cover"
            onError={(e) => {
              // Fallback to a placeholder if image fails to load
              const target = e.target as HTMLImageElement;
              target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="200" height="300" viewBox="0 0 200 300"%3E%3Crect fill="%23ddd" width="200" height="300"/%3E%3Ctext fill="%23999" font-family="sans-serif" font-size="16" dy="10.5" font-weight="bold" x="50%25" y="50%25" text-anchor="middle"%3ENo Image%3C/text%3E%3C/svg%3E'
            }}
          />
        </div>
      </CardHeader>
      <CardContent className="p-2">
        <div className="space-y-1">
          {/* Product Name */}
          <h3 className="text-xs font-semibold line-clamp-2 min-h-[2rem]">
            {product.name}
          </h3>

          {/* Rating */}
          {product.rating && (
            <div className="flex items-center gap-1">
              <div className="flex">
                {[...Array(5)].map((_, i) => (
                  <Star
                    key={i}
                    className={`w-2.5 h-2.5 ${
                      i < Math.floor(product.rating!)
                        ? 'fill-orange-500 text-orange-500'
                        : 'fill-none text-gray-300'
                    }`}
                  />
                ))}
              </div>
              {product.reviewCount && (
                <span className="text-[9px] text-muted-foreground">
                  {product.reviewCount}
                </span>
              )}
            </div>
          )}

          {/* Price */}
          <div className="text-base font-bold">
            ${product.price.toFixed(2)}
          </div>

          {/* Promo Text */}
          {product.promoText && (
            <div className="text-xs text-red-600 font-semibold">
              {product.promoText}
            </div>
          )}

          {/* Add Button */}
          <Button
            className="w-full bg-[#0033A0] hover:bg-[#002080] text-white rounded-full text-xs py-1"
            size="sm"
          >
            <ShoppingCart className="w-3 h-3 mr-1" />
            Add
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

