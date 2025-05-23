# Voice Integration Plan for Field Service Assistant

## Overview

This document outlines the plan for integrating voice capabilities into the Field Service Assistant application, enabling hands-free operation for technicians in the field.

## Requirements

- Speech-to-Text (STT): Convert spoken user input to text
- Text-to-Speech (TTS): Convert assistant responses to spoken audio
- Hands-free operation
- Secure handling of Azure API credentials
- Responsive user experience

## Architecture Decision

We've chosen a **backend-driven approach with WebSocket streaming** for the following reasons:

1. **Security**: Keeps Azure API keys secure on the server
2. **Consistency**: Provides uniform experience across browsers/devices
3. **Advanced features**: Leverages full capabilities of Azure AI services
4. **Existing pattern**: Aligns with current streaming architecture

### Architecture Diagram

``` text
User (Browser) <--WebSocket--> Backend <--API--> Azure AI Services
   ↑                              ↑
Microphone                      Azure
& Speakers                    Credentials
```

## Implementation Components

### 1. Backend Voice Service (Python)

Create a new `voice_service.py` file in the backend that will handle:

- WebSocket connections from the frontend
- STT streaming using Azure's gpt-4o-mini-transcribe
- TTS streaming using Azure's gpt-4o-mini-tts
- Bidirectional audio/transcript streaming

### 2. Frontend Voice Component (React/TypeScript)

Create a new `VoiceControl.tsx` component that will:

- Manage WebSocket connection to the backend
- Handle microphone access and audio streaming
- Process incoming transcripts and audio responses
- Provide UI for enabling/disabling voice features

### 3. UI Integration Points

- **SearchInput**: Add voice control for query input
- **ChatContent**: Add TTS for assistant responses

## Implementation Plan

### Phase 1: Backend Voice Service

1. Create `voice_service.py` in the backend directory
2. Implement WebSocket endpoint for voice connections
3. Add STT streaming functionality using existing script as reference
4. Add TTS streaming functionality using existing script as reference
5. Test with simple client

### Phase 2: Frontend Voice Component

1. Create `VoiceControl.tsx` component
2. Implement WebSocket connection management
3. Add microphone access and audio streaming
4. Add audio playback for TTS responses
5. Create simple UI with microphone and speaker controls

### Phase 3: UI Integration

1. Integrate VoiceControl with SearchInput for query input
2. Integrate VoiceControl with ChatContent for response playback
3. Add CSS styling for voice controls
4. Add visual feedback for listening/speaking states

### Phase 4: Testing and Refinement

1. Test in various browsers and devices
2. Optimize audio processing for field conditions
3. Add error handling and reconnection logic
4. Improve accessibility features

## Code Implementation Details

### Backend Voice Service (Python)

