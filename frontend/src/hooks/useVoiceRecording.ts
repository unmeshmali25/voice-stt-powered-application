import { useState, useCallback, useRef } from 'react'

interface VoiceRecordingState {
  isRecording: boolean
  transcript: string | null
  error: string | null
  latency: number | null
}

interface UseVoiceRecordingReturn extends VoiceRecordingState {
  startRecording: () => Promise<void>
  stopRecording: () => void
  clearTranscript: () => void
}

const chooseMimeType = (): string => {
  const preferred = ['audio/webm;codecs=opus', 'audio/webm']
  for (const mimeType of preferred) {
    if (MediaRecorder.isTypeSupported(mimeType)) {
      return mimeType
    }
  }
  return '' // Let browser decide
}

export function useVoiceRecording(): UseVoiceRecordingReturn {
  const [isRecording, setIsRecording] = useState(false)
  const [transcript, setTranscript] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [latency, setLatency] = useState<number | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const autoStopTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const handleStopRecording = useCallback(async () => {
    try {
      const blob = new Blob(chunksRef.current, {
        type: chunksRef.current[0]?.type || 'audio/webm',
      })

      // Send to backend
      const t0 = performance.now()
      const formData = new FormData()
      const ext = blob.type.includes('wav') ? 'wav' : 'webm'
      formData.append('file', blob, `audio.${ext}`)

      const response = await fetch('/api/stt', {
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
        throw new Error(`STT error: ${response.status} - ${errorDetail}`)
      }

      const data = await response.json()
      const transcriptText = data?.transcript?.trim() || ''
      const totalLatency = t1 - t0

      setTranscript(transcriptText)
      setLatency(totalLatency)
      setError(null)

      console.log('Transcript:', transcriptText)
      console.log(`Latency: ${Math.round(totalLatency)}ms (Total), ${data.api_duration_ms || 'n/a'}ms (API)`)

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err)
      setError(errorMessage)
      console.error('Recording error:', errorMessage)
    } finally {
      // Cleanup media tracks
      if (mediaRecorderRef.current?.stream) {
        mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop())
      }
      chunksRef.current = []
    }
  }, [])

  const startRecording = useCallback(async () => {
    if (isRecording) return

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError('Microphone not available')
      console.error('MediaDevices.getUserMedia not supported')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = chooseMimeType()

      chunksRef.current = []
      mediaRecorderRef.current = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : {}
      )

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      mediaRecorderRef.current.onstop = handleStopRecording

      mediaRecorderRef.current.start()
      setIsRecording(true)
      setError(null)
      setTranscript(null)

      console.log('Recording started...')

      // Auto-stop after 7 seconds
      autoStopTimeoutRef.current = setTimeout(() => {
        if (isRecording) {
          stopRecording()
        }
      }, 7000)

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err)
      setError(`Failed to access microphone: ${errorMessage}`)
      console.error('Error starting recording:', err)
    }
  }, [isRecording, handleStopRecording])

  const stopRecording = useCallback(() => {
    if (!isRecording || !mediaRecorderRef.current) return

    setIsRecording(false)

    if (autoStopTimeoutRef.current) {
      clearTimeout(autoStopTimeoutRef.current)
      autoStopTimeoutRef.current = null
    }

    try {
      mediaRecorderRef.current.stop()
      console.log('Recording stopped. Processing...')
    } catch (err) {
      console.error('Error stopping recorder:', err)
    }
  }, [isRecording])

  const clearTranscript = useCallback(() => {
    setTranscript(null)
    setError(null)
    setLatency(null)
  }, [])

  return {
    isRecording,
    transcript,
    error,
    latency,
    startRecording,
    stopRecording,
    clearTranscript,
  }
}
