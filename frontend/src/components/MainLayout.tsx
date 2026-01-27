import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SidebarProvider, SidebarInset } from './ui/sidebar'
import { VoiceSidebar } from './VoiceSidebar'
import { CouponCard } from './CouponCard'
import { ProductCard } from './ProductCard'
import { ChristmasDecorations } from './ChristmasDecorations'
import { ProductCardSkeleton, CouponCardSkeleton, NoResults } from './SkeletonLoader'
import { ARCameraView } from './ARCameraView'
import { Button } from './ui/button'
import { useStoreData } from '../hooks/useStoreData'
import { StoreSelector } from './StoreSelector'
import { CartDrawer } from './CartDrawer'
import { ClipboardList } from 'lucide-react'

export function MainLayout() {
  const navigate = useNavigate()
  const {
    transcript,
    products,
    frontstoreCoupons,
    categoryBrandCoupons,
    isLoadingProducts,
    isLoadingCoupons,
    hasSearched,
    isARMode,
    isWalletView,
    categoryBrandVisibleCount,
    user,
    signOut,
    handleTranscriptChange,
    handleLoadMoreCoupons,
    toggleARMode,
    handleARSearch,
    mockProducts
  } = useStoreData()

  const [hoveredProductId, setHoveredProductId] = useState<string | null>(null)

  const handleSignOut = async () => {
    await signOut()
  }

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
            <h1 className="text-xl font-bold flex items-center gap-2 cursor-pointer" onClick={() => navigate('/')}>
              <span className="festive-glow">❄️</span>
              {transcript ? 'Recommended for you' : 'AI Powered Retail App'}
              <span className="festive-glow">🎄</span>
            </h1>
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate('/orders')} title="Order History">
                <ClipboardList className="h-5 w-5" />
              </Button>
              <StoreSelector />
              <CartDrawer />
              {user && (
                <>
                  <span className="text-sm text-muted-foreground hidden md:inline">{user.email}</span>
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
                      {transcript ? 'Products found' : 'Recommended for you'}
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
                      {isWalletView ? 'Coupons in Wallet' : 'Applicable Coupons'}
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      {isWalletView ? 'Basket-offers discounts' : 'Basket-offers matching your search'}
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
                        {hasSearched
                          ? 'No basket-offers match your search'
                          : (isWalletView ? 'No basket-offers in your wallet' : 'No basket-offers available')
                        }
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
                      {isWalletView ? 'Category & Brand' : 'Applicable Offers'}
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      {isWalletView
                        ? 'Product-specific discounts'
                        : (transcript ? `Results for "${transcript}"` : 'Search results')
                      }
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
                        {hasSearched
                          ? 'No category/brand coupons match your search'
                          : (isWalletView ? 'No category/brand coupons in your wallet' : 'Use voice search to find relevant coupons')
                        }
                      </div>
                    ) : (
                      <>
                        {categoryBrandCoupons.slice(0, categoryBrandVisibleCount).map((coupon) => (
                          <CouponCard key={coupon.id} coupon={coupon} />
                        ))}

                        {categoryBrandCoupons.length > categoryBrandVisibleCount && (
                          <Button
                            variant="outline"
                            onClick={handleLoadMoreCoupons}
                            className="w-full mt-2"
                          >
                            Load More ({categoryBrandCoupons.length - categoryBrandVisibleCount} remaining)
                          </Button>
                        )}
                      </>
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
