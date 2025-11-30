import { useState, useEffect } from 'react'
import { useStoreData } from '../hooks/useStoreData'
import { ProductCard } from './ProductCard'
import { CouponCard } from './CouponCard'
import { ProductCardSkeleton, CouponCardSkeleton, NoResults } from './SkeletonLoader'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Search, Mic, MicOff, ShoppingBag, Wallet, Scan, LogOut } from 'lucide-react'
import { cn } from '../lib/utils'
import { useVoiceRecording } from '../hooks/useVoiceRecording'
import { ARCameraView } from './ARCameraView'

export function MobileLayout() {
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

  const [activeTab, setActiveTab] = useState<'shop' | 'wallet' | 'scan'>('shop')
  const [searchQuery, setSearchQuery] = useState('')
  const { isRecording, startRecording, stopRecording, transcript: voiceTranscript } = useVoiceRecording()

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      handleTranscriptChange(searchQuery)
      setActiveTab('shop')
    }
  }

  const handleMicClick = () => {
    if (isRecording) {
      stopRecording()
    } else {
      startRecording()
    }
  }

  // Sync voice transcript to store and local input
  useEffect(() => {
    if (voiceTranscript) {
      setSearchQuery(voiceTranscript)
      handleTranscriptChange(voiceTranscript)
    }
  }, [voiceTranscript, handleTranscriptChange])

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b border-border/50 px-4 py-3">
        <div className="flex items-center gap-3">
          <form onSubmit={handleSearchSubmit} className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search products..."
              className="pl-9 pr-10 h-10 rounded-full bg-muted/50 border-transparent focus-visible:bg-background focus-visible:ring-primary/20"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className={cn(
                "absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8 rounded-full hover:bg-background/50 transition-colors text-muted-foreground hover:text-foreground",
                isRecording && "bg-red-100 text-red-600 hover:bg-red-200 hover:text-red-700"
              )}
              onClick={handleMicClick}
            >
              {isRecording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            </Button>
          </form>
          {user && (
            <Button variant="ghost" size="icon" className="rounded-full" onClick={() => signOut()}>
              <LogOut className="h-5 w-5 text-muted-foreground" />
            </Button>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto pb-20 px-4 py-4">
        {isARMode ? (
           <ARCameraView
             onExit={toggleARMode}
             onSearchTrigger={handleARSearch}
           />
        ) : (
          <>
            {activeTab === 'shop' && (
              <div className="space-y-6">
                {/* Coupons Section (Visible when searching or recommended) */}
                {(frontstoreCoupons.length > 0 || categoryBrandCoupons.length > 0) && (
                  <div className="space-y-3">
                    <h2 className="text-sm font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                      <span className="text-red-500">🎁</span>
                      Available Coupons
                    </h2>
                    <div className="flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-hide">
                      {frontstoreCoupons.map(coupon => (
                        <div key={coupon.id} className="min-w-[280px]">
                          <CouponCard coupon={coupon} size="compact" />
                        </div>
                      ))}
                      {categoryBrandCoupons.map(coupon => (
                        <div key={coupon.id} className="min-w-[280px]">
                          <CouponCard coupon={coupon} size="compact" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Products Section */}
                <div>
                  <h2 className="text-lg font-bold mb-3">
                    {transcript ? 'Search Results' : 'Recommended for You'}
                  </h2>
                  
                  {isLoadingProducts ? (
                    <div className="grid grid-cols-2 gap-4">
                      {[...Array(4)].map((_, i) => (
                        <ProductCardSkeleton key={i} />
                      ))}
                    </div>
                  ) : products.length > 0 ? (
                    <div className="grid grid-cols-2 gap-4">
                      {products.map(product => (
                        <ProductCard key={product.id} product={product} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <NoResults query={transcript} />
                      <div className="mt-8 text-left">
                        <h3 className="text-lg font-semibold mb-4">Suggested Products</h3>
                        <div className="grid grid-cols-2 gap-4">
                          {mockProducts.slice(0, 4).map(product => (
                            <ProductCard key={product.id} product={product} />
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'wallet' && (
              <div className="space-y-6">
                {/* Coupons Section */}
                <div>
                  <h2 className="text-lg font-bold mb-3 flex items-center gap-2">
                    <span className="text-red-500">🎁</span>
                    Your Wallet
                  </h2>
                  
                  <div className="space-y-4">
                    <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Front-store Offers</h3>
                    {isLoadingCoupons ? (
                      [...Array(2)].map((_, i) => <CouponCardSkeleton key={i} />)
                    ) : frontstoreCoupons.length > 0 ? (
                      frontstoreCoupons.map(coupon => (
                        <CouponCard key={coupon.id} coupon={coupon} />
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground italic">No front-store coupons available.</p>
                    )}
                  </div>

                  <div className="space-y-4 mt-6">
                    <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Category & Brand Offers</h3>
                    {isLoadingCoupons ? (
                      [...Array(2)].map((_, i) => <CouponCardSkeleton key={i} />)
                    ) : categoryBrandCoupons.length > 0 ? (
                      <>
                        {categoryBrandCoupons.slice(0, categoryBrandVisibleCount).map(coupon => (
                          <CouponCard key={coupon.id} coupon={coupon} />
                        ))}
                        {categoryBrandCoupons.length > categoryBrandVisibleCount && (
                          <Button variant="outline" className="w-full" onClick={handleLoadMoreCoupons}>
                            Load More
                          </Button>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground italic">No category coupons available.</p>
                    )}
                  </div>
                </div>
              </div>
            )}
            
            {activeTab === 'scan' && (
               <div className="flex flex-col items-center justify-center h-full space-y-6 py-12">
                  <div className="text-center space-y-2">
                    <h2 className="text-2xl font-bold">Scan & Search</h2>
                    <p className="text-muted-foreground">Use your camera to find products</p>
                  </div>
                  
                  <div className="w-full max-w-xs">
                    <Button
                      variant="outline"
                      className="w-full h-32 flex flex-col gap-3 rounded-2xl border-2 hover:border-primary/50 hover:bg-primary/5"
                      onClick={toggleARMode}
                    >
                      <Scan className="w-12 h-12 text-primary" />
                      <span className="text-lg font-medium">Start AR Scanner</span>
                    </Button>
                  </div>
               </div>
            )}
          </>
        )}
      </main>

      {/* Bottom Navigation */}
      {!isARMode && (
        <nav className="fixed bottom-0 left-0 right-0 bg-background border-t border-border/50 pb-safe">
          <div className="flex items-center justify-around h-16">
            <button 
              onClick={() => setActiveTab('shop')}
              className={cn(
                "flex flex-col items-center justify-center w-full h-full gap-1 transition-colors",
                activeTab === 'shop' ? "text-primary" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <ShoppingBag className={cn("h-6 w-6", activeTab === 'shop' && "fill-current")} />
              <span className="text-[10px] font-medium">Shop</span>
            </button>
            
            <button 
              onClick={() => setActiveTab('scan')}
              className={cn(
                "flex flex-col items-center justify-center w-full h-full gap-1 transition-colors",
                activeTab === 'scan' ? "text-primary" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <div className={cn(
                "p-3 rounded-full -mt-6 shadow-lg border transition-all",
                activeTab === 'scan' 
                  ? "bg-primary text-primary-foreground border-primary" 
                  : "bg-background border-border text-foreground"
              )}>
                <Scan className="h-6 w-6" />
              </div>
              <span className="text-[10px] font-medium mt-1">Scan</span>
            </button>
            
            <button 
              onClick={() => setActiveTab('wallet')}
              className={cn(
                "flex flex-col items-center justify-center w-full h-full gap-1 transition-colors",
                activeTab === 'wallet' ? "text-primary" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Wallet className={cn("h-6 w-6", activeTab === 'wallet' && "fill-current")} />
              <span className="text-[10px] font-medium">Wallet</span>
            </button>
          </div>
        </nav>
      )}
    </div>
  )
}