```python
import os
import json
import base64
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import websockets

class VoiceService:
    def __init__(self, app):
        self.app = app
        self.active_connections = {}
        
        @app.websocket("/voice")
        async def voice_endpoint(websocket: WebSocket):
            await self._handle_voice_connection(websocket)
    
    async def _handle_voice_connection(self, websocket: WebSocket):
        # Accept the WebSocket connection
        await websocket.accept()
        connection_id = id(websocket)
        self.active_connections[connection_id] = websocket
        
        try:
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "stt_start":
                    # Start STT session
                    await self._handle_stt(websocket, data)
                elif message_type == "tts_request":
                    # Handle TTS request
                    await self._handle_tts(websocket, data)
                
        except WebSocketDisconnect:
            # Clean up the connection
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
    
    async def _handle_stt(self, websocket, data):
        # Connect to Azure STT service using websockets
        azure_ws_url = f"{os.environ.get('AZURE_OPENAI_STT_TTS_ENDPOINT').replace('https', 'wss')}/openai/realtime?api-version=2025-04-01-preview&intent=transcription"
        headers = {"api-key": os.environ.get("AZURE_OPENAI_STT_TTS_KEY")}
        
        async with websockets.connect(azure_ws_url, extra_headers=headers) as azure_ws:
            # Send initial configuration
            session_config = {
                "type": "transcription_session.update",
                "session": {
                    "input_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        "prompt": "Respond in English.",
                    },
                    "input_audio_noise_reduction": {"type": "near_field"},
                    "turn_detection": {"type": "server_vad"},
                }
            }
            await azure_ws.send(json.dumps(session_config))
            
            # Start two-way communication
            # Forward audio from client to Azure
            audio_task = asyncio.create_task(self._forward_audio(websocket, azure_ws))
            # Forward transcription from Azure to client
            transcription_task = asyncio.create_task(self._forward_transcription(azure_ws, websocket))
            
            # Wait for either task to complete
            await asyncio.gather(audio_task, transcription_task)
    
    async def _forward_audio(self, client_ws, azure_ws):
        try:
            while True:
                message = await client_ws.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "audio_data":
                    # Forward audio data to Azure
                    await azure_ws.send(json.dumps({
                        "type": "input_audio_buffer.append", 
                        "audio": data.get("audio")
                    }))
                elif data.get("type") == "stt_stop":
                    break
        except Exception as e:
            print(f"Error in audio forwarding: {e}")
    
    async def _forward_transcription(self, azure_ws, client_ws):
        try:
            while True:
                message = await azure_ws.recv()
                data = json.loads(message)
                event_type = data.get("type", "")
                
                if event_type == "conversation.item.input_audio_transcription.delta":
                    # Forward incremental transcript
                    await client_ws.send_text(json.dumps({
                        "type": "transcript_delta",
                        "text": data.get("delta", "")
                    }))
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    # Forward completed transcript
                    await client_ws.send_text(json.dumps({
                        "type": "transcript_complete",
                        "text": data.get("transcript", "")
                    }))
                    break
        except Exception as e:
            print(f"Error in transcription forwarding: {e}")
    
    async def _handle_tts(self, websocket, data):
        from openai import AsyncAzureOpenAI
        
        client = AsyncAzureOpenAI(
            azure_endpoint=os.environ.get("AZURE_OPENAI_STT_TTS_ENDPOINT"),
            api_key=os.environ.get("AZURE_OPENAI_STT_TTS_KEY"),
            api_version="2025-03-01-preview",
        )
        
        text = data.get("text", "")
        voice = data.get("voice", "coral")
        
        try:
            async with client.audio.speech.with_streaming_response.create(
                model="gpt-4o-mini-tts",
                voice=voice,
                input=text,
                response_format="pcm"
            ) as response:
                # Stream audio chunks back to client
                async for chunk in response.iter_bytes():
                    base64_chunk = base64.b64encode(chunk).decode('utf-8')
                    await websocket.send_text(json.dumps({
                        "type": "tts_chunk",
                        "audio": base64_chunk
                    }))
                
                # Signal end of stream
                await websocket.send_text(json.dumps({
                    "type": "tts_complete"
                }))
                
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "tts_error",
                "error": str(e)
            }))
```

### Frontend Voice Component (TypeScript/React)

