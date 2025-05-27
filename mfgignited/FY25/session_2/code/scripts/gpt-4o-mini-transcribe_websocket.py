# Reference: https://techcommunity.microsoft.com/blog/azure-ai-services-blog/real-time-speech-transcription-with-gpt-4o-transcribe-and-gpt-4o-mini-transcribe/4410353

import os
import json
import base64
import threading
import pyaudio
import websocket
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_STT_TTS_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY is missing!")

# WebSocket endpoint for OpenAI Realtime API (transcription model)
url = f"{os.environ.get("AZURE_OPENAI_STT_TTS_ENDPOINT").replace("https", "wss")}/openai/realtime?api-version=2025-04-01-preview&intent=transcription"
headers = {"api-key": OPENAI_API_KEY}
# Audio stream parameters (16-bit PCM, 16kHz mono)
RATE = 24000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1024

audio_interface = pyaudio.PyAudio()
stream = audio_interface.open(
    format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
)


def on_open(ws):
    print("Connected! Start speaking...")
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
        },
    }
    ws.send(json.dumps(session_config))

    def stream_microphone():
        try:
            while ws.keep_running:
                audio_data = stream.read(CHUNK, exception_on_overflow=False)
                audio_base64 = base64.b64encode(audio_data).decode("utf-8")
                ws.send(
                    json.dumps(
                        {"type": "input_audio_buffer.append", "audio": audio_base64}
                    )
                )
        except Exception as e:
            print("Audio streaming error:", e)
            ws.close()

    threading.Thread(target=stream_microphone, daemon=True).start()


def on_message(ws, message):
    try:
        data = json.loads(message)
        event_type = data.get("type", "")
        # print("Event type:", event_type)
        # print(data)
        # Stream live incremental transcripts
        if event_type == "conversation.item.input_audio_transcription.delta":
            transcript_piece = data.get("delta", "")
            if transcript_piece:
                print(transcript_piece, end=" ", flush=True)
        if event_type == "conversation.item.input_audio_transcription.completed":
            print(data["transcript"])
        if event_type == "item":
            transcript = data.get("item", "")
            if transcript:
                print("\nFinal transcript:", transcript)

    except Exception:
        pass  # Ignore unrelated events


def on_error(ws, error):
    print("WebSocket error:", error)


def on_close(ws, close_status_code, close_msg):
    print("Disconnected from server.")
    stream.stop_stream()
    stream.close()
    audio_interface.terminate()


print("Connecting to OpenAI Realtime API...")
ws_app = websocket.WebSocketApp(
    url,
    header=headers,
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close,
)

ws_app.run_forever()
