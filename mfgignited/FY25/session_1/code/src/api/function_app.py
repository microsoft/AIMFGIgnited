import azure.functions as func
import datetime
import json
import logging
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

app = func.FunctionApp()

import azure.functions as func
import azure.durable_functions as df
import logging
import json
import os
import hashlib
from azure.cosmos import CosmosClient
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
from utils import *

from azure.ai.projects.models import (
    MessageTextContent,
    MessageInputContentBlock,
    MessageImageUrlParam,
    MessageInputTextBlock,
    MessageInputImageUrlBlock,
    ResponseFormat,
    AgentsApiResponseFormat,
    AgentsApiResponseFormatMode
)
from typing import List


app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)

# An HTTP-Triggered Function with a Durable Functions Client binding
@app.route(route="orchestrators/{functionName}")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client):
    function_name = req.route_params.get('functionName')
    payload = json.loads(req.get_body())

    instance_id = await client.start_new(function_name, client_input=payload)
    response = client.create_check_status_response(req, instance_id)
    return response

# Orchestrators
@app.orchestration_trigger(context_name="context")
def agent_document_analysis_orchestrator(context):

    first_retry_interval_in_milliseconds = 5000
    max_number_of_attempts = 2
    retry_options = df.RetryOptions(first_retry_interval_in_milliseconds, max_number_of_attempts)

    # Get the input payload from the context
    payload = context.get_input()
    
    # Extract the container names from the payload
    container = payload.get("container")
    filename = payload.get("filename")
    doc_intel_model = payload.get("doc_intel_model")
    analyze_prompt = payload.get("analyze_prompt")
    review_prompt = payload.get("review_prompt")
    schema = payload.get("target_schema")
    format_prompt = payload.get("format_prompt")
    format_template = payload.get("schema_types")
    max_iterations = payload.get("max_iterations", 8)
    cosmos_logging = payload.get("cosmos_logging", False)

    status_record = payload.copy()

    status_record['tokens_consumed'] = 0
    status_record['responses'] = []
    status_record['extract'] = ''
    status_record['id'] = context.instance_id

    analyst_agent_id = os.environ['ANALYST_AGENT_ID']
    reviewer_agent_id = os.environ['REVIEWER_AGENT_ID'] 
    formatter_agent_id = os.environ['FORMATTER_AGENT_ID']

    try:
        if cosmos_logging:
            payload = yield context.call_activity("create_status_record", json.dumps({'cosmos_id': context.instance_id, 'record': status_record}))
            context.set_custom_status('Created Cosmos Record Successfully')
    except Exception as e:
        context.set_custom_status('Failed to Create Cosmos Record')
        pass


    # Confirm that all storage locations exist to support document ingestion
    try:
        container_check = yield context.call_activity_with_retry("check_containers", retry_options, json.dumps({'source_container': container}))
        context.set_custom_status('Intermediate Processing Containers Checked')
        
    except Exception as e:
        context.set_custom_status('Processing Failed During Container Check')
        logging.error(e)
        raise e
    
    image_container = f"{container}-images"
    document_intelligence_results_container = f"{container}-document-intelligence-results"
    processed_results_container = f"{container}-processed-results"

    # Initialize lists to store parent and extracted files
    parent_files = []
    extracted_files = []
    
     # Get the list of files in the source container
    try:
        files = yield context.call_activity_with_retry("get_source_files", retry_options, json.dumps({'source_container': container, 'extensions': ['.pdf'], 'prefix': filename}))
        context.set_custom_status('Retrieved Source Files')
    except Exception as e:
        context.set_custom_status('Ingestion Failed During File Retrieval')
        logging.error(e)
        raise e
    
    context.set_custom_status('Retrieved Source Files')


    try:
        extract_pdf_tasks = []
        for file in files:
            # Create a task to process the PDF page and append it to the extract_pdf_tasks list
            extract_pdf_tasks.append(context.call_activity("process_pdf_with_document_intelligence", json.dumps({'file':file, 'container': container, 'doc_intel_results_container': document_intelligence_results_container , 'doc_intel_model': doc_intel_model})))
        # Execute all the extract PDF tasks and get the results
        extracted_pdf_files = yield context.task_all(extract_pdf_tasks)
        extracted_pdf_files = [x for x in extracted_pdf_files if x is not None]

    except Exception as e:
        context.set_custom_status('Ingestion Failed During Document Intelligence Extraction')
        logging.error(e)
        raise e
    
    try:
        extract_image_tasks = []
        for file in files:
            # Create a task to process the PDF page and append it to the extract_pdf_tasks list
            extract_image_tasks.append(context.call_activity("save_pdf_images", json.dumps({'filename':file, 'source_container': container})))
        # Execute all the extract PDF tasks and get the results
        extracted_image_files = yield context.task_all(extract_image_tasks)
        extracted_image_files = [item for sublist in extracted_image_files for item in sublist]

    except Exception as e:
        context.set_custom_status('Processing Failed During Image Extraction')
        logging.error(e)
        raise e

    context.set_custom_status('Converted PDF to Images')

    if len(schema)==0:
        schema = json.loads(open('schema.json', 'r').read())
    if len(format_template)==0:
        format_template = json.loads(open('format.json', 'r').read())


    analyze = True
    review = False
    current_extract = ''
    current_feedback = ''
    previous_feedback = []
    ocr_text = extracted_pdf_files[0]['OCR']
    key_value_pairs = extracted_pdf_files[0]['DefaultDocumentExtract']
    total_tokens = 0
    responses = []
    iterations = 0

    # Connect to Foundry
    # Creaate 3 Threads
    # Start analysis loop
    project_client = AIProjectClient.from_connection_string(
        credential=DefaultAzureCredential(),
        conn_str=os.environ['AZURE_AI_FOUNDRY_CONNECTION_STRING'],
    )

    analyst_thread = project_client.agents.create_thread()
    reviewer_thread = project_client.agents.create_thread()
    formatter_thread = project_client.agents.create_thread()

    while True:
        iterations += 1
        if iterations > max_iterations:
            break
        if analyze:
            # call run agent workflow with analyze arguments
            resp, tokens = yield context.call_activity("run_agent_workflow", json.dumps({
                                                                                    'agent': 'analyze',
                                                                                    'agent_id': analyst_agent_id,
                                                                                    'thread_id': analyst_thread.id,
                                                                                    'template_schema': schema,
                                                                                    'ocr_text': ocr_text,
                                                                                    'key_value_pairs': key_value_pairs,                 
                                                                                    'image_files': extracted_image_files, 
                                                                                    'current_extract': current_extract,
                                                                                    'current_feedback': current_feedback, 
                                                                                }))
            current_extract = resp
            total_tokens += tokens

            responses.append({'AI Agent - Analyze - Output': resp, 'Response Timestamp': datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})
            context.set_custom_status(({'Consumed Tokens': total_tokens, 'Current Agent Response': resp}))

            analyze = False
            review = True
            if cosmos_logging:

                yield context.call_activity("update_status_record", json.dumps({'cosmos_id': context.instance_id, 'response': resp, 'agent': 'analyze'}))

            
        elif review:
            # call agent with review arguments
            resp, tokens = yield context.call_activity("run_agent_workflow", json.dumps({
                                                                                    'agent': 'review',
                                                                                    'agent_id':reviewer_agent_id,
                                                                                    'thread_id': reviewer_thread.id,
                                                                                    'template_schema': schema,
                                                                                    'ocr_text': ocr_text,
                                                                                    'key_value_pairs': key_value_pairs,                 
                                                                                    'image_files': extracted_image_files, 
                                                                                    'current_extract': current_extract,
                                                                                    'current_feedback': current_feedback, 
                                                                                }))
            current_feedback = resp
            review = False
            total_tokens += tokens
            
            responses.append({'AI Agent - Review - Output': resp, 'Response Timestamp': datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})
            context.set_custom_status(({'Consumed Tokens': total_tokens, 'Current Agent Response': resp}))
            if cosmos_logging:

                yield context.call_activity("update_status_record", json.dumps({'cosmos_id': context.instance_id, 'response': resp, 'agent': 'review'}))

            
            if current_feedback['complete']:
                break
            else:
                analyze = True
            pass


    # Call with format arguments
    resp, tokens = yield context.call_activity("run_agent_workflow", json.dumps({
                                                                            'agent': 'format',
                                                                            'agent_id':formatter_agent_id,
                                                                            'thread_id': formatter_thread.id,
                                                                            'template_schema': format_template,
                                                                            'ocr_text': ocr_text,
                                                                            'key_value_pairs': key_value_pairs,                 
                                                                            'image_files': extracted_image_files, 
                                                                            'current_extract': current_extract,
                                                                            'current_feedback': current_feedback, 
                                                                        }))
    
    current_extract = resp
    total_tokens += tokens

    responses.append({'AI Agent - Format - Output': resp, 'Response Timestamp': datetime.now().strftime("%m/%d/%Y, %H:%M:%S")})
    context.set_custom_status(({'Consumed Tokens': total_tokens, 'Final Agent Response': resp}))

    if cosmos_logging:
        yield context.call_activity("update_status_record", json.dumps({'cosmos_id': context.instance_id, 'response': resp, 'agent': 'format', 'extract': current_extract}))
    # Format should be separate

    saved_file = yield context.call_activity("save_extract", json.dumps({'result_container': processed_results_container, 'filename': filename, 'extract': current_extract}))

    return (saved_file)



