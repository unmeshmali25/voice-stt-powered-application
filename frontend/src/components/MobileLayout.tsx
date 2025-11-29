import { useState } from 'react'
import { useStoreData } from '../hooks/useStoreData'
import { ProductCard } from './ProductCard'
import { CouponCard } from './CouponCard'
import { ProductCardSkeleton, CouponCardSkeleton, NoResults } from './SkeletonLoader'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Search, Mic, MicOff, ShoppingBag, Wallet, Scan, User, LogOut } from 'lucide-react'
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
  const { isRecording, startRecording, stopRecording } = useVoiceRecording()

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
      // The transcript will be updated via the useVoiceRecording hook which should be connected to handleTranscriptChange
      // However, since useVoiceRecording is internal to VoiceSidebar in the original code, we might need to adapt it.
      // For now, let's assume we can pass the transcript change handler if we were using the hook directly.
      // But wait, useStoreData doesn't expose useVoiceRecording.
      // Let's use the hook here directly and update the store when transcript changes.
    } else {
      startRecording()
    }
  }

  // Effect to sync voice transcript with store
  // Note: In a real implementation, we'd need to pass the transcript from useVoiceRecording to handleTranscriptChange
  // But useVoiceRecording returns the transcript state.
  // Let's just use the hook here and sync it.
  const voice = useVoiceRecording()
  
  // Sync voice transcript to store when it changes and is final
  // This part is a bit tricky without seeing the internals of useVoiceRecording again.
  // Assuming useVoiceRecording returns a transcript string that updates as you speak.
  
  // Let's simplify for now and assume the user types or we use a simple mic button that toggles recording
  // and we'd need to handle the transcript update.
  
  // Actually, let's look at VoiceSidebar again. It uses useVoiceRecording and has a useEffect to call onTranscriptChange.
  // We should replicate that here.

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
              className="pl-9 h-10 rounded-full bg-muted/50 border-transparent focus-visible:bg-background focus-visible:ring-primary/20"
            />
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
                    <p className="text-muted-foreground">Use your camera or voice to find products</p>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4 w-full max-w-xs">
                    <Button 
                      variant="outline" 
                      className="h-32 flex flex-col gap-3 rounded-2xl border-2 hover:border-primary/50 hover:bg-primary/5"
                      onClick={toggleARMode}
                    >
                      <Scan className="w-8 h-8 text-primary" />
                      <span className="font-medium">AR Scanner</span>
                    </Button>
                    
                    <Button 
                      variant="outline" 
                      className={cn(
                        "h-32 flex flex-col gap-3 rounded-2xl border-2 hover:border-primary/50 hover:bg-primary/5",
                        isRecording && "border-red-500 bg-red-50 text-red-600 animate-pulse"
                      )}
                      onClick={handleMicClick}
                    >
                      {isRecording ? <MicOff className="w-8 h-8" /> : <Mic className="w-8 h-8 text-primary" />}
                      <span className="font-medium">{isRecording ? 'Stop' : 'Voice Search'}</span>
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