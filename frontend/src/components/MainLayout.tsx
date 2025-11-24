import { useState, useEffect, useCallback } from 'react'
import { SidebarProvider, SidebarInset } from './ui/sidebar'
import { VoiceSidebar } from './VoiceSidebar'
import { CouponCard } from './CouponCard'
import { ProductCard } from './ProductCard'
import { ChristmasDecorations } from './ChristmasDecorations'
import { ProductCardSkeleton, CouponCardSkeleton, NoResults } from './SkeletonLoader'
import { ARCameraView } from './ARCameraView'
import { Coupon } from '../types/coupon'
import { Product } from '../types/product'
import { useAuth } from '../hooks/useAuth'
import { Button } from './ui/button'
import { supabase } from '../lib/supabase'
import { apiFetch } from '../lib/api'

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
  const [products, setProducts] = useState<Product[]>([])
  const [frontstoreCoupons, setFrontstoreCoupons] = useState<Coupon[]>([])
  const [categoryBrandCoupons, setCategoryBrandCoupons] = useState<Coupon[]>([])
  const [hoveredProductId, setHoveredProductId] = useState<string | null>(null)
  const [isLoadingProducts, setIsLoadingProducts] = useState(false)
  const [isLoadingCoupons, setIsLoadingCoupons] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [isARMode, setIsARMode] = useState(false)
  const { user, signOut } = useAuth()

  const loadRecommendations = useCallback(async () => {
    setIsLoadingProducts(true)

    try {
      // Get auth token
      const { data: { session } } = await supabase.auth.getSession()

      if (!session?.access_token) {
        console.log('No session, showing default products')
        setProducts(mockProducts.slice(0, 5)) // Show 5 mock products as fallback
        return
      }

      // Fetch personalized recommendations
      const response = await apiFetch('/api/products/recommendations?limit=5', {
        method: 'GET'
      })

      if (response.ok) {
        const data = await response.json()
        console.log(`Loaded ${data.count} recommendations (personalized=${data.personalized})`)
        const transformedProducts = data.products.map((p: any) => ({
          id: p.id,
          name: p.name,
          description: p.description,
          imageUrl: p.imageUrl,
          price: p.price,
          rating: p.rating,
          reviewCount: p.reviewCount,
          category: p.category,
          brand: p.brand,
          promoText: p.promoText,
          inStock: p.inStock
        }))
        setProducts(transformedProducts)
      } else {
        // Fallback to mock data
        console.log('Recommendations API failed, using mock data')
        setProducts(mockProducts.slice(0, 5))
      }
    } catch (error) {
      console.error('Failed to load recommendations:', error)
      setProducts(mockProducts.slice(0, 5))
    } finally {
      setIsLoadingProducts(false)
    }
  }, []) // Empty dependency array - only create once

  // Load personalized recommendations on startup (only once)
  useEffect(() => {
    loadRecommendations()
  }, [loadRecommendations])

  const handleTranscriptChange = useCallback(async (newTranscript: string) => {
    setTranscript(newTranscript)
    setHasSearched(true)

    // If transcript is empty, reset to recommendations
    if (!newTranscript.trim()) {
      loadRecommendations()
      setFrontstoreCoupons([])
      setCategoryBrandCoupons([])
      setHasSearched(false)
      return
    }

    // Get auth token
    const { data: { session } } = await supabase.auth.getSession()

    if (!session?.access_token) {
      console.error('No authentication token available')
      return
    }

    // Search products
    setIsLoadingProducts(true)
    try {
      const productsResponse = await apiFetch('/api/products/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query: newTranscript, limit: 50 })
      })

      if (productsResponse.ok) {
        const productsData = await productsResponse.json()
        const transformedProducts = productsData.products.map((p: any) => ({
          id: p.id,
          name: p.name,
          description: p.description,
          imageUrl: p.imageUrl,  // Backend already returns camelCase
          price: p.price,
          rating: p.rating,
          reviewCount: p.reviewCount,  // Backend already returns camelCase
          category: p.category,
          brand: p.brand,
          promoText: p.promoText,  // Backend already returns camelCase
          inStock: p.inStock  // Backend already returns camelCase
        }))
        setProducts(transformedProducts)
      }
    } catch (error) {
      console.error('Product search failed:', error)
    } finally {
      setIsLoadingProducts(false)
    }

    // Search coupons (user-specific only)
    setIsLoadingCoupons(true)
    try {
      const couponsResponse = await apiFetch('/api/coupons/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ question: newTranscript })
      })

      if (couponsResponse.ok) {
        const couponsData = await couponsResponse.json()
        const transformedCoupons = couponsData.results.map((c: any) => ({
          id: c.id,
          type: c.type,
          discountDetails: c.discount_details || c.discountDetails,  // Handle both formats
          categoryOrBrand: c.category_or_brand || c.categoryOrBrand,
          expirationDate: c.expiration_date || c.expirationDate,
          terms: c.terms
        }))

        // Split by type
        const frontstore = transformedCoupons.filter((c: Coupon) => c.type === 'frontstore')
        const categoryBrand = transformedCoupons.filter((c: Coupon) => c.type !== 'frontstore')

        setFrontstoreCoupons(frontstore)
        setCategoryBrandCoupons(categoryBrand)
      }
    } catch (error) {
      console.error('Coupon search failed:', error)
    } finally {
      setIsLoadingCoupons(false)
    }
  }, [loadRecommendations])

  const handleSignOut = async () => {
    await signOut()
  }

  const toggleARMode = useCallback(() => {
    setIsARMode(prev => !prev)
  }, [])

  const handleARSearch = useCallback(async (query: string): Promise<Coupon[]> => {
    // Get auth token
    const { data: { session } } = await supabase.auth.getSession()

    if (!session?.access_token) {
      console.error('No authentication token available')
      return []
    }

    // Search coupons (user-specific only)
    try {
      const couponsResponse = await apiFetch('/api/coupons/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ question: query })
      })

      if (couponsResponse.ok) {
        const couponsData = await couponsResponse.json()
        const transformedCoupons = couponsData.results.map((c: any) => ({
          id: c.id,
          type: c.type,
          discountDetails: c.discount_details || c.discountDetails,
          categoryOrBrand: c.category_or_brand || c.categoryOrBrand,
          expirationDate: c.expiration_date || c.expirationDate,
          terms: c.terms
        }))

        return transformedCoupons
      }
    } catch (error) {
      console.error('AR coupon search failed:', error)
    }

    return []
  }, [])

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex w-full min-h-screen relative">
        <ChristmasDecorations />
        <VoiceSidebar
          onTranscriptChange={handleTranscriptChange}
          onARModeToggle={toggleARMode}
        />
        {isARMode ? (
          <ARCameraView
            onExit={toggleARMode}
            onSearchTrigger={handleARSearch}
          />
        ) : (
          <SidebarInset>
          <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-3 border-b border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-6">
            <h1 className="text-xl font-bold flex items-center gap-2">
              <span className="festive-glow">❄️</span>
              {transcript ? 'Recommended for you' : 'AI Powered Retail App'}
              <span className="festive-glow">🎄</span>
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
              <div className="grid grid-cols-1 gap-6 px-4 sm:px-6 lg:px-8 lg:gap-16" style={{ gridTemplateColumns: 'repeat(1, minmax(0, 1fr))' }} data-lg-grid="true">
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

                  {isLoadingProducts ? (
                    <div className="relative flex flex-col items-start">
                      <div className="w-[72%] relative flex flex-col">
                        {[...Array(5)].map((_, index) => (
                          <div
                            key={index}
                            style={{
                              marginTop: index === 0 ? '0' : '-4rem',
                              zIndex: 10
                            }}
                          >
                            <ProductCardSkeleton />
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : products.length === 0 && hasSearched ? (
                    <>
                      <NoResults query={transcript} />
                      <div className="relative flex flex-col items-start mt-8">
                        <h3 className="text-lg font-semibold mb-4">Suggested Products</h3>
                        <div className="w-[72%] relative flex flex-col">
                          {mockProducts.slice(0, 5).map((product, index) => (
                            <div
                              key={product.id}
                              className={`relative transition-all duration-300 ${
                                hoveredProductId && hoveredProductId !== product.id
                                  ? 'opacity-60'
                                  : 'opacity-100'
                              }`}
                              style={{
                                marginTop: index === 0 ? '0' : '-4rem',
                                zIndex: hoveredProductId === product.id ? 50 : 10
                              }}
                              onMouseEnter={() => setHoveredProductId(product.id)}
                              onMouseLeave={() => setHoveredProductId(null)}
                            >
                              <ProductCard product={product} />
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="relative flex flex-col items-start">
                      <div className="w-[72%] relative flex flex-col">
                        {products.map((product, index) => (
                          <div
                            key={product.id}
                            className={`relative transition-all duration-300 ${
                              hoveredProductId && hoveredProductId !== product.id
                                ? 'opacity-60'
                                : 'opacity-100'
                            }`}
                            style={{
                              marginTop: index === 0 ? '0' : '-4rem',
                              zIndex: hoveredProductId === product.id ? 50 : 10
                            }}
                            onMouseEnter={() => setHoveredProductId(product.id)}
                            onMouseLeave={() => setHoveredProductId(null)}
                          >
                            <ProductCard product={product} />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* MIDDLE COLUMN: Front-store Offers */}
                <div className="space-y-4">
                  <div className="mb-6">
                    <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-1 flex items-center gap-2">
                      <span className="text-red-500">🎁</span>
                      Front-store Offers
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      Discounts on entire basket
                    </p>
                  </div>
                  <div className="space-y-4">
                    {isLoadingCoupons ? (
                      <>
                        {[...Array(3)].map((_, index) => (
                          <CouponCardSkeleton key={index} />
                        ))}
                      </>
                    ) : frontstoreCoupons.length === 0 ? (
                      <div className="text-sm text-muted-foreground text-center py-8">
                        {hasSearched ? 'No frontstore coupons match your search' : 'No frontstore coupons available'}
                      </div>
                    ) : (
                      frontstoreCoupons.map((coupon) => (
                        <CouponCard key={coupon.id} coupon={coupon} />
                      ))
                    )}
                  </div>
                </div>

                {/* RIGHT COLUMN: Category & Brand Offers */}
                <div className="space-y-4">
                  <div className="mb-6">
                    <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-1 flex items-center gap-2">
                      <span className="text-green-600">✨</span>
                      Category & Brand Offers
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      {transcript ? `Results for "${transcript}"` : 'Use voice to search'}
                    </p>
                  </div>
                  <div className="space-y-4">
                    {isLoadingCoupons ? (
                      <>
                        {[...Array(3)].map((_, index) => (
                          <CouponCardSkeleton key={index} />
                        ))}
                      </>
                    ) : categoryBrandCoupons.length === 0 ? (
                      <div className="text-sm text-muted-foreground text-center py-8">
                        {hasSearched ? 'No category/brand coupons match your search' : 'Use voice search to find relevant coupons'}
                      </div>
                    ) : (
                      categoryBrandCoupons.map((coupon) => (
                        <CouponCard key={coupon.id} coupon={coupon} />
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </main>
        </SidebarInset>
        )}
      </div>
    </SidebarProvider>
  )
}