@app.activity_trigger(input_name="activitypayload")
def run_agent_workflow(activitypayload: str):

    data = json.loads(activitypayload)
    ocr_text = data.get("ocr_text")
    key_value_pairs = data.get("key_value_pairs")
    image_files = data.get("image_files")
    current_extract = data.get("current_extract")
    agent = data.get("agent")
    agent_id = data.get("agent_id")
    thread_id = data.get("thread_id")
    schema = data.get("template_schema")
    current_feedback = data.get("current_feedback")

    if agent=='analyze':

        user_prompt = f'''## Target Schema: {schema}

        -------------------------------------------------------
        
        ## Document OCR Text: {ocr_text}

        -------------------------------------------------------

        ## Document Key-Value Pairs: {key_value_pairs}

        -------------------------------------------------------
        
        ## Current Extract: {current_extract}

        -------------------------------------------------------

        ## Current Feedback: {current_feedback}
        
        -------------------------------------------------------
        '''
    elif agent=='review':

        user_prompt = f'''## Target Schema: {schema}

        -------------------------------------------------------

        ## Current Extract: {current_extract}

        -------------------------------------------------------

        ## Product Diagram OCR Text: {ocr_text}

        -------------------------------------------------------

        ## Product Diagram Key-Value Pairs: {key_value_pairs}

        -------------------------------------------------------

        '''

    elif agent=='format':
            
        user_prompt = f'''## Format Template: {schema}

        -------------------------------------------------------

        ## Current Extract: {current_extract}

        '''
    
    # img_url = f"data:image/png;base64,{image_base64}"
    # url_param = MessageImageUrlParam(url=img_url, detail="high")

    project_client = AIProjectClient.from_connection_string(
        credential=DefaultAzureCredential(),
        conn_str=os.environ['AZURE_AI_FOUNDRY_CONNECTION_STRING'],
    )
    
    if agent!='format':
        content_blocks: List[MessageInputContentBlock] = [
            MessageInputTextBlock(text=user_prompt),
            # MessageInputImageUrlBlock(image_url=url_param),
        ]
        for image in image_files:
            img_url = f"data:image/png;base64,{image['image']}"
            url_param = MessageImageUrlParam(url=img_url, detail="high")
            content_blocks.append(MessageInputImageUrlBlock(image_url=url_param))
    
        message = project_client.agents.create_message(thread_id=thread_id, role="user", content=content_blocks)
    else:
        message = project_client.agents.create_message(thread_id=thread_id, role="user", content=[MessageInputTextBlock(text=user_prompt)])

    processed = False
    while not processed:
        try:

            agent_run = project_client.agents.create_and_process_run(thread_id=thread_id, agent_id=agent_id, response_format={ "type": "json_object" })

            print(agent_run.usage, flush=True)
            messages = project_client.agents.list_messages(thread_id=thread_id)
            last_msg = messages.get_last_text_message_by_role(role="assistant")
            print(last_msg, flush=True)
            print(type(last_msg), flush=True)
            msg = last_msg.text.value.replace('```json', '').replace('```', '')
            try:
                return json.loads(msg), agent_run.usage.total_tokens
            except Exception as e:
                return msg
        except Exception as e:
            time.sleep(5)
            print('Run Failed. Retrying...', flush=True)
            pass


