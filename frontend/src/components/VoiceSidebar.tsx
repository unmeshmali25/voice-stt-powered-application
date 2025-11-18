import { useEffect, useState } from 'react'
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
import { Badge } from './ui/badge'
import { useVoiceRecording } from '../hooks/useVoiceRecording'

interface VoiceSidebarProps {
  onTranscriptChange?: (transcript: string) => void
}

export function VoiceSidebar({ onTranscriptChange }: VoiceSidebarProps) {
  const { isRecording, transcript, error, latency, startRecording, stopRecording } = useVoiceRecording()
  const [textInput, setTextInput] = useState('')
  const [statusDisplay, setStatusDisplay] = useState<{ type: 'transcript' | 'search', value: string } | null>(null)

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
      startRecording()
    }
  }


  const handleTextKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && textInput.trim()) {
      const searchValue = textInput.trim()
      setStatusDisplay({ type: 'search', value: searchValue })
      if (onTranscriptChange) {
        onTranscriptChange(searchValue)
      }
      setTextInput('')
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
              <Glass className="w-full h-32 p-6 flex items-center justify-center relative">
                <Button
                  disabled
                  size="lg"
                  className="w-12 h-12 rounded-full text-2xl transition-all duration-300 bg-gradient-to-br from-sky-400/50 to-cyan-500/50 cursor-not-allowed opacity-60"
                  aria-label="Upload photo - Coming Soon"
                >
                  <Camera className="w-5 h-5" />
                </Button>
                <Badge
                  variant="secondary"
                  className="absolute top-2 right-2 text-xs bg-sky-100 text-sky-700 border-sky-300"
                >
                  Coming Soon
                </Badge>
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

        {(statusDisplay || error || (latency !== null && statusDisplay?.type === 'transcript')) && (
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

              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md mb-2">
                  <p className="text-xs font-medium text-red-900 mb-1">Error:</p>
                  <p className="text-sm text-red-800">{error}</p>
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

      <SidebarFooter className="border-t border-sidebar-border">
      </SidebarFooter>
    </Sidebar>
  )
}
