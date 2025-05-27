import asyncio
import os

from openai import AsyncAzureOpenAI
from openai.helpers import LocalAudioPlayer

from dotenv import load_dotenv

load_dotenv()

client = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_STT_TTS_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_STT_TTS_KEY"),
    api_version="2025-03-01-preview",
)


async def main() -> None:

    async with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="coral",
        input="""Hello, and welcome to your moment of mindfulness. I'm so glad you're here. Let's begin by closing your eyes and taking a deep, calming breath. Breathe in slowly through your nose, and exhale softly, releasing any tension.\n\nImagine your thoughts as soft clouds drifting across the sky—observe them without attachment, letting your mind become clear and peaceful.""",
        instructions="""Voice Affect: Soft, gentle, soothing; embody tranquility.\n\nTone: Calm, reassuring, peaceful; convey genuine warmth and serenity.\n\nPacing: Slow, deliberate, and unhurried; pause gently after instructions to allow the listener time to relax and follow along.\n\nEmotion: Deeply soothing and comforting; express genuine kindness and care.\n\nPronunciation: Smooth, soft articulation, slightly elongating vowels to create a sense of ease.\n\nPauses: Use thoughtful pauses, especially between breathing instructions and visualization guidance, enhancing relaxation and mindfulness.""",
        response_format="pcm",
    ) as response:
        await LocalAudioPlayer().play(response)


if __name__ == "__main__":
    asyncio.run(main())