@app.activity_trigger(input_name="activitypayload")
def get_source_files(activitypayload: str):

    # Load the activity payload as a JSON string
    data = json.loads(activitypayload)
    
    # Extract the source container, file extension, and prefix from the payload
    source_container = data.get("source_container")
    extensions = data.get("extensions")
    prefix = data.get("prefix")
    
    # Create a BlobServiceClient object which will be used to create a container client
    blob_service_client = BlobServiceClient.from_connection_string(os.environ['STORAGE_CONN_STR'])
    
    try:
        # Get a ContainerClient object from the BlobServiceClient
        container_client = blob_service_client.get_container_client(source_container)
        # List all blobs in the container that start with the specified prefix
        blobs = container_client.list_blobs(name_starts_with=prefix)

    except Exception as e:
        # If the container does not exist, return an empty list
        return []

    if not container_client.exists():
        return []
    
    # Initialize an empty list to store the names of the files
    files = []

    # For each blob in the container
    for blob in blobs:
        # If the blob's name ends with the specified extension
        if '.' + blob.name.lower().split('.')[-1] in extensions:
            # Append the blob's name to the files list
            files.append(blob.name)

    # Return the list of file names
    return files

@app.activity_trigger(input_name="activitypayload")
def process_pdf_with_document_intelligence(activitypayload: str):
    """
    Process a PDF file using Document Intelligence.

    Args:
        activitypayload (str): The payload containing information about the PDF file.

    Returns:
        str: The updated filename of the processed PDF file.
    """

    # Load the activity payload as a JSON string
    data = json.loads(activitypayload)

    # Extract the file name and container names from the payload
    file = data.get("file")
    container = data.get("container")
    doc_intel_results_container = data.get("doc_intel_results_container")
    doc_intel_model = data.get("doc_intel_model")

    # Create a BlobServiceClient object which will be used to create a container client
    blob_service_client = BlobServiceClient.from_connection_string(os.environ['STORAGE_CONN_STR'])

    pdf_blob_client = blob_service_client.get_blob_client(container, file)

    # Get a ContainerClient object for the pages, Document Intelligence results, and DI formatted results containers
    doc_intel_results_container_client = blob_service_client.get_container_client(container=doc_intel_results_container)

    # Initialize a flag to indicate whether the PDF file has been processed
    processed = False

    # Create a new file name for the processed PDF file
    updated_filename = file.replace('.pdf', '.json')

    # Get a BlobClient object for the Document Intelligence results file
    doc_results_blob_client = doc_intel_results_container_client.get_blob_client(blob=updated_filename)
    # Check if the Document Intelligence results file exists
    if doc_results_blob_client.exists():

        # Get a BlobClient object for the Document Intelligence results file
        doc_intel_result_client = doc_intel_results_container_client.get_blob_client(updated_filename)

        doc_intel_result = json.loads(doc_intel_result_client.download_blob().readall())

    # If the PDF file has not been processed
    else:
        # Extract the PDF file with AFR, save the AFR results, and save the extract results

        # Download the PDF file
        pdf_data = pdf_blob_client.download_blob().readall()
        # Analyze the PDF file with Document Intelligence
        doc_intel_result = analyze_pdf(pdf_data, doc_intel_model)

        # Get a BlobClient object for the Document Intelligence results file
        doc_intel_result_client = doc_intel_results_container_client.get_blob_client(updated_filename)

        # Upload the Document Intelligence results to the Document Intelligence results container
        doc_intel_result_client.upload_blob(json.dumps(doc_intel_result, default=custom_serializer), overwrite=True)

    document_key_values = {}
    # for item in doc_intel_result['keyValuePairs']:
    #     try:
    #         document_key_values[item['key']['content']] = item['value']['content']
    #     except Exception as e:
    #         pass
    
    
    return {'OCR': doc_intel_result['content'], 'DefaultDocumentExtract': document_key_values, 'file': file}

    # Return the updated file name
    return updated_filename


