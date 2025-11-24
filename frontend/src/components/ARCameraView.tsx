import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { useCameraStream } from '@/hooks/useCameraStream'
import { useFrameCapture } from '@/hooks/useFrameCapture'
import { CouponCard } from './CouponCard'
import { Button } from './ui/button'
import { X, Camera, Pause, Play, Repeat } from 'lucide-react'
import { Coupon } from '@/types/coupon'
import { apiFetch } from '@/lib/api'

interface ARCameraViewProps {
  onExit: () => void
  onSearchTrigger: (query: string) => Promise<Coupon[]>
}

type DetectedProductInfo = {
  brand: string | null
  category: string | null
  confidence: string | null
  name: string | null
  loading: boolean
  error: string | null
}

export function ARCameraView({ onExit, onSearchTrigger }: ARCameraViewProps) {
  const { videoRef, isActive, error: cameraError, startCamera, stopCamera, switchCamera } = useCameraStream()
  const { isProcessing, captureFrame, clearResult } = useFrameCapture()

  const [coupons, setCoupons] = useState<Coupon[]>([])
  const [isAutoScan, setIsAutoScan] = useState(true)
  const [scanStatus, setScanStatus] = useState<string>('')
  const [detectedProducts, setDetectedProducts] = useState<Set<string>>(new Set())
  const [detectedProduct, setDetectedProduct] = useState<DetectedProductInfo | null>(null)
  const statusResetTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const frontstoreCoupons = useMemo(
    () => coupons.filter(coupon => coupon.type === 'frontstore'),
    [coupons]
  )
  const categoryBrandCoupons = useMemo(
    () => coupons.filter(coupon => coupon.type !== 'frontstore'),
    [coupons]
  )

  const updateScanStatus = useCallback((status: string, duration = 2000) => {
    if (statusResetTimeout.current) {
      clearTimeout(statusResetTimeout.current)
      statusResetTimeout.current = null
    }

    setScanStatus(status)

    if (duration > 0) {
      statusResetTimeout.current = setTimeout(() => {
        setScanStatus('')
        statusResetTimeout.current = null
      }, duration)
    }
  }, [])

  // Keep a stable ref to the latest startCamera
  const startCameraRef = useRef(startCamera)
  useEffect(() => {
    startCameraRef.current = startCamera
  }, [startCamera])

  // Start camera on mount and clean up on unmount
  useEffect(() => {
    startCameraRef.current()

    return () => {
      if (statusResetTimeout.current) {
        clearTimeout(statusResetTimeout.current)
        statusResetTimeout.current = null
      }
      stopCamera()
      clearResult()
      setDetectedProduct(null)
    }
  }, [stopCamera, clearResult])

  const fetchDetectedProductName = useCallback(async (brand: string | null, category: string | null) => {
    const queryParts = [brand, category]
      .filter((part): part is string => !!part && part.trim().length > 0)
      .map(part => part.trim())

    if (queryParts.length === 0) {
      setDetectedProduct(prev => (prev ? { ...prev, loading: false } : prev))
      return
    }

    const query = queryParts.join(' ')
    setDetectedProduct(prev => (prev ? { ...prev, loading: true, error: null } : prev))

    try {
      const response = await apiFetch('/api/products/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query, limit: 1 })
      })

      if (!response.ok) {
        throw new Error(`Product lookup failed (${response.status})`)
      }

      const data = await response.json()
      const topProduct = data?.products?.[0]

      setDetectedProduct(prev =>
        prev
          ? {
              ...prev,
              name: topProduct?.name ?? null,
              brand: prev.brand ?? topProduct?.brand ?? null,
              loading: false
            }
          : prev
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Product lookup failed'
      console.error('Product lookup error:', error)
      setDetectedProduct(prev => (prev ? { ...prev, loading: false, error: message } : prev))
    }
  }, [])

  // Manual frame capture handler
  const handleManualCapture = useCallback(async () => {
    if (!videoRef.current || isProcessing) return

    updateScanStatus('Capturing frame...', 0)

    let result
    try {
      result = await captureFrame(videoRef.current)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Frame capture failed'
      console.error('Capture error:', error)
      updateScanStatus(`Scan failed: ${message}`)
      setDetectedProduct(null)
      return
    }

    if (!result) {
      updateScanStatus('No product detected')
      setDetectedProduct(null)
      return
    }

    const hasProductClues = Boolean(result.brand || result.category)
    setDetectedProduct({
      brand: result.brand ?? null,
      category: result.category ?? null,
      confidence: result.confidence ?? null,
      name: null,
      loading: hasProductClues,
      error: null
    })

    if (hasProductClues) {
      fetchDetectedProductName(result.brand ?? null, result.category ?? null)
    }

    const querySet = new Set<string>()
    const prioritizedQueries: string[] = []
    const addQuery = (value?: string | null) => {
      if (!value) return
      const trimmed = value.trim()
      if (!trimmed) return
      const normalized = trimmed.toLowerCase()
      if (querySet.has(normalized)) return
      querySet.add(normalized)
      prioritizedQueries.push(trimmed)
    }

    const combinedQuery = [result.brand, result.category].filter(Boolean).join(' ').trim()
    addQuery(combinedQuery)
    addQuery(result.brand)
    addQuery(result.category)
    addQuery(result.searchQuery)

    if (prioritizedQueries.length === 0) {
      updateScanStatus('No recognizable product details')
      setDetectedProduct(prev => (prev ? { ...prev, loading: false } : prev))
      return
    }

    const aggregatedResults: Coupon[] = []
    const aggregatedIds = new Set<string>()
    let hasFrontstoreResult = false
    let hasCategoryBrandResult = false

    for (const query of prioritizedQueries) {
      updateScanStatus(`Searching for coupons (${query})...`, 0)

      try {
        const foundCoupons = await onSearchTrigger(query)
        if (foundCoupons && foundCoupons.length > 0) {
          foundCoupons.forEach(coupon => {
            if (!aggregatedIds.has(coupon.id)) {
              aggregatedIds.add(coupon.id)
              aggregatedResults.push(coupon)
              if (coupon.type === 'frontstore') {
                hasFrontstoreResult = true
              } else {
                hasCategoryBrandResult = true
              }
            }
          })
        }

        if (hasFrontstoreResult && hasCategoryBrandResult) {
          break
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Search failed'
        console.error('Search error:', error)
        updateScanStatus(`Search failed: ${message}`)
      }
    }

    if (aggregatedResults.length === 0) {
      updateScanStatus('No coupons found for this product')
      setDetectedProduct(prev => (prev ? { ...prev, loading: false } : prev))
      return
    }

    let addedCount = 0
    let addedFrontstore = false
    let addedCategoryBrand = false

    setCoupons(prev => {
      const existingIds = new Set(prev.map(c => c.id))
      const uniqueNew = aggregatedResults.filter(c => !existingIds.has(c.id))
      addedCount = uniqueNew.length
      addedFrontstore = uniqueNew.some(c => c.type === 'frontstore')
      addedCategoryBrand = uniqueNew.some(c => c.type !== 'frontstore')
      if (!uniqueNew.length) return prev
      return [...prev, ...uniqueNew]
    })

    if (result.brand || result.category) {
      const productKey = `${result.brand || ''}_${result.category || ''}`
      setDetectedProducts(prev => new Set(prev).add(productKey))
    }

    setDetectedProduct(prev => (prev ? { ...prev, loading: false } : prev))

    if (addedCount === 0) {
      updateScanStatus('Coupons already captured for this product')
    } else {
      const segments: string[] = []
      if (addedFrontstore) segments.push('front-store')
      if (addedCategoryBrand) segments.push('category/brand')
      updateScanStatus(
        `Found ${addedCount} ${segments.join(' & ')} coupon${addedCount > 1 ? 's' : ''}!`
      )
    }
  }, [
    videoRef,
    isProcessing,
    captureFrame,
    onSearchTrigger,
    updateScanStatus,
    fetchDetectedProductName
  ])

  // Auto-scan with interval
  useEffect(() => {
    if (!isAutoScan || !isActive) return

    const intervalId = setInterval(() => {
      if (!isProcessing && videoRef.current) {
        handleManualCapture()
      }
    }, 3000) // Scan every 3 seconds

    return () => clearInterval(intervalId)
  }, [isAutoScan, isActive, isProcessing, handleManualCapture, videoRef])

  // Handle exit with confirmation if coupons found
  const handleExit = useCallback(() => {
    if (coupons.length > 0) {
      const confirmed = window.confirm(
        `You found ${coupons.length} coupon(s). Exit AR mode?`
      )
      if (!confirmed) return
    }

    stopCamera()
    setDetectedProduct(null)
    onExit()
  }, [coupons.length, stopCamera, onExit])

  return (
    <div className="fixed inset-0 z-50 bg-black">
      <div className="h-full flex flex-col md:flex-row">
        {/* Left Panel - Video Feed */}
        <div className="relative flex-1 bg-gray-900">
          {/* Video Element */}
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover bg-black"
            style={{ minHeight: '100%', minWidth: '100%' }}
          />

          {/* Detected product summary */}
          {detectedProduct && (
            <div className="absolute top-4 left-4 right-4 max-w-sm bg-black/70 text-white p-4 rounded-2xl shadow-2xl backdrop-blur">
              <p className="text-xs uppercase tracking-wider text-gray-400 mb-1">
                Detected Product
              </p>
              {detectedProduct.loading ? (
                <p className="text-sm text-gray-200">Identifying product...</p>
              ) : (
                <>
                  <p className="text-lg font-semibold leading-snug">
                    {detectedProduct.name ||
                      [detectedProduct.brand, detectedProduct.category]
                        .filter(Boolean)
                        .join(' · ') ||
                      'No catalog match yet'}
                  </p>
                  <p className="text-sm text-gray-300">
                    {[detectedProduct.brand, detectedProduct.category]
                      .filter(Boolean)
                      .join(' · ') || 'Awaiting brand/category clues'}
                  </p>
                </>
              )}
              {detectedProduct.confidence && (
                <p className="text-xs text-gray-400 mt-1">
                  Confidence: {detectedProduct.confidence}
                </p>
              )}
              {detectedProduct.error && (
                <p className="text-xs text-red-400 mt-1">{detectedProduct.error}</p>
              )}
            </div>
          )}

          {/* Scan Status Overlay */}
          {(isProcessing || scanStatus) && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/30 backdrop-blur-sm pointer-events-none">
              <div className="bg-black/80 text-white px-6 py-4 rounded-lg shadow-2xl flex items-center gap-3">
                {isProcessing && (
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white" />
                )}
                <span className="text-lg font-medium">
                  {isProcessing ? 'Analyzing...' : scanStatus}
                </span>
              </div>
            </div>
          )}

          {/* Scan Line Animation (when auto-scanning) */}
          {isAutoScan && isActive && !isProcessing && (
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
              <div className="absolute w-full h-1 bg-gradient-to-r from-transparent via-[#CC0000] to-transparent animate-scan-line" />
            </div>
          )}

          {/* Camera Error */}
          {cameraError && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/90">
              <div className="text-center text-white px-6">
                <Camera className="w-16 h-16 mx-auto mb-4 text-red-500" />
                <h3 className="text-xl font-semibold mb-2">Camera Error</h3>
                <p className="text-gray-300 mb-4">{cameraError}</p>
                <Button
                  variant="outline"
                  onClick={handleExit}
                  className="!border-white/50 !text-white hover:!bg-white/20 font-semibold"
                  style={{
                    borderColor: 'rgba(255, 255, 255, 0.5)',
                    color: 'white',
                    backgroundColor: 'transparent'
                  }}
                >
                  Exit AR Mode
                </Button>
              </div>
            </div>
          )}

          {/* Control Bar (Bottom) */}
          <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-black/90 via-black/50 to-transparent">
            <div className="flex items-center justify-center gap-4">
              {/* Manual Capture Button */}
              <Button
                size="lg"
                onClick={handleManualCapture}
                disabled={isProcessing || !isActive}
                className="!bg-[#CC0000] hover:!bg-[#AA0000] !text-white font-semibold shadow-lg"
                style={{
                  backgroundColor: '#CC0000',
                  color: 'white',
                  border: 'none'
                }}
              >
                <Camera className="w-5 h-5 mr-2 text-white" />
                Scan Now
              </Button>

              {/* Auto-Scan Toggle */}
              <Button
                size="lg"
                variant="outline"
                onClick={() => setIsAutoScan(!isAutoScan)}
                className="!border-white/50 !text-white hover:!bg-white/20 font-semibold"
                style={{
                  borderColor: 'rgba(255, 255, 255, 0.5)',
                  color: 'white',
                  backgroundColor: 'transparent'
                }}
              >
                {isAutoScan ? (
                  <>
                    <Pause className="w-5 h-5 mr-2 text-white" />
                    Pause Auto-Scan
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5 mr-2 text-white" />
                    Resume Auto-Scan
                  </>
                )}
              </Button>

              {/* Switch Camera (Mobile) */}
              <Button
                size="lg"
                variant="outline"
                onClick={switchCamera}
                disabled={!isActive}
                className="!border-white/50 !text-white hover:!bg-white/20 hidden sm:flex font-semibold"
                style={{
                  borderColor: 'rgba(255, 255, 255, 0.5)',
                  color: 'white',
                  backgroundColor: 'transparent'
                }}
              >
                <Repeat className="w-5 h-5 text-white" />
              </Button>
            </div>
          </div>
        </div>

        {/* Right Panel - Coupon Results */}
        <div className="w-full md:w-[400px] bg-gray-950 border-l border-gray-800 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-800">
            <div>
              <h2 className="text-xl font-bold text-white">
                Found Coupons
              </h2>
              <p className="text-sm text-gray-400 mt-0.5">
                {coupons.length} coupon{coupons.length !== 1 ? 's' : ''} detected
              </p>
            </div>

            {/* Exit Button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={handleExit}
              className="!text-gray-300 hover:!text-white hover:!bg-gray-800"
              style={{ color: 'rgb(209, 213, 219)' }}
            >
              <X className="w-6 h-6" style={{ color: 'rgb(209, 213, 219)' }} />
            </Button>
          </div>

          {/* Coupon List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-6">
            {coupons.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-4 py-12">
                <Camera className="w-16 h-16 text-gray-600 mb-4" />
                <h3 className="text-lg font-semibold text-gray-400 mb-2">
                  No Coupons Yet
                </h3>
                <p className="text-sm text-gray-500">
                  Point your camera at products to find relevant coupons
                </p>
              </div>
            ) : (
              <>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-300">
                      Front-store Coupons
                    </h3>
                    <span className="text-xs text-gray-500">
                      {frontstoreCoupons.length}
                    </span>
                  </div>
                  {frontstoreCoupons.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-gray-800/70 p-4 text-sm text-gray-500">
                      No front-store coupons matched this scan yet.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {frontstoreCoupons.map(coupon => (
                        <CouponCard key={coupon.id} coupon={coupon} />
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-300">
                      Category / Brand Coupons
                    </h3>
                    <span className="text-xs text-gray-500">
                      {categoryBrandCoupons.length}
                    </span>
                  </div>
                  {categoryBrandCoupons.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-gray-800/70 p-4 text-sm text-gray-500">
                      No category or brand coupons matched this scan yet.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {categoryBrandCoupons.map(coupon => (
                        <CouponCard key={coupon.id} coupon={coupon} />
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          {/* Clear Results Button */}
          {coupons.length > 0 && (
            <div className="p-4 border-t border-gray-800">
              <Button
                variant="outline"
                onClick={() => {
                  setCoupons([])
                  setDetectedProducts(new Set())
                  setDetectedProduct(null)
                }}
                className="w-full !border-gray-600 !text-gray-200 hover:!bg-gray-800 font-semibold"
                style={{
                  borderColor: 'rgb(75, 85, 99)',
                  color: 'rgb(229, 231, 235)',
                  backgroundColor: 'transparent'
                }}
              >
                Clear Results
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* CSS for scan line animation */}
      <style>{`
        @keyframes scan-line {
          0% {
            top: -10px;
          }
          100% {
            top: 100%;
          }
        }
        .animate-scan-line {
          animation: scan-line 3s linear infinite;
        }
      `}</style>
    </div>
  )
}
