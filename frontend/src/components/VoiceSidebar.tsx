import { useEffect, useState, useRef } from 'react'
import { Mic, MicOff, Camera, Loader2 } from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
} from './ui/sidebar'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Glass } from './ui/glass'
import { Badge } from './ui/badge'
import { useVoiceRecording } from '../hooks/useVoiceRecording'
import { ImageExtractionResult } from '../types/coupon'
import { apiFetch } from '../lib/api'

// Discord icon component
function DiscordIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="#5865F2"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z" />
    </svg>
  )
}

interface VoiceSidebarProps {
  onTranscriptChange?: (transcript: string) => void
}

export function VoiceSidebar({ onTranscriptChange }: VoiceSidebarProps) {
  const { isRecording, transcript, error, latency, startRecording, stopRecording } = useVoiceRecording()
  const [textInput, setTextInput] = useState('')
  const [statusDisplay, setStatusDisplay] = useState<{ type: 'transcript' | 'search', value: string } | null>(null)
  const [isUploadingImage, setIsUploadingImage] = useState(false)
  const [imageResult, setImageResult] = useState<ImageExtractionResult | null>(null)
  const [imageError, setImageError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (transcript) {
      setStatusDisplay({ type: 'transcript', value: transcript })
      if (onTranscriptChange) {
        onTranscriptChange(transcript)
      }
    } else if (isRecording) {
      setStatusDisplay(null)
    }
  }, [transcript, isRecording, onTranscriptChange])

  const handleMicClick = () => {
    if (isRecording) {
      stopRecording()
    } else {
      // Clear image results when starting voice recording
      setImageResult(null)
      setImageError(null)
      startRecording()
    }
  }


  const handleTextKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && textInput.trim()) {
      const searchValue = textInput.trim()
      // Clear image results when submitting text search
      setImageResult(null)
      setImageError(null)
      setStatusDisplay({ type: 'search', value: searchValue })
      if (onTranscriptChange) {
        onTranscriptChange(searchValue)
      }
      setTextInput('')
    }
  }

  const handleCameraClick = () => {
    // Trigger file input
    fileInputRef.current?.click()
  }

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    if (!allowedTypes.includes(file.type)) {
      setImageError('Please upload a JPEG, PNG, or WebP image')
      return
    }

    // Validate file size (max 5MB)
    const maxSizeMB = 5
    if (file.size > maxSizeMB * 1024 * 1024) {
      setImageError(`Image too large. Maximum size is ${maxSizeMB}MB`)
      return
    }

    setIsUploadingImage(true)
    setImageError(null)
    setImageResult(null)

    try {
      // Create FormData
      const formData = new FormData()
      formData.append('file', file)

      // Call API
      const response = await apiFetch('/api/image-extract', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to extract image data' }))
        throw new Error(errorData.detail || 'Image extraction failed')
      }

      const result: ImageExtractionResult = await response.json()
      setImageResult(result)

      // Trigger search if we have a query
      if (result.searchQuery && onTranscriptChange) {
        onTranscriptChange(result.searchQuery)
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to process image'
      setImageError(errorMessage)
      console.error('Image upload error:', err)
    } finally {
      setIsUploadingImage(false)
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  return (
    <Sidebar collapsible="none" className="h-screen">
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <div className="flex flex-col items-center gap-6 py-8 px-4">
              {/* Microphone with Glass Design */}
              <Glass className="w-full h-32 p-6 flex items-center justify-center">
                <Button
                  onClick={handleMicClick}
                  size="lg"
                  className={`
                    w-12 h-12 rounded-full text-2xl transition-all duration-300
                    ${isRecording
                      ? 'bg-red-600 hover:bg-red-700 animate-pulse shadow-[0_0_30px_rgba(220,53,69,0.8)]'
                      : 'bg-gradient-to-br from-[#CC0000] to-[#990000] hover:from-[#DD0000] hover:to-[#AA0000] hover:scale-105 shadow-[0_8px_24px_rgba(204,0,0,0.5)]'
                    }
                  `}
                  aria-pressed={isRecording}
                  aria-label={isRecording ? 'Stop recording' : 'Start recording'}
                >
                  {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </Button>
              </Glass>

              {/* Photo Icon Component */}
              <Glass className="w-full h-32 p-6 flex items-center justify-center relative">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/jpg,image/png,image/webp"
                  onChange={handleImageUpload}
                  className="hidden"
                  aria-label="Upload product image"
                />
                <Button
                  onClick={handleCameraClick}
                  disabled={isUploadingImage}
                  size="lg"
                  className={`
                    w-12 h-12 rounded-full text-2xl transition-all duration-300
                    ${isUploadingImage
                      ? 'bg-sky-400/50 cursor-wait'
                      : 'bg-gradient-to-br from-sky-400 to-cyan-500 hover:from-sky-500 hover:to-cyan-600 hover:scale-105 shadow-[0_8px_24px_rgba(56,189,248,0.4)]'
                    }
                  `}
                  aria-label="Upload product image"
                >
                  {isUploadingImage ? <Loader2 className="w-5 h-5 animate-spin" /> : <Camera className="w-5 h-5" />}
                </Button>
              </Glass>

              {/* Text Input Component */}
              <Glass className="w-full h-32 p-3 flex items-center justify-center">
                <Input
                  type="text"
                  placeholder="Type to search..."
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  onKeyDown={handleTextKeyDown}
                  className="bg-transparent border-0 focus-visible:ring-0 placeholder:text-muted-foreground/60 w-full h-full text-center"
                />
              </Glass>
            </div>
          </SidebarGroupContent>
        </SidebarGroup>

        {(statusDisplay || error || imageResult || imageError || (latency !== null && statusDisplay?.type === 'transcript')) && (
          <SidebarGroup>
            <SidebarGroupLabel>Status</SidebarGroupLabel>
            <SidebarGroupContent className="px-2">
              {statusDisplay && (
                <div className={`p-3 border rounded-md mb-2 ${
                  statusDisplay.type === 'transcript'
                    ? 'bg-green-500/10 border-green-500/40'
                    : 'bg-blue-500/10 border-blue-500/40'
                }`}>
                  <p className={`text-xs font-medium mb-1 ${
                    statusDisplay.type === 'transcript' ? 'text-green-600' : 'text-blue-600'
                  }`}>
                    {statusDisplay.type === 'transcript' ? 'Transcript:' : 'Search:'}
                  </p>
                  <p className={`text-sm ${
                    statusDisplay.type === 'transcript' ? 'text-green-800' : 'text-blue-800'
                  }`}>
                    {statusDisplay.value}
                  </p>
                </div>
              )}

              {imageResult && (
                <div className="p-3 border rounded-md mb-2 bg-sky-500/10 border-sky-500/40">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-medium text-sky-600">Image Analysis:</p>
                    <Badge
                      variant="secondary"
                      className={`text-xs ${
                        imageResult.confidence === 'high'
                          ? 'bg-green-100 text-green-700 border-green-300'
                          : imageResult.confidence === 'medium'
                          ? 'bg-yellow-100 text-yellow-700 border-yellow-300'
                          : 'bg-orange-100 text-orange-700 border-orange-300'
                      }`}
                    >
                      {imageResult.confidence === 'high' ? '⚫ High' : imageResult.confidence === 'medium' ? '🟡 Medium' : '🟠 Low'} Confidence
                    </Badge>
                  </div>
                  <div className="space-y-1">
                    {imageResult.brand && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-sky-700">Brand:</span>
                        <span className="text-sm text-sky-800">{imageResult.brand}</span>
                      </div>
                    )}
                    {imageResult.category && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-sky-700">Category:</span>
                        <span className="text-sm text-sky-800">{imageResult.category}</span>
                      </div>
                    )}
                    {!imageResult.brand && !imageResult.category && (
                      <p className="text-sm text-sky-700 italic">No brand or category detected</p>
                    )}
                  </div>
                </div>
              )}

              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md mb-2">
                  <p className="text-xs font-medium text-red-900 mb-1">Error:</p>
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              {imageError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md mb-2">
                  <p className="text-xs font-medium text-red-900 mb-1">Image Error:</p>
                  <p className="text-sm text-red-800">{imageError}</p>
                </div>
              )}

              {latency !== null && statusDisplay?.type === 'transcript' && (
                <div className="text-xs text-muted-foreground">
                  Latency: {Math.round(latency)}ms
                </div>
              )}
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border mt-auto">
        <div className="p-3">
          <a
            href="https://discord.gg/VTW3G4zq"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
          >
            <DiscordIcon className="w-4 h-4" />
            <div className="flex flex-col flex-1 min-w-0">
              <span className="text-xs font-medium">Join Discord Channel</span>
              <span className="text-xs text-sidebar-foreground/50">Feature Requests & Bugs</span>
            </div>
          </a>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
