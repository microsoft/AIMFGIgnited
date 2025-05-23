import os
import json
import base64
import asyncio
import logging
import threading
import queue
from aiohttp import web, WSMsgType
import websocket  # Using websocket-client library instead of websockets


class VoiceService:
    def __init__(self, app):
        self.app = app
        self.active_connections = {}

        # Store environment variables as instance attributes
        self.stt_tts_endpoint = os.environ.get("AZURE_OPENAI_STT_TTS_ENDPOINT")
        self.stt_tts_key = os.environ.get("AZURE_OPENAI_STT_TTS_KEY")

        # Check if required environment variables are present
        if not self.stt_tts_endpoint or not self.stt_tts_key:
            logging.warning(
                "Voice service disabled: Missing AZURE_OPENAI_STT_TTS_ENDPOINT or AZURE_OPENAI_STT_TTS_KEY"
            )
            print(
                "Voice service disabled: Missing AZURE_OPENAI_STT_TTS_ENDPOINT or AZURE_OPENAI_STT_TTS_KEY"
            )
        else:
            # Register the WebSocket route using aiohttp pattern
            app.router.add_route("GET", "/voice", self.voice_endpoint)
            print(f"Voice service enabled with endpoint: {self.stt_tts_endpoint}")

    async def voice_endpoint(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        connection_id = id(ws)
        self.active_connections[connection_id] = ws

        # Message queues for communication between threads
        azure_to_client_queue = queue.Queue()
        client_to_azure_queue = queue.Queue()
        stop_event = threading.Event()

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    message_type = data.get("type")

                    if message_type == "stt_start":
                        # Start STT in a separate thread
                        threading.Thread(
                            target=self._handle_stt_thread,
                            args=(
                                azure_to_client_queue,
                                client_to_azure_queue,
                                stop_event,
                            ),
                            daemon=True,
                        ).start()

                        # Start a background task to forward messages from Azure to client
                        asyncio.create_task(
                            self._forward_azure_to_client(
                                ws, azure_to_client_queue, stop_event
                            )
                        )

                    elif message_type == "audio_data":
                        # Put audio data in the queue for the Azure thread
                        client_to_azure_queue.put(data)

                    elif message_type == "stt_stop":
                        stop_event.set()

                    elif message_type == "tts_request":
                        await self._handle_tts(ws, data)

                elif msg.type == WSMsgType.ERROR:
                    print(
                        f"WebSocket connection closed with exception {ws.exception()}"
                    )
                    stop_event.set()

        finally:
            stop_event.set()
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
            print(f"WebSocket connection {connection_id} closed")

        return ws

    def _handle_stt_thread(
        self, azure_to_client_queue, client_to_azure_queue, stop_event
    ):
        """Handle STT in a separate thread using websocket-client just like the example"""
        # WebSocket endpoint for Azure OpenAI Realtime API
        azure_ws_url = f"{self.stt_tts_endpoint.replace('https', 'wss')}/openai/realtime?api-version=2025-04-01-preview&intent=transcription"
        headers = {"api-key": self.stt_tts_key}

        def on_open(ws):
            print("Azure STT WebSocket connected")
            # Send the same session config as your working example
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

            # Start audio forwarding thread
            threading.Thread(target=forward_audio, args=(ws,), daemon=True).start()

        def forward_audio(ws):
            """Forward audio from client to Azure in a loop"""
            try:
                while not stop_event.is_set() and ws.sock and ws.sock.connected:
                    try:
                        # Get audio data with a timeout to check stop_event regularly
                        data = client_to_azure_queue.get(timeout=0.1)
                        if data.get("type") == "audio_data":
                            ws.send(
                                json.dumps(
                                    {
                                        "type": "input_audio_buffer.append",
                                        "audio": data.get("audio"),
                                    }
                                )
                            )
                    except queue.Empty:
                        continue
            except Exception as e:
                print(f"Error in audio forwarding: {e}")

        def on_message(ws, message):
            try:
                data = json.loads(message)
                event_type = data.get("type", "")

                # Handle different event types from Azure
                if event_type == "conversation.item.input_audio_transcription.delta":
                    # Forward incremental transcript to client
                    azure_to_client_queue.put(
                        {"type": "transcript_delta", "text": data.get("delta", "")}
                    )
                elif (
                    event_type
                    == "conversation.item.input_audio_transcription.completed"
                ):
                    # Forward completed transcript to client
                    azure_to_client_queue.put(
                        {
                            "type": "transcript_complete",
                            "text": data.get("transcript", ""),
                        }
                    )
                elif event_type == "item":
                    # Sometimes Azure sends a different event format
                    transcript = data.get("item", "")
                    if transcript:
                        azure_to_client_queue.put(
                            {"type": "transcript_complete", "text": transcript}
                        )
            except Exception as e:
                print(f"Error processing message: {e}")

        def on_error(ws, error):
            print(f"Azure WebSocket error: {error}")
            azure_to_client_queue.put({"type": "stt_error", "error": str(error)})

        def on_close(ws, close_status_code, close_msg):
            print("Azure WebSocket closed")
            if not stop_event.is_set():
                # If not intentionally stopped, report error
                azure_to_client_queue.put(
                    {
                        "type": "stt_error",
                        "error": "Azure WebSocket connection closed unexpectedly",
                    }
                )

        # Create and run the WebSocket client
        ws_app = websocket.WebSocketApp(
            azure_ws_url,
            header=headers,  # Note: header not extra_headers
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        ws_app.run_forever()

    async def _forward_azure_to_client(
        self, client_ws, azure_to_client_queue, stop_event
    ):
        """Forward messages from Azure to client in an async manner"""
        while not stop_event.is_set():
            try:
                # Check queue with a short timeout
                while not azure_to_client_queue.empty():
                    data = azure_to_client_queue.get_nowait()
                    await client_ws.send_str(json.dumps(data))

                # Sleep a bit to prevent CPU thrashing
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"Error forwarding to client: {e}")

    async def _handle_tts(self, websocket, data):
        from openai import AsyncAzureOpenAI

        # Use the stored environment variables
        if not self.stt_tts_endpoint or not self.stt_tts_key:
            await websocket.send_str(
                json.dumps(
                    {"type": "tts_error", "error": "Speech services not configured"}
                )
            )
            return

        client = AsyncAzureOpenAI(
            azure_endpoint=self.stt_tts_endpoint,
            api_key=self.stt_tts_key,
            api_version="2025-03-01-preview",
        )

        text = data.get("text", "")
        voice = data.get("voice", "coral")

        try:
            async with client.audio.speech.with_streaming_response.create(
                model="gpt-4o-mini-tts", voice=voice, input=text, response_format="pcm"
            ) as response:
                # Stream audio chunks back to client
                async for chunk in response.iter_bytes():
                    base64_chunk = base64.b64encode(chunk).decode("utf-8")
                    await websocket.send_str(
                        json.dumps({"type": "tts_chunk", "audio": base64_chunk})
                    )

                # Signal end of stream
                await websocket.send_str(json.dumps({"type": "tts_complete"}))

        except Exception as e:
            print(f"Error in TTS: {e}")
            await websocket.send_str(json.dumps({"type": "tts_error", "error": str(e)}))
