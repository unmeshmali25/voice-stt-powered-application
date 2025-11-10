import { useState } from 'react'
import { SidebarProvider, SidebarInset } from './ui/sidebar'
import { VoiceSidebar } from './VoiceSidebar'
import { CouponCard } from './CouponCard'
import { Coupon } from '../types/coupon'

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

export function MainLayout() {
  const [transcript, setTranscript] = useState<string>('')

  // This will be replaced with actual search logic when backend is connected
  const handleTranscriptChange = (newTranscript: string) => {
    setTranscript(newTranscript)
    console.log('Searching for:', newTranscript)
    // TODO: Implement PostgreSQL search when backend is ready
  }

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex w-full min-h-screen">
        <VoiceSidebar onTranscriptChange={handleTranscriptChange} />
        <SidebarInset>
          <header className="sticky top-0 z-10 flex h-16 items-center gap-3 border-b border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-6">
            <div className="w-2.5 h-2.5 rounded-full bg-[#CC0000] shadow-[0_0_10px_rgba(204,0,0,0.6)]"></div>
            <h1 className="text-lg font-semibold tracking-tight">UM Retail Voice Offers</h1>
          </header>
          <main className="flex-1 p-6">
            <div className="max-w-6xl mx-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 px-4 sm:px-6 lg:px-8">
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
