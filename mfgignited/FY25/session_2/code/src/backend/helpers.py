from io import BytesIO
import base64
import os
from azure.storage.blob.aio import BlobClient


async def get_blob_as_base64(blob_client: BlobClient):
    try:
        stream = BytesIO()
        download_stream = await blob_client.download_blob()
        await download_stream.readinto(stream)

        base64_image = base64.b64encode(stream.getvalue()).decode("utf-8")
        return base64_image

    except Exception as e:
        print(f"Error retrieving blob as Base64: {e}")
        return None
