import { useState, useCallback, useRef } from 'react'
import { apiFetch } from '@/lib/api'

interface FrameCaptureState {
  isProcessing: boolean
  lastCapturedImage: string | null
  error: string | null
  lastResult: ImageExtractionResult | null
}

interface ImageExtractionResult {
  product_name: string | null
  brand: string | null
  category: string | null
  confidence: number
  searchQuery: string
  raw_response?: string
}

interface UseFrameCaptureReturn extends FrameCaptureState {
  captureFrame: (videoElement: HTMLVideoElement) => Promise<ImageExtractionResult | null>
  clearResult: () => void
}

export function useFrameCapture(): UseFrameCaptureReturn {
  const [isProcessing, setIsProcessing] = useState(false)
  const [lastCapturedImage, setLastCapturedImage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<ImageExtractionResult | null>(null)

  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const captureFrame = useCallback(async (videoElement: HTMLVideoElement): Promise<ImageExtractionResult | null> => {
    if (isProcessing) {
      console.log('Frame capture already in progress, skipping...')
      return null
    }

    if (!videoElement || videoElement.readyState !== videoElement.HAVE_ENOUGH_DATA) {
      console.warn('Video not ready for frame capture')
      return null
    }

    try {
      setIsProcessing(true)
      setError(null)

      // Create canvas if it doesn't exist
      if (!canvasRef.current) {
        canvasRef.current = document.createElement('canvas')
      }

      const canvas = canvasRef.current
      const ctx = canvas.getContext('2d')

      if (!ctx) {
        throw new Error('Failed to get canvas context')
      }

      // Set canvas dimensions to match video (or smaller for optimization)
      const width = Math.min(videoElement.videoWidth, 1280)
      const height = Math.min(videoElement.videoHeight, 720)
      canvas.width = width
      canvas.height = height

      // Draw current video frame to canvas
      ctx.drawImage(videoElement, 0, 0, width, height)

      // Convert canvas to blob
      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob(
          (blob) => resolve(blob),
          'image/jpeg',
          0.85 // Quality: 85%
        )
      })

      if (!blob) {
        throw new Error('Failed to create image blob')
      }

      // Store preview (optional - for debugging)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.85)
      setLastCapturedImage(dataUrl)

      console.log(`Frame captured: ${width}x${height}, ${(blob.size / 1024).toFixed(1)}KB`)

      // Upload to backend
      const t0 = performance.now()
      const formData = new FormData()
      formData.append('file', blob, 'frame.jpg')

      const response = await apiFetch('/api/image-extract', {
        method: 'POST',
        body: formData,
      })

      const t1 = performance.now()

      if (!response.ok) {
        let errorDetail = response.statusText
        try {
          const errorData = await response.json()
          errorDetail = errorData.detail || response.statusText
        } catch {
          // Use statusText if JSON parsing fails
        }
        throw new Error(`Image analysis error: ${response.status} - ${errorDetail}`)
      }

      const result: ImageExtractionResult = await response.json()
      const latency = t1 - t0

      console.log('Frame analysis result:', result)
      console.log(`Analysis latency: ${Math.round(latency)}ms`)

      setLastResult(result)
      setError(null)

      return result

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err)
      setError(errorMessage)
      console.error('Frame capture error:', errorMessage)
      throw new Error(errorMessage)
    } finally {
      setIsProcessing(false)
    }
  }, [isProcessing])

  const clearResult = useCallback(() => {
    setLastResult(null)
    setLastCapturedImage(null)
    setError(null)
  }, [])

  return {
    isProcessing,
    lastCapturedImage,
    error,
    lastResult,
    captureFrame,
    clearResult,
  }
}
