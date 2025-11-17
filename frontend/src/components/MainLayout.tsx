import { useState } from 'react'
import { SidebarProvider, SidebarInset } from './ui/sidebar'
import { VoiceSidebar } from './VoiceSidebar'
import { CouponCard } from './CouponCard'
import { ProductCard } from './ProductCard'
import { Coupon } from '../types/coupon'
import { Product } from '../types/product'
import { useAuth } from '../hooks/useAuth'
import { Button } from './ui/button'

// Mock data - will be replaced with real data from backend
const mockFrontstoreCoupons: Coupon[] = [
  {
    id: '1',
    type: 'frontstore',
    discountDetails: '2% off entire purchase',
    expirationDate: '2025-12-31',
    terms: 'Valid on all items. Cannot be combined with other offers.'
  },
  {
    id: '2',
    type: 'frontstore',
    discountDetails: '$2 off on $20 purchase',
    expirationDate: '2025-11-30',
    terms: 'Minimum purchase of $20 required.'
  },
  {
    id: '3',
    type: 'frontstore',
    discountDetails: '5% off orders over $50',
    expirationDate: '2025-12-15',
  },
]

const mockCategoryBrandCoupons: Coupon[] = [
  {
    id: '4',
    type: 'category',
    discountDetails: '20% off',
    categoryOrBrand: 'Beauty Products',
    expirationDate: '2025-11-25',
    terms: 'Excludes premium brands.'
  },
  {
    id: '5',
    type: 'brand',
    discountDetails: 'Buy 2 Get 1 Free',
    categoryOrBrand: 'Coca-Cola',
    expirationDate: '2025-12-10',
  },
  {
    id: '6',
    type: 'category',
    discountDetails: '$5 off',
    categoryOrBrand: 'Dairy Products',
    expirationDate: '2025-11-28',
  },
]

// Mock product data - will be replaced with real data from backend
const mockProducts: Product[] = [
  {
    id: '1',
    name: 'CVS Durable Nitrile Exam Gloves',
    imageUrl: 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400',
    price: 15.79,
    rating: 5,
    reviewCount: 205,
    category: 'Health',
    inStock: true
  },
  {
    id: '2',
    name: 'CVS Extra Strength Acetaminophen Pain Reliever, 500 mg',
    imageUrl: 'https://images.unsplash.com/photo-1587854692152-cbe660dbde88?w=400',
    price: 10.49,
    rating: 5,
    reviewCount: 345,
    category: 'Health',
    inStock: true
  },
  {
    id: '3',
    name: "Nature's Bounty Magnesium Tablets 500mg",
    imageUrl: 'https://images.unsplash.com/photo-1550572017-4340e44c1f6a?w=400',
    price: 19.49,
    rating: 5,
    reviewCount: 162,
    promoText: 'Buy 1, Get 1 Free',
    category: 'Vitamins',
    inStock: true
  },
  {
    id: '4',
    name: 'One+other Premium Cotton Rounds',
    imageUrl: 'https://images.unsplash.com/photo-1556228720-195a672e8a03?w=400',
    price: 4.19,
    rating: 5,
    reviewCount: 273,
    promoText: 'Buy 2, Get 1 Free',
    category: 'Beauty',
    inStock: true
  },
]

export function MainLayout() {
  const [transcript, setTranscript] = useState<string>('')
  const [products] = useState<Product[]>(mockProducts)
  const { user, signOut } = useAuth()

  // This will be replaced with actual search logic when backend is connected
  const handleTranscriptChange = (newTranscript: string) => {
    setTranscript(newTranscript)
    console.log('Searching for:', newTranscript)
    // TODO: Implement PostgreSQL search when backend is ready
  }

  const handleSignOut = async () => {
    await signOut()
  }

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex w-full min-h-screen">
        <VoiceSidebar onTranscriptChange={handleTranscriptChange} />
        <SidebarInset>
          <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-3 border-b border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-6">
            <h1 className="text-xl font-bold">
              {transcript ? 'Recommended for you' : 'VoiceOffers'}
            </h1>
            <div className="flex items-center gap-4">
              {user && (
                <>
                  <span className="text-sm text-muted-foreground">{user.email}</span>
                  <Button variant="outline" size="sm" onClick={handleSignOut}>
                    Sign Out
                  </Button>
                </>
              )}
            </div>
          </header>
          <main className="flex-1 p-6">
            <div className="max-w-7xl mx-auto">
              {/* Three-column grid */}
              <div className="grid grid-cols-1 gap-6 px-4 sm:px-6 lg:px-8 lg:gap-8" style={{ gridTemplateColumns: 'repeat(1, minmax(0, 1fr))' }} data-lg-grid="true">
                <style>{`
                  @media (min-width: 1024px) {
                    [data-lg-grid="true"] {
                      grid-template-columns: 1.15fr 1fr 1fr !important;
                    }
                  }
                `}</style>
                
                {/* LEFT COLUMN: Products */}
                <div className="space-y-4">
                  <div className="mb-6">
                    <h2 className="text-2xl font-bold mb-1">
                      Recommended for you
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      {transcript ? `Products matching "${transcript}"` : 'Popular products'}
                    </p>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
                    {products.map((product) => (
                      <ProductCard key={product.id} product={product} />
                    ))}
                  </div>
                </div>

                {/* MIDDLE COLUMN: Front-store Offers */}
                <div className="space-y-4">
                  <div className="mb-6">
                    <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-1">
                      Front-store Offers
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      Discounts on entire basket
                    </p>
                  </div>
                  <div className="space-y-4">
                    {mockFrontstoreCoupons.map((coupon) => (
                      <CouponCard key={coupon.id} coupon={coupon} />
                    ))}
                  </div>
                </div>

                {/* RIGHT COLUMN: Category & Brand Offers */}
                <div className="space-y-4">
                  <div className="mb-6">
                    <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-1">
                      Category & Brand Offers
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      {transcript ? `Results for "${transcript}"` : 'Use voice to search'}
                    </p>
                  </div>
                  <div className="space-y-4">
                    {mockCategoryBrandCoupons.map((coupon) => (
                      <CouponCard key={coupon.id} coupon={coupon} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  )
}
