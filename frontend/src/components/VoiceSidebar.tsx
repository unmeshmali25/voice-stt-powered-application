import { useEffect, useState, useRef } from 'react'
import { Mic, MicOff, Camera } from 'lucide-react'
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
import { useVoiceRecording } from '../hooks/useVoiceRecording'

interface VoiceSidebarProps {
  onTranscriptChange?: (transcript: string) => void
}

export function VoiceSidebar({ onTranscriptChange }: VoiceSidebarProps) {
  const { isRecording, transcript, error, latency, startRecording, stopRecording } = useVoiceRecording()
  const [textInput, setTextInput] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (transcript && onTranscriptChange) {
      onTranscriptChange(transcript)
    }
  }, [transcript, onTranscriptChange])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.code === 'Space' && !event.repeat) {
        event.preventDefault()
        if (isRecording) {
          stopRecording()
        } else {
          startRecording()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isRecording, startRecording, stopRecording])

  const handleMicClick = () => {
    if (isRecording) {
      stopRecording()
    } else {
      startRecording()
    }
  }

  const handlePhotoClick = () => {
    fileInputRef.current?.click()
  }

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      // TODO: Implement photo upload/processing logic
      console.log('Photo selected:', file.name)
    }
  }

  const handleTextKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && textInput.trim() && onTranscriptChange) {
      onTranscriptChange(textInput.trim())
    }
  }

  return (
    <Sidebar collapsible="none">
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
              <Glass className="w-full h-32 p-6 flex items-center justify-center">
                <Button
                  onClick={handlePhotoClick}
                  size="lg"
                  className="w-12 h-12 rounded-full text-2xl transition-all duration-300 bg-gradient-to-br from-sky-400 to-cyan-500 hover:from-sky-500 hover:to-cyan-600 hover:scale-105 shadow-[0_8px_24px_rgba(56,189,248,0.5)] hover:shadow-[0_12px_32px_rgba(56,189,248,0.7)]"
                  aria-label="Upload photo"
                >
                  <Camera className="w-5 h-5" />
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoChange}
                  className="hidden"
                  aria-label="Upload photo"
                />
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

        {(transcript || error || latency !== null) && (
          <SidebarGroup>
            <SidebarGroupLabel>Status</SidebarGroupLabel>
            <SidebarGroupContent className="px-2">
              {transcript && (
                <div className="p-3 bg-[#CC0000]/5 border border-[#CC0000]/30 rounded-md mb-2">
                  <p className="text-xs font-medium text-[#CC0000] mb-1">Transcript:</p>
                  <p className="text-sm text-gray-800">{transcript}</p>
                </div>
              )}

              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md mb-2">
                  <p className="text-xs font-medium text-red-900 mb-1">Error:</p>
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              {latency !== null && (
                <div className="text-xs text-muted-foreground">
                  Latency: {Math.round(latency)}ms
                </div>
              )}
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
      </SidebarFooter>
    </Sidebar>
  )
}