@app.activity_trigger(input_name="activitypayload")
def save_pdf_images(activitypayload: str):

    data = json.loads(activitypayload)
    source_container = data.get('source_container')
    filename = data.get('filename')

    blob_service_client = BlobServiceClient.from_connection_string(os.getenv('STORAGE_CONN_STR'))
    container_client = blob_service_client.get_container_client(source_container)   
    blob_client = container_client.get_blob_client(filename)

    data = blob_client.download_blob().readall()

    pdf_reader = PdfReader(BytesIO(data))

    # Get the number of pages in the PDF file
    num_pages = len(pdf_reader.pages)

    images_container_name = f"{source_container}-images"
    images_container = blob_service_client.get_container_client(images_container_name)

    image_files = []

    # For each page in the PDF file
    for i in range(num_pages):
        # Create a new file name for the PDF chunk
        new_file_name = filename.replace('.pdf', '') + '_page_' + str(i+1) + '.png'

        # Create a PdfWriter object
        pdf_writer = PdfWriter()
        # Add the page to the PdfWriter object
        pdf_writer.add_page(pdf_reader.pages[i])

        # Create a BytesIO object for the output stream
        output_stream = BytesIO()
        # Write the PdfWriter object to the output stream
        pdf_writer.write(output_stream)

        # Reset the position of the output stream to the beginning
        output_stream.seek(0)

        png_bytes = pdf_bytes_to_png_bytes(output_stream)

        images_blob_client = images_container.get_blob_client(new_file_name)
        images_blob_client.upload_blob(png_bytes.read(), overwrite=True)

        data = images_blob_client.download_blob().readall()

        image_files.append({'file': new_file_name, 'image': base64.b64encode(data).decode('utf-8')})

    return image_files

