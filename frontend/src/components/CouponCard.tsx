import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card'
import { Coupon } from '../types/coupon'

interface CouponCardProps {
  coupon: Coupon
  size?: 'default' | 'compact'
}

export function CouponCard({ coupon, size = 'default' }: CouponCardProps) {
  const getBadgeColor = (type: Coupon['type']) => {
    switch (type) {
      case 'frontstore':
        return 'bg-[#CC0000]/10 text-[#CC0000] border border-[#CC0000]/30'
      case 'category':
        return 'bg-emerald-500/10 text-emerald-700 border border-emerald-500/30'
      case 'brand':
        return 'bg-purple-500/10 text-purple-700 border border-purple-500/30'
      default:
        return 'bg-gray-500/10 text-gray-700 border border-gray-500/30'
    }
  }

  const formatExpirationDate = (dateString: string) => {
    try {
      const date = new Date(dateString)
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      })
    } catch {
      return dateString
    }
  }

  const isCompact = size === 'compact'

  return (
    <Card
      className={`shadow-[0_4px_12px_rgba(0,0,0,0.5)] hover:shadow-[0_12px_32px_rgba(204,0,0,0.4)] hover:-translate-y-1 transition-all duration-300 border-border/50 backdrop-blur-sm ${
        isCompact ? 'p-2 text-sm' : ''
      }`}
    >
      <CardHeader className={isCompact ? 'py-4' : undefined}>
        <div className={`flex items-start justify-between gap-2 ${isCompact ? 'space-x-2' : ''}`}>
          <div className="flex-1">
            <CardTitle className={`${isCompact ? 'text-sm mb-1' : 'text-lg mb-2'}`}>
              {coupon.discountDetails}
            </CardTitle>
            {coupon.categoryOrBrand && (
              <CardDescription className={`${isCompact ? 'text-xs font-medium' : 'text-base font-medium'}`}>
                {coupon.categoryOrBrand}
              </CardDescription>
            )}
          </div>
          <span
            className={`px-2.5 py-1 rounded-full text-xs font-semibold ${getBadgeColor(coupon.type)} ${
              isCompact ? 'text-[0.6rem] px-2 py-0.5' : ''
            }`}
          >
            {coupon.type === 'frontstore' ? 'Basket-offers' : coupon.type.charAt(0).toUpperCase() + coupon.type.slice(1)}
          </span>
        </div>
      </CardHeader>
      <CardContent className={isCompact ? 'pt-0 pb-3' : undefined}>
        <div className={`flex flex-col ${isCompact ? 'gap-0.5' : 'gap-1'}`}>
          <div className={`text-muted-foreground ${isCompact ? 'text-xs' : 'text-sm'}`}>
            <span className="font-medium">Expires:</span>{' '}
            {formatExpirationDate(coupon.expirationDate)}
          </div>
          {coupon.terms && (
            <div className={`text-muted-foreground mt-2 pt-2 border-t ${isCompact ? 'text-[0.65rem]' : 'text-xs'}`}>
              {coupon.terms}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