```tsx
import React, { useEffect, useRef, useState } from 'react';
import { Button, Tooltip } from "@fluentui/react-components";
import { Mic20Regular, MicOff20Regular, Speaker20Regular, SpeakerMute20Regular } from "@fluentui/react-icons";
import './VoiceControl.css';

interface VoiceControlProps {
  onTranscript: (text: string) => void;  // Callback when transcript is complete
  responseText: string | null;           // Text to synthesize
  isProcessing: boolean;                // Is the system processing a request
}

const VoiceControl: React.FC<VoiceControlProps> = ({ 
  onTranscript, 
  responseText,
  isProcessing 
}) => {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [currentTranscript, setCurrentTranscript] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioBufferQueue = useRef<AudioBuffer[]>([]);
  const isPlayingRef = useRef<boolean>(false);

  // Setup WebSocket connection
  useEffect(() => {
    const connectWebsocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}/voice`);
      
      ws.onopen = () => {
        console.log('Voice WebSocket connected');
        setIsConnected(true);
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'transcript_delta') {
          // Handle incremental transcript
          setCurrentTranscript(prev => prev + data.text);
        } 
        else if (data.type === 'transcript_complete') {
          // Handle complete transcript
          const finalTranscript = data.text || currentTranscript;
          setCurrentTranscript('');
          onTranscript(finalTranscript);
          setIsListening(false);
        }
        else if (data.type === 'tts_chunk') {
          // Handle TTS audio chunk
          if (!audioContextRef.current) {
            audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
          }
          
          const base64Audio = data.audio;
          const binaryAudio = atob(base64Audio);
          const arrayBuffer = new ArrayBuffer(binaryAudio.length);
          const bufferView = new Uint8Array(arrayBuffer);
          
          for (let i = 0; i < binaryAudio.length; i++) {
            bufferView[i] = binaryAudio.charCodeAt(i);
          }
          
          audioContextRef.current.decodeAudioData(arrayBuffer, (buffer) => {
            audioBufferQueue.current.push(buffer);
            if (!isPlayingRef.current) {
              playNextBuffer();
            }
          });
        }
        else if (data.type === 'tts_complete') {
          // TTS stream complete
          setIsSpeaking(false);
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
      
      ws.onclose = () => {
        console.log('WebSocket connection closed');
        setIsConnected(false);
        // Try to reconnect in 3 seconds
        setTimeout(connectWebsocket, 3000);
      };
      
      wsRef.current = ws;
    };
    
    connectWebsocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);
  
  // Function to play audio buffers sequentially
  const playNextBuffer = () => {
    if (audioBufferQueue.current.length === 0) {
      isPlayingRef.current = false;
      return;
    }
    
    isPlayingRef.current = true;
    const audioContext = audioContextRef.current!;
    const source = audioContext.createBufferSource();
    source.buffer = audioBufferQueue.current.shift()!;
    source.connect(audioContext.destination);
    source.onended = playNextBuffer;
    source.start();
  };
  
  // Function to handle microphone button click
  const toggleListening = async () => {
    if (!isConnected) return;
    
    if (!isListening) {
      // Start listening
      setIsListening(true);
      setCurrentTranscript('');
      
      // Request microphone access
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(stream);
        const processor = audioContext.createScriptProcessor(1024, 1, 1);
        
        source.connect(processor);
        processor.connect(audioContext.destination);
        
        // Start STT session
        wsRef.current?.send(JSON.stringify({ type: 'stt_start' }));
        
        processor.onaudioprocess = (e) => {
          if (!isListening) {
            // Clean up if we've stopped listening
            stream.getTracks().forEach(track => track.stop());
            source.disconnect();
            processor.disconnect();
            return;
          }
          
          // Get raw audio data
          const inputData = e.inputBuffer.getChannelData(0);
          
          // Convert to 16-bit PCM
          const pcm16 = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            pcm16[i] = Math.min(1, Math.max(-1, inputData[i])) * 32767;
          }
          
          // Send to server
          const binary = new Uint8Array(pcm16.buffer);
          const base64 = btoa(String.fromCharCode(...binary));
          
          wsRef.current?.send(JSON.stringify({
            type: 'audio_data',
            audio: base64
          }));
        };
        
      } catch (err) {
        console.error('Error accessing microphone:', err);
        setIsListening(false);
      }
    } else {
      // Stop listening
      setIsListening(false);
      wsRef.current?.send(JSON.stringify({ type: 'stt_stop' }));
    }
  };
  
  // Effect to handle Text-to-Speech when responseText changes
  useEffect(() => {
    if (responseText && wsRef.current && isConnected && !isSpeaking) {
      setIsSpeaking(true);
      
      // Request TTS for the response
      wsRef.current.send(JSON.stringify({
        type: 'tts_request',
        text: responseText,
        voice: 'coral' // Can be customized
      }));
    }
  }, [responseText, isConnected]);

  return (
    <div className="voice-control-container">
      <div className="voice-buttons">
        <Tooltip content={isListening ? "Stop listening" : "Start listening"} relationship="label">
          <Button 
            icon={isListening ? <MicOff20Regular /> : <Mic20Regular />}
            appearance={isListening ? "primary" : "secondary"}
            disabled={!isConnected || isProcessing}
            onClick={toggleListening}
            aria-label={isListening ? "Stop listening" : "Start listening"}
          />
        </Tooltip>
        
        <Tooltip content={isSpeaking ? "Speaking..." : "Text to Speech"} relationship="label">
          <Button 
            icon={isSpeaking ? <Speaker20Regular /> : <SpeakerMute20Regular />}
            appearance={isSpeaking ? "primary" : "secondary"}
            disabled={isSpeaking}
            aria-label={isSpeaking ? "Speaking" : "Text to Speech"}
          />
        </Tooltip>
      </div>
      
      {isListening && (
        <div className="transcript-preview">
          {currentTranscript || "Listening..."}
        </div>
      )}
    </div>
  );
};

