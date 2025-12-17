import { Card, CardContent, CardHeader, CardFooter } from './ui/card'
import { Product } from '../types/retail'
import { Star, ShoppingCart, Loader2 } from 'lucide-react'
import { Button } from './ui/button'
import { useCart } from '../contexts/CartContext'
import { useState } from 'react'
import { useStore } from '../contexts/StoreContext'
import { toast } from 'sonner' // Assuming sonner is used for toasts, or I should use standard alert for now if not available

interface ProductCardProps {
  product: Product
}

export function ProductCard({ product }: ProductCardProps) {
  const { addToCart } = useCart()
  const { selectedStore } = useStore()
  const [isAdding, setIsAdding] = useState(false)

  const handleAddToCart = async () => {
    if (!selectedStore) {
      // Show error or prompt to select store
      alert("Please select a store first")
      return
    }

    setIsAdding(true)
    try {
      await addToCart(product.id, 1)
      // Optional: Show success toast
    } catch (error) {
      // Error handled in context
      console.error(error)
    } finally {
      setIsAdding(false)
    }
  }

  return (
    <Card className="h-full flex flex-col shadow-[0_4px_12px_rgba(0,0,0,0.5)] hover:shadow-[0_12px_32px_rgba(255,215,0,0.4)] hover:scale-105 transition-all duration-300 border-border/50 backdrop-blur-sm">
      <CardHeader className="p-2">
        <div className="relative w-full h-32 overflow-hidden rounded-md bg-white flex items-center justify-center p-2">
          <img
            src={product.imageUrl}
            alt={product.name}
            className="w-full h-full object-contain"
            onError={(e) => {
              const target = e.target as HTMLImageElement;
              target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="200" height="300" viewBox="0 0 200 300"%3E%3Crect fill="%23ddd" width="200" height="300"/%3E%3Ctext fill="%23999" font-family="sans-serif" font-size="16" dy="10.5" font-weight="bold" x="50%25" y="50%25" text-anchor="middle"%3ENo Image%3C/text%3E%3C/svg%3E'
            }}
          />
        </div>
      </CardHeader>
      <CardContent className="p-2 flex-1">
        <div className="space-y-1">
          <h3 className="text-xs font-semibold line-clamp-2 min-h-[2rem]">
            {product.name}
          </h3>

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

          <div className="text-base font-bold">
            ${product.price.toFixed(2)}
          </div>

          {product.promoText && (
            <div className="text-xs text-red-600 font-semibold">
              {product.promoText}
            </div>
          )}
        </div>
      </CardContent>
      <CardFooter className="p-2 pt-0">
        <Button 
          className="w-full h-8 text-xs" 
          size="sm"
          onClick={handleAddToCart}
          disabled={isAdding || !product.inStock}
        >
          {isAdding ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <>
              <ShoppingCart className="h-3 w-3 mr-1" />
              Add
            </>
          )}
        </Button>
      </CardFooter>
    </Card>
  )
}
