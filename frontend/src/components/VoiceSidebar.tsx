import { useEffect } from 'react'
import { Mic, MicOff } from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
} from './ui/sidebar'
import { Button } from './ui/button'
import { useVoiceRecording } from '../hooks/useVoiceRecording'

interface VoiceSidebarProps {
  onTranscriptChange?: (transcript: string) => void
}

export function VoiceSidebar({ onTranscriptChange }: VoiceSidebarProps) {
  const { isRecording, transcript, error, latency, startRecording, stopRecording } = useVoiceRecording()

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

  return (
    <Sidebar collapsible="none">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-3">
          <div className="w-2.5 h-2.5 rounded-full bg-[#CC0000] shadow-[0_0_10px_rgba(204,0,0,0.6)]"></div>
          <h2 className="font-semibold text-sm">Voice Controls</h2>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Microphone</SidebarGroupLabel>
          <SidebarGroupContent>
            <div className="flex flex-col items-center gap-4 py-6">
              <Button
                onClick={handleMicClick}
                size="lg"
                className={`
                  w-20 h-20 rounded-full text-3xl transition-all duration-300
                  ${isRecording
                    ? 'bg-red-600 hover:bg-red-700 animate-pulse shadow-[0_0_30px_rgba(220,53,69,0.8)]'
                    : 'bg-gradient-to-br from-[#CC0000] to-[#990000] hover:from-[#DD0000] hover:to-[#AA0000] hover:scale-105 shadow-[0_8px_24px_rgba(204,0,0,0.5)]'
                  }
                `}
                aria-pressed={isRecording}
                aria-label={isRecording ? 'Stop recording' : 'Start recording'}
              >
                {isRecording ? <MicOff className="w-8 h-8" /> : <Mic className="w-8 h-8" />}
              </Button>

              <div className="text-center px-4">
                <p className="text-xs text-muted-foreground">
                  {isRecording ? 'Recording... Click or press SPACE to stop' : 'Click or press SPACE to start'}
                </p>
              </div>
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
        <div className="px-4 py-3">
          <p className="text-xs text-muted-foreground text-center">
            UM Retail Voice Offers
          </p>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
