import azure.functions as func
import azure.durable_functions as df
import logging
import json
import os
import hashlib
from azure.storage.blob import BlobServiceClient
from pypdf import PdfReader, PdfWriter
from io import BytesIO
from datetime import datetime
import filetype
import fitz as pymupdf
from PIL import Image
import io
import base64
from doc_intel_utilities import *
from datetime import date
from openai import AzureOpenAI

def load_doc_intel_result(source_container, results_filename):
    blob_service_client = BlobServiceClient.from_connection_string(os.getenv('STORAGE_CONN_STR'))
    container_client = blob_service_client.get_container_client(source_container)   
    blob_client = container_client.get_blob_client(results_filename)

    data = blob_client.download_blob().readall()

    return json.loads(data)

def retrieve_document_content(doc_intel_results):
    document_content = doc_intel_results['content']
    document_key_values = {}
    if len(doc_intel_results['documents'])>0:
        for k, v in doc_intel_results['documents'][0]['fields'].items():
            document_key_values[k] = v['content']
    
    return {'OCR': doc_intel_results['content'], 'DefaultExtract': document_key_values}

def gather_document_inputs(source_container, filename):
    results_container_name = f"{source_container}-document-intelligence-results"
    images_container_name = f"{source_container}-images"

    blob_service_client = BlobServiceClient.from_connection_string(os.getenv('STORAGE_CONN_STR'))
    results_container = blob_service_client.get_container_client(results_container_name)
    images_container = blob_service_client.get_container_client(images_container_name)

    updated_filename = filename.replace(".pdf", ".json")

    results = load_doc_intel_result(results_container_name, updated_filename)
    document_content = retrieve_document_content(results)
    images = []

    image_container_client = blob_service_client.get_container_client(images_container_name)
    image_list = image_container_client.list_blobs(name_starts_with=filename.replace(".pdf", "_page_"))

    for image in image_list:
        image_blob_client = image_container_client.get_blob_client(image.name)
        png_bytes = image_blob_client.download_blob().readall()
        image_data = base64.b64encode(png_bytes).decode('ascii')
        images.append(image_data)

    return {'document_content': document_content, 'images': images}

def review_extract(reviewer_system_message, current_extract, images, ocr_text, critiques=[]):

    client = AzureOpenAI(
        azure_endpoint = os.getenv("AOAI_ENDPOINT"), 
        api_key=os.getenv("AOAI_KEY"),  
        api_version="2024-05-01-preview"
    )
    system_message = reviewer_system_message
    messages = [{'role': 'system', 'content': system_message}]
    messages.append({'role': 'user', 'content': f'# CURRENT INVOICE EXTRACTION: {json.dumps(current_extract)}\n# INVOICE OCR TEXT: {json.dumps(ocr_text)}\n# PREVIOUS CRITIQUES: {json.dumps(critiques)}'})
    for image in images:
        img_msg = {
            "role": "user",
            "content": [
                {
                "type": "image_url",
                "image_url": {
                        "url": f"data:image/jpeg;base64,{image}"
                        , "detail": "high"
                    }
                }  
            ]
        }
        messages.append(img_msg)
        
    response = client.chat.completions.create(
            model=os.environ['AOAI_GPT_MODEL'],
            messages=messages,
            temperature=0.0
        )
    print(response)
    return response.choices[0].message.content, response.usage.prompt_tokens, response.usage.completion_tokens

def pdf_bytes_to_png_bytes(pdf_bytes, page_number=1):
    # Load the PDF from a bytes object
    # pdf_stream = io.BytesIO(pdf_bytes)
    document = pymupdf.open("pdf", pdf_bytes)

    # Select the page
    page = document.load_page(page_number - 1)  # Adjust for zero-based index

    # Render page to an image
    pix = page.get_pixmap(dpi=100)

    # Convert the PyMuPDF pixmap into a Pillow Image
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    # Create a BytesIO object for the output PNG
    png_bytes_io = io.BytesIO()

    # Save the image to the BytesIO object using Pillow
    img.save(png_bytes_io, "PNG")


    # Rewind the BytesIO object to the beginning
    png_bytes_io.seek(0)

    # Close the document
    document.close()

    # Return the BytesIO object containing the PNG image
    return png_bytes_io

def custom_serializer(obj):
    if isinstance(obj, date):
        return obj.isoformat()  # Convert date to string
    raise TypeError(f"Type {type(obj)} not serializable")