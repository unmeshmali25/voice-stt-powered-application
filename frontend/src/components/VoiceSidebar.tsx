import { useEffect, useState, useRef } from 'react'
import { Mic, MicOff, Camera, Loader2, Video, Search, Sparkles } from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from './ui/sidebar'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Badge } from './ui/badge'
import { useVoiceRecording } from '../hooks/useVoiceRecording'
import { ImageExtractionResult } from '../types/coupon'
import { apiFetch } from '../lib/api'
import { cn } from '../lib/utils'

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
  onARModeToggle?: () => void
}

export function VoiceSidebar({ onTranscriptChange, onARModeToggle }: VoiceSidebarProps) {
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
      setImageResult(null)
      setImageError(null)
      startRecording()
    }
  }

  const handleTextKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && textInput.trim()) {
      const searchValue = textInput.trim()
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
    fileInputRef.current?.click()
  }

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    if (!allowedTypes.includes(file.type)) {
      setImageError('Please upload a JPEG, PNG, or WebP image')
      return
    }

    const maxSizeMB = 5
    if (file.size > maxSizeMB * 1024 * 1024) {
      setImageError(`Image too large. Maximum size is ${maxSizeMB}MB`)
      return
    }

    setIsUploadingImage(true)
    setImageError(null)
    setImageResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

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

      if (result.searchQuery && onTranscriptChange) {
        onTranscriptChange(result.searchQuery)
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to process image'
      setImageError(errorMessage)
      console.error('Image upload error:', err)
    } finally {
      setIsUploadingImage(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  return (
    <Sidebar collapsible="none" className="h-screen border-r border-sidebar-border/50 bg-sidebar/95 backdrop-blur supports-[backdrop-filter]:bg-sidebar/60">
      <SidebarHeader className="pt-6 pb-2 px-4 border-none">
         <div className="flex flex-col gap-1 px-1">
            <h2 className="text-sm font-semibold tracking-tight text-sidebar-foreground uppercase flex items-center gap-2">
              <Sparkles className="w-3 h-3 text-primary" />
              Assistant
            </h2>
            <p className="text-xs text-muted-foreground">
              Multi-modal search
            </p>
         </div>
      </SidebarHeader>

      <SidebarContent className="px-4 gap-6">
        {/* Search Input - Spotlight Style */}
        <div className="relative group mt-2">
          <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-muted-foreground/70 group-focus-within:text-primary transition-colors" />
          </div>
          <Input
            type="text"
            placeholder="Ask anything..."
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={handleTextKeyDown}
            className="pl-9 h-10 bg-sidebar-accent/50 border-transparent hover:bg-sidebar-accent/80 focus-visible:bg-background focus-visible:ring-1 focus-visible:ring-primary/20 transition-all shadow-sm rounded-xl"
          />
        </div>

        {/* Primary Actions */}
        <div className="flex flex-col gap-4">
           {/* Mic Button - Hero */}
           <div className="flex justify-center py-4">
              <Button
                onClick={handleMicClick}
                variant="ghost"
                className={cn(
                  "w-24 h-24 rounded-full transition-all duration-500 flex items-center justify-center relative",
                  isRecording
                    ? "bg-red-500/10 text-red-600 shadow-[0_0_40px_-10px_rgba(220,38,38,0.4)] scale-110"
                    : "bg-gradient-to-b from-sidebar-accent to-sidebar-accent/50 hover:from-sidebar-accent hover:to-sidebar-accent text-sidebar-foreground shadow-sm hover:scale-105 hover:shadow-md border border-sidebar-border/50"
                )}
                aria-label={isRecording ? 'Stop recording' : 'Start recording'}
              >
                 {isRecording && (
                    <>
                      <span className="absolute inset-0 rounded-full border border-red-500/30 animate-[ping_2s_ease-in-out_infinite]" />
                      <span className="absolute inset-0 rounded-full border border-red-500/20 animate-[ping_2s_ease-in-out_infinite_0.5s]" />
                    </>
                 )}
                 {isRecording ? (
                   <MicOff className="w-8 h-8 relative z-10" />
                 ) : (
                   <Mic className="w-8 h-8 relative z-10" />
                 )}
              </Button>
           </div>

           <div className="grid grid-cols-2 gap-3">
              <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/jpg,image/png,image/webp"
                  onChange={handleImageUpload}
                  className="hidden"
               />
              <Button
                 onClick={handleCameraClick}
                 disabled={isUploadingImage}
                 variant="outline"
                 className="h-20 flex flex-col gap-2 rounded-2xl border-sidebar-border/50 bg-sidebar-accent/30 hover:bg-sidebar-accent/60 transition-all group relative overflow-hidden hover:border-sidebar-border"
              >
                 <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                 {isUploadingImage ? (
                    <Loader2 className="w-5 h-5 animate-spin text-primary" />
                 ) : (
                    <Camera className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                 )}
                 <span className="text-xs font-medium text-muted-foreground group-hover:text-foreground transition-colors">
                    Photo
                 </span>
              </Button>

              <Button
                 onClick={onARModeToggle}
                 variant="outline"
                 className="h-20 flex flex-col gap-2 rounded-2xl border-sidebar-border/50 bg-sidebar-accent/30 hover:bg-sidebar-accent/60 transition-all group relative overflow-hidden hover:border-sidebar-border"
              >
                 <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-pink-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                 <Video className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                 <span className="text-xs font-medium text-muted-foreground group-hover:text-foreground transition-colors">
                    Live AR
                 </span>
              </Button>
           </div>
        </div>

        {/* Status Section - Unified Glass Panel */}
        {(statusDisplay || error || imageResult || imageError || (latency !== null && statusDisplay?.type === 'transcript')) && (
          <div className="rounded-2xl border border-sidebar-border/50 bg-sidebar-accent/30 backdrop-blur-sm p-4 space-y-3 shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-300">
              {statusDisplay && (
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <div className={cn("w-1.5 h-1.5 rounded-full", statusDisplay.type === 'transcript' ? "bg-green-500" : "bg-blue-500")} />
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      {statusDisplay.type === 'transcript' ? 'Listening' : 'Searching'}
                    </span>
                  </div>
                  <p className="text-sm text-foreground leading-relaxed">
                    {statusDisplay.value}
                  </p>
                </div>
              )}

              {imageResult && (
                <div className="space-y-2 pt-2 border-t border-sidebar-border/50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">Analyzed Image</span>
                    <Badge variant={imageResult.confidence === 'high' ? 'default' : 'secondary'} className="text-[10px] h-5">
                      {imageResult.confidence} confidence
                    </Badge>
                  </div>
                  {imageResult.brand && (
                    <div className="text-sm">
                      <span className="text-muted-foreground">Brand: </span>
                      <span className="font-medium">{imageResult.brand}</span>
                    </div>
                  )}
                  {imageResult.category && (
                    <div className="text-sm">
                       <span className="text-muted-foreground">Category: </span>
                       <span className="font-medium">{imageResult.category}</span>
                    </div>
                  )}
                </div>
              )}

              {error && (
                <div className="pt-2 border-t border-red-200/20">
                  <p className="text-xs text-red-500 font-medium">{error}</p>
                </div>
              )}

              {imageError && (
                <div className="pt-2 border-t border-red-200/20">
                   <p className="text-xs text-red-500 font-medium">{imageError}</p>
                </div>
              )}

              {latency !== null && statusDisplay?.type === 'transcript' && (
                <div className="pt-1 flex justify-end">
                  <span className="text-[10px] text-muted-foreground font-mono opacity-50">
                    {Math.round(latency)}ms
                  </span>
                </div>
              )}
          </div>
        )}

      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border/50 p-4">
        <a
            href="https://discord.gg/VTW3G4zq"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/50 transition-all group"
          >
            <div className="p-1.5 rounded-md bg-sidebar-accent group-hover:bg-background transition-colors">
               <DiscordIcon className="w-4 h-4" />
            </div>
            <div className="flex flex-col flex-1 min-w-0">
              <span className="text-xs font-medium">Join Community</span>
              <span className="text-[10px] text-muted-foreground/70">Feature Requests</span>
            </div>
        </a>
      </SidebarFooter>
    </Sidebar>
  )
}
