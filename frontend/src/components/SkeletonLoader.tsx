import { Card, CardContent, CardHeader } from './ui/card'

export function ProductCardSkeleton() {
  return (
    <Card className="shadow-[0_4px_12px_rgba(0,0,0,0.5)] border-border/50 backdrop-blur-sm animate-pulse">
      <CardHeader className="p-0">
        <div className="relative w-full h-20 overflow-hidden rounded-t-lg bg-gray-300" />
      </CardHeader>
      <CardContent className="p-2">
        <div className="space-y-1">
          {/* Product Name Skeleton */}
          <div className="space-y-1">
            <div className="h-3 bg-gray-300 rounded w-full" />
            <div className="h-3 bg-gray-300 rounded w-3/4" />
          </div>

          {/* Rating Skeleton */}
          <div className="flex items-center gap-1">
            <div className="flex gap-0.5">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="w-2.5 h-2.5 bg-gray-300 rounded-full" />
              ))}
            </div>
            <div className="h-2 bg-gray-300 rounded w-8" />
          </div>

          {/* Price Skeleton */}
          <div className="h-4 bg-gray-300 rounded w-16" />

          {/* Button Skeleton */}
          <div className="h-7 bg-gray-300 rounded-full w-full mt-2" />
        </div>
      </CardContent>
    </Card>
  )
}

export function CouponCardSkeleton() {
  return (
    <Card className="shadow-md hover:shadow-xl transition-shadow duration-300 border-border/40 backdrop-blur-sm animate-pulse">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          {/* Badge Skeleton */}
          <div className="h-5 bg-gray-300 rounded-full w-24" />
          {/* Icon Skeleton */}
          <div className="w-4 h-4 bg-gray-300 rounded" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Discount Details Skeleton */}
        <div className="space-y-1">
          <div className="h-5 bg-gray-300 rounded w-full" />
          <div className="h-5 bg-gray-300 rounded w-3/4" />
        </div>

        {/* Category/Brand Skeleton */}
        <div className="h-4 bg-gray-300 rounded w-32" />

        {/* Expiration Skeleton */}
        <div className="h-3 bg-gray-300 rounded w-40" />

        {/* Terms Skeleton */}
        <div className="space-y-1">
          <div className="h-3 bg-gray-300 rounded w-full" />
          <div className="h-3 bg-gray-300 rounded w-2/3" />
        </div>
      </CardContent>
    </Card>
  )
}

export function NoResults({ query }: { query: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      <div className="text-6xl mb-4">🔍</div>
      <h3 className="text-xl font-semibold mb-2">No results found</h3>
      <p className="text-muted-foreground mb-6">
        We couldn't find any products matching "{query}"
      </p>
      <p className="text-sm text-muted-foreground">
        Try searching for something else or browse our suggested products below
      </p>
    </div>
  )
}
