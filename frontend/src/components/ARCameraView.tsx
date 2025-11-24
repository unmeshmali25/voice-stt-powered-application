import { useEffect, useState, useCallback } from 'react'
import { useCameraStream } from '@/hooks/useCameraStream'
import { useFrameCapture } from '@/hooks/useFrameCapture'
import { CouponCard } from './CouponCard'
import { Button } from './ui/button'
import { X, Camera, Pause, Play, Repeat } from 'lucide-react'
import { Coupon } from '@/types/coupon'

interface ARCameraViewProps {
  onExit: () => void
  onSearchTrigger: (query: string) => Promise<Coupon[]>
}

export function ARCameraView({ onExit, onSearchTrigger }: ARCameraViewProps) {
  const { videoRef, isActive, error: cameraError, startCamera, stopCamera, switchCamera } = useCameraStream()
  const { isProcessing, lastResult, captureFrame, clearResult } = useFrameCapture()

  const [coupons, setCoupons] = useState<Coupon[]>([])
  const [isAutoScan, setIsAutoScan] = useState(true)
  const [scanStatus, setScanStatus] = useState<string>('')
  const [detectedProducts, setDetectedProducts] = useState<Set<string>>(new Set())

  // Start camera on mount
  useEffect(() => {
    startCamera()

    return () => {
      stopCamera()
      clearResult()
    }
  }, [startCamera, stopCamera, clearResult])

  // Manual frame capture handler
  const handleManualCapture = useCallback(async () => {
    if (!videoRef.current || isProcessing) return

    setScanStatus('Capturing frame...')

    const result = await captureFrame(videoRef.current)

    if (result && result.searchQuery) {
      setScanStatus('Searching for coupons...')

      try {
        const foundCoupons = await onSearchTrigger(result.searchQuery)

        if (foundCoupons && foundCoupons.length > 0) {
          // Deduplicate by ID
          setCoupons(prev => {
            const existingIds = new Set(prev.map(c => c.id))
            const newCoupons = foundCoupons.filter(c => !existingIds.has(c.id))
            return [...prev, ...newCoupons]
          })

          // Track detected product to avoid re-scanning
          if (result.brand || result.category) {
            const productKey = `${result.brand || ''}_${result.category || ''}`
            setDetectedProducts(prev => new Set(prev).add(productKey))
          }

          setScanStatus(`Found ${foundCoupons.length} new coupons!`)
        } else {
          setScanStatus('No coupons found for this product')
        }
      } catch (error) {
        console.error('Search error:', error)
        setScanStatus('Search failed')
      }

      // Clear status after 2 seconds
      setTimeout(() => setScanStatus(''), 2000)
    } else {
      setScanStatus('No product detected')
      setTimeout(() => setScanStatus(''), 2000)
    }
  }, [videoRef, isProcessing, captureFrame, onSearchTrigger])

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
            playsInline
            muted
            className="w-full h-full object-cover bg-black"
            style={{ minHeight: '100%', minWidth: '100%' }}
          />

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
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
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
              coupons.map(coupon => (
                <CouponCard key={coupon.id} coupon={coupon} />
              ))
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