@app.activity_trigger(input_name="activitypayload")
def check_containers(activitypayload: str):

    # Load the activity payload as a JSON string
    data = json.loads(activitypayload)
    
    # Extract the source container, file extension, and prefix from the payload
    source_container = data.get("source_container")
    
    image_container = f"{source_container}-images"
    document_intelligence_results_container = f"{source_container}-document-intelligence-results"
    processed_results_container = f"{source_container}-processed-results"
    
    # Create a BlobServiceClient object which will be used to create a container client
    blob_service_client = BlobServiceClient.from_connection_string(os.environ['STORAGE_CONN_STR'])

    try:
        blob_service_client.create_container(image_container)
    except Exception as e:
        pass

    try:
        blob_service_client.create_container(document_intelligence_results_container)
    except Exception as e:
        pass

    try:
        blob_service_client.create_container(processed_results_container)
    except Exception as e:
        pass

    # Return the list of file names
    return True

@app.activity_trigger(input_name="activitypayload")
def save_extract(activitypayload: str):

    # Load the activity payload as a JSON string
    data = json.loads(activitypayload)
    
    # Extract the source container, file extension, and prefix from the payload
    result_container = data.get("result_container")
    filename = data.get("filename")
    extract = data.get("extract")
    
    blob_service_client = BlobServiceClient.from_connection_string(os.environ['STORAGE_CONN_STR'])

    container_client = blob_service_client.get_container_client(result_container)

    updated_filename = filename.replace('.pdf', '.json')

    blob_client = container_client.get_blob_client(updated_filename)

    blob_client.upload_blob(json.dumps(extract), overwrite=True)

    return updated_filename

@app.activity_trigger(input_name="activitypayload")
def create_status_record(activitypayload: str):

    # Load the activity payload as a JSON string
    data = json.loads(activitypayload)
    record = data.get("record")
    cosmos_id = data.get("cosmos_id")
    cosmos_container = os.environ['COSMOS_CONTAINER']
    cosmos_database = os.environ['COSMOS_DATABASE']
    cosmos_endpoint = os.environ['COSMOS_ENDPOINT']
    cosmos_key = os.environ['COSMOS_KEY']
    record['id'] = cosmos_id

    data['id'] = cosmos_id

    client = CosmosClient(cosmos_endpoint, cosmos_key)

    # Select the database
    database = client.get_database_client(cosmos_database)

    # Select the container
    container = database.get_container_client(cosmos_container)

    # response = container.read_item(item=cosmos_id)
    response = container.create_item(record)
    if type(response) == dict:
        return response
    return json.loads(response)


@app.activity_trigger(input_name="activitypayload")
def update_status_record(activitypayload: str):

    # Load the activity payload as a JSON string
    data = json.loads(activitypayload)
    response = data.get("response")
    agent = data.get("agent")
    tokens = data.get("tokens")
    timestamp = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    cosmos_id = data.get("cosmos_id")
    final_response = None
    if 'extract' in data.keys():
        final_response = data.get("extract")

    cosmos_container = os.environ['COSMOS_CONTAINER']
    cosmos_database = os.environ['COSMOS_DATABASE']
    cosmos_endpoint = os.environ['COSMOS_ENDPOINT']
    cosmos_key = os.environ['COSMOS_KEY']

    client = CosmosClient(cosmos_endpoint, cosmos_key)

    # Select the database
    database = client.get_database_client(cosmos_database)

    # Select the container
    container = database.get_container_client(cosmos_container)

    # Retrieve the existing record from Cosmos DB
    existing_record = container.read_item(item=cosmos_id, partition_key=cosmos_id)

    # Update the attribute on the retrieved record
    if 'responses' not in existing_record:
        existing_record['responses'] = []  

    existing_record['responses'].append({'agent': agent, 'response': response, 'timestamp': timestamp})
    # existing_record['tokens_consumed'] += tokens

    if final_response is not None:
        existing_record['extract'] = final_response

    # Upsert the updated record back into Cosmos DB
    container.upsert_item(existing_record)

    return True