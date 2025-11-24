import { useState, useCallback, useRef, useEffect } from 'react'

interface CameraStreamState {
  isActive: boolean
  error: string | null
  hasPermission: boolean | null
}

interface UseCameraStreamReturn extends CameraStreamState {
  videoRef: React.RefObject<HTMLVideoElement>
  startCamera: () => Promise<void>
  stopCamera: () => void
  switchCamera: () => Promise<void>
}

export function useCameraStream(): UseCameraStreamReturn {
  const [isActive, setIsActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasPermission, setHasPermission] = useState<boolean | null>(null)
  const [facingMode, setFacingMode] = useState<'user' | 'environment'>('environment')

  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => {
        track.stop()
        console.log('Camera track stopped:', track.label)
      })
      streamRef.current = null
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    setIsActive(false)
    console.log('Camera stopped')
  }, [])

  const startCamera = useCallback(async () => {
    if (isActive) {
      console.log('Camera already active')
      return
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      const errorMsg = 'Camera not available in this browser'
      setError(errorMsg)
      setHasPermission(false)
      console.error(errorMsg)
      return
    }

    try {
      // Request camera access
      console.log('Requesting camera access...')

      const constraints: MediaStreamConstraints = {
        video: {
          facingMode: facingMode,
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      }

      const stream = await navigator.mediaDevices.getUserMedia(constraints)

      streamRef.current = stream
      setHasPermission(true)
      setError(null)

      // Attach stream to video element
      if (videoRef.current) {
        videoRef.current.srcObject = stream

        // Wait for video to be ready and play
        videoRef.current.onloadedmetadata = async () => {
          if (!videoRef.current) return

          try {
            // Explicitly play the video (required for some browsers)
            await videoRef.current.play()
            console.log('Camera stream started successfully')
            console.log('Video dimensions:', videoRef.current.videoWidth, 'x', videoRef.current.videoHeight)
          } catch (playError) {
            console.error('Failed to play video:', playError)
            // Autoplay might be blocked - video element will still show stream
            // User can click to play manually if needed
          }
        }
      }

      setIsActive(true)

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err)

      // Handle specific error types
      if (errorMessage.includes('Permission denied') || errorMessage.includes('NotAllowedError')) {
        setError('Camera permission denied. Please allow camera access.')
        setHasPermission(false)
      } else if (errorMessage.includes('NotFoundError') || errorMessage.includes('not found')) {
        setError('No camera found on this device.')
        setHasPermission(false)
      } else {
        setError(`Failed to access camera: ${errorMessage}`)
        setHasPermission(false)
      }

      console.error('Error starting camera:', err)
    }
  }, [isActive, facingMode])

  const switchCamera = useCallback(async () => {
    if (!isActive) return

    console.log('Switching camera...')
    stopCamera()

    // Toggle facing mode
    setFacingMode(prev => prev === 'user' ? 'environment' : 'user')

    // Small delay to ensure camera is released
    setTimeout(() => {
      startCamera()
    }, 200)
  }, [isActive, stopCamera, startCamera])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
      }
    }
  }, [])

  return {
    videoRef,
    isActive,
    error,
    hasPermission,
    startCamera,
    stopCamera,
    switchCamera,
  }
}