export default VoiceControl;
```

### CSS for Voice Control

```css
.voice-control-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 8px 0;
}

.voice-buttons {
  display: flex;
  gap: 8px;
}

.transcript-preview {
  margin-top: 8px;
  padding: 8px;
  border-radius: 4px;
  background-color: rgba(0, 0, 0, 0.05);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-style: italic;
  color: #666;
}
```

## Integration Guide

### 1. Backend Setup

1. Install required dependencies:

   ```bash
   pip install websockets python-multipart
   ```

2. Initialize the VoiceService in app.py:

   ```python
   from voice_service import VoiceService
   
   # Initialize FastAPI app
   app = FastAPI()
   
   # Initialize voice service
   voice_service = VoiceService(app)
   ```

### 2. Frontend Integration

1. Install Audio Web API types:

   ```bash
   npm install --save-dev @types/dom-mediacapture-record
   ```

2. Add VoiceControl to SearchInput:

   ```tsx
   import VoiceControl from './VoiceControl';
   
   // In your SearchInput component
   const handleTranscript = (text: string) => {
       setQuery(text);
       if (text.trim()) {
           onSearch(text.trim());
       }
   };
   
   return (
       <div className="search-container">
           {/* Existing search input */}
           <Textarea value={query} onChange={...} />
           
           <VoiceControl 
               onTranscript={handleTranscript}
               responseText={null}
               isProcessing={isLoading}
           />
           
           {/* Existing buttons */}
       </div>
   );
   ```

3. Add VoiceControl to ChatContent:

   ```tsx
   const [latestResponse, setLatestResponse] = useState<string | null>(null);
   
   useEffect(() => {
       const lastMessage = thread.filter(msg => msg.type === ThreadType.Answer)
           .sort((a, b) => new Date(b.request_id).getTime() - new Date(a.request_id).getTime())[0];
           
       if (lastMessage?.answerPartial?.answer) {
           setLatestResponse(lastMessage.answerPartial.answer);
       }
   }, [thread]);
   
   // Add to your JSX
   <VoiceControl 
       onTranscript={() => {}} 
       responseText={latestResponse}
       isProcessing={false}
   />
   ```

## Potential Challenges and Solutions

### Challenge: Audio Quality in Field Conditions

- **Solution**: Add noise reduction and filtering options in the backend
- **Solution**: Provide audio level indicators and feedback to users

### Challenge: Poor Network Connectivity

- **Solution**: Implement local buffering and reconnection logic
- **Solution**: Add fallback to text input when voice is unavailable

### Challenge: Browser Compatibility

- **Solution**: Test with major browsers and add polyfills as needed
- **Solution**: Implement feature detection and graceful degradation

### Challenge: Security Concerns

- **Solution**: Use secure WebSocket connections (wss://)
- **Solution**: Implement proper authentication for voice endpoints
- **Solution**: Keep all credentials on the server side

## Future Enhancements

1. Voice commands for navigation and actions
2. Voice profile customization for different environments
3. Offline voice recognition for basic commands
4. Voice activity detection to automatically start listening
5. Custom TTS voices for different types of content

## Conclusion

This voice integration plan provides a comprehensive approach to adding hands-free capabilities to the Field Service Assistant application. By using a backend-driven approach with WebSocket streaming, we can provide a secure, responsive, and feature-rich voice experience for field technicians.

The implementation leverages existing Azure services and follows the same architectural patterns already in use in the application, ensuring consistency and maintainability.
