import React, { useCallback, useEffect, useRef, useState } from "react";
import { Button, Tooltip } from "@fluentui/react-components";
import { Mic20Regular, MicOff20Regular } from "@fluentui/react-icons";
import "./VoiceControl.css";

interface VoiceControlProps {
    onTranscript: (text: string) => void; // Callback when transcript is complete
    responseText: string | null; // Text to synthesize
    isProcessing: boolean; // Is the system processing a request
}

const VoiceControl: React.FC<VoiceControlProps> = ({ onTranscript, responseText, isProcessing }) => {
    const [isListening, setIsListening] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [currentTranscript, setCurrentTranscript] = useState("");
    const [audioLevel, setAudioLevel] = useState(0);
    const [noAudioWarning, setNoAudioWarning] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const audioBufferQueue = useRef<AudioBuffer[]>([]);
    const isPlayingRef = useRef<boolean>(false);
    const streamRef = useRef<MediaStream | null>(null);
    const processorRef = useRef<ScriptProcessorNode | null>(null);
    const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
    const audioSetupCompleteRef = useRef<boolean>(false);

    // Function to play audio buffers sequentially - wrapped in useCallback to avoid recreating on every render
    const playNextBuffer = useCallback(() => {
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
    }, []);

    // Setup WebSocket connection
    useEffect(() => {
        const connectWebsocket = () => {
            const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
            const ws = new WebSocket(`${protocol}//${window.location.host}/voice`);

            ws.onopen = () => {
                console.log("[VoiceControl] Voice WebSocket connected");
                setIsConnected(true);
            };

            ws.onmessage = event => {
                const data = JSON.parse(event.data);

                if (data.type === "transcript_delta") {
                    // Handle incremental transcript
                    setCurrentTranscript(prev => prev + data.text);
                } else if (data.type === "transcript_complete") {
                    // Handle complete transcript
                    const finalTranscript = data.text || currentTranscript;
                    setCurrentTranscript("");

                    if (finalTranscript.trim()) {
                        onTranscript(finalTranscript);
                    }

                    // Always continuous, so keep listening
                    console.log("Continuing to listen in continuous mode (VAD server)");
                } else if (data.type === "tts_chunk") {
                    // Handle TTS audio chunk
                    if (!audioContextRef.current) {
                        // Type safe way to handle vendor prefixed API
                        const globalWindow = window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext };
                        const AudioContextClass = globalWindow.AudioContext || globalWindow.webkitAudioContext;
                        audioContextRef.current = new (AudioContextClass as typeof AudioContext)();
                    }

                    const base64Audio = data.audio;
                    const binaryAudio = atob(base64Audio);
                    const arrayBuffer = new ArrayBuffer(binaryAudio.length);
                    const bufferView = new Uint8Array(arrayBuffer);

                    for (let i = 0; i < binaryAudio.length; i++) {
                        bufferView[i] = binaryAudio.charCodeAt(i);
                    }

                    audioContextRef.current.decodeAudioData(arrayBuffer, buffer => {
                        audioBufferQueue.current.push(buffer);
                        if (!isPlayingRef.current) {
                            playNextBuffer();
                        }
                    });
                } else if (data.type === "tts_complete") {
                    // TTS stream complete
                    setIsSpeaking(false);
                }
            };

            ws.onerror = error => {
                console.error("[VoiceControl] WebSocket error:", error);
            };

            ws.onclose = () => {
                console.log("[VoiceControl] WebSocket connection closed");
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
            cleanupAudioResources();
        };
    }, [currentTranscript, onTranscript, playNextBuffer]);

    // Function to handle microphone button click
    const toggleListening = async () => {
        if (!isConnected) return;

        if (!isListening) {
            // Start listening
            setIsListening(true);
            setCurrentTranscript("");
            setNoAudioWarning(false);
            console.log("[VoiceControl] Requesting microphone access...");

            // Request microphone access
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                streamRef.current = stream;
                console.log("[VoiceControl] Microphone access granted.");

                // Type safe way to handle vendor prefixed API
                const globalWindow = window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext };
                const AudioContextClass = globalWindow.AudioContext || globalWindow.webkitAudioContext;
                const audioContext = new (AudioContextClass as typeof AudioContext)();
                audioContextRef.current = audioContext;
                console.log(`[VoiceControl] AudioContext created, sampleRate: ${audioContext.sampleRate}`);

                const source = audioContext.createMediaStreamSource(stream);
                sourceRef.current = source;

                const processor = audioContext.createScriptProcessor(1024, 1, 1);
                processorRef.current = processor;

                source.connect(processor);
                processor.connect(audioContext.destination);

                // Start STT session
                wsRef.current?.send(JSON.stringify({ type: "stt_start" }));
                console.log("[VoiceControl] Sent stt_start to backend.");

                let silentFrames = 0;
                processor.onaudioprocess = e => {
                    if (!isListening) {
                        // Clean up if we've stopped listening
                        stream.getTracks().forEach(track => track.stop());
                        source.disconnect();
                        processor.disconnect();
                        return;
                    }

                    // Get raw audio data
                    const inputData = e.inputBuffer.getChannelData(0);

                    // --- AUDIO LEVEL (RMS) ---
                    let sum = 0;
                    for (let i = 0; i < inputData.length; i++) {
                        sum += inputData[i] * inputData[i];
                    }
                    const rms = Math.sqrt(sum / inputData.length);
                    setAudioLevel(rms); // 0 (silent) to ~1 (loud)
                    if (rms < 0.01) {
                        silentFrames++;
                    } else {
                        silentFrames = 0;
                    }
                    if (silentFrames > 40) {
                        // ~2 seconds at 1024/24000
                        setNoAudioWarning(true);
                    } else {
                        setNoAudioWarning(false);
                    }
                    if (silentFrames % 10 === 0) {
                        console.log(`[VoiceControl] onaudioprocess RMS: ${rms.toFixed(4)}`);
                    }

                    // Convert to 16-bit PCM
                    const pcm16 = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        pcm16[i] = Math.min(1, Math.max(-1, inputData[i])) * 32767;
                    }

                    // Send to server
                    const binary = new Uint8Array(pcm16.buffer);
                    const base64 = btoa(String.fromCharCode.apply(null, [...binary]));

                    wsRef.current?.send(
                        JSON.stringify({
                            type: "audio_data",
                            audio: base64
                        })
                    );
                };
            } catch (err) {
                console.error("[VoiceControl] Error accessing microphone:", err);
                setIsListening(false);
            }
        } else {
            // Stop listening
            setIsListening(false);
            wsRef.current?.send(JSON.stringify({ type: "stt_stop" }));
            console.log("[VoiceControl] Sent stt_stop to backend.");

            // Cleanup audio resources
            cleanupAudioResources();
        }
    };

    const cleanupAudioResources = () => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }

        if (sourceRef.current) {
            sourceRef.current.disconnect();
            sourceRef.current = null;
        }

        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current = null;
        }

        audioSetupCompleteRef.current = false;
    };

    // Effect to handle Text-to-Speech when responseText changes
    useEffect(() => {
        if (responseText && wsRef.current && isConnected && !isSpeaking) {
            setIsSpeaking(true);

            // Request TTS for the response
            wsRef.current.send(
                JSON.stringify({
                    type: "tts_request",
                    text: responseText,
                    voice: "coral" // Can be customized
                })
            );
        }
    }, [responseText, isConnected, isSpeaking]);

    // --- UI: single circular mic button, left-aligned ---
    return (
        <div className="voice-mic-left">
            <Tooltip content={isListening ? "Stop listening" : "Start listening"} relationship="label">
                <Button
                    icon={isListening ? <MicOff20Regular /> : <Mic20Regular />}
                    shape="circular"
                    size="medium"
                    appearance={isListening ? "primary" : "secondary"}
                    disabled={!isConnected || isProcessing}
                    onClick={toggleListening}
                    aria-label={isListening ? "Stop listening" : "Start listening"}
                />
            </Tooltip>
            <div className="audio-bar-container" aria-label={`Audio level: ${(audioLevel * 100).toFixed(0)}%`}>
                <div
                    className="audio-bar-fill"
                    style={{
                        width: isListening ? `${Math.min(1, audioLevel) * 100}%` : "100%",
                        background: isListening ? (audioLevel > 0.6 ? "#f44336" : audioLevel > 0.3 ? "#ff9800" : "#4caf50") : "#bbb"
                    }}
                />
            </div>
            {noAudioWarning && isListening && <div className="audio-warning">No audio detected. Is your mic muted?</div>}
        </div>
    );
};

export default VoiceControl;
