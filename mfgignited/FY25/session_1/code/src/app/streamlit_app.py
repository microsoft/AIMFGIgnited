import streamlit as st
from datetime import datetime
import json
import os
from dotenv import load_dotenv
import requests
import time
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential
import re
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import pandas as pd
from azure.ai.projects import AIProjectClient


# Load environment variables
load_dotenv(override=True)

# Set up the page title
st.set_page_config(page_title="Microsoft Demo - Complex Document Analysis (AI Agent Service)", layout="wide")

# Main title
st.title("Microsoft Demo - Complex Document Analysis (AI Agent Service)")

st.session_state.processing = False

max_date = None
max_file = None

project_client = project_client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str=os.environ['AZURE_AI_FOUNDRY_CONNECTION_STRING'],
)

analyst_agent_id = os.environ['ANALYST_AGENT_ID']
reviewer_agent_id = os.environ['REVIEWER_AGENT_ID']
formatter_agent_id = os.environ['FORMATTER_AGENT_ID']



if os.path.exists('./prompt_edits'):
    files = os.listdir('./prompt_edits')
    for filename in files:
        pattern = r'prompts_(\d{8})_(\d{6})\.json'  
  
        # Search for the pattern in the filename  
        match = re.search(pattern, filename)  
        if match:  
            date_str = match.group(1)  # '20241120'  
            time_str = match.group(2)  # '121716'  
        
            # Combine the date and time strings  
            datetime_str = f'{date_str} {time_str}'  # '20241120 121716'  
        
            # Parse the combined string into a datetime object  
            dt = datetime.strptime(datetime_str, '%Y%m%d %H%M%S')  
        
            if max_date is None:
                max_date = dt
                max_file = filename
            elif dt > max_date:
                max_date = dt
                max_file = filename

        else:  
            print('Filename does not match the expected pattern')  


# Tabs
tab1, tab2, tab3 = st.tabs(["Agent Instructions & Schema", "Agent Analysis - Single Document", "Agent Analysis - Batch Processing"])

if 'analyst_prompt' not in st.session_state:

    analyst_agent_instructions = project_client.agents.get_agent(analyst_agent_id).instructions
    reviewer_agent_instructions = project_client.agents.get_agent(reviewer_agent_id).instructions
    formatter_agent_instructions = project_client.agents.get_agent(formatter_agent_id).instructions
    st.session_state.analyst_prompt = analyst_agent_instructions
    st.session_state.reviewer_prompt = reviewer_agent_instructions
    st.session_state.formatter_prompt = formatter_agent_instructions

    if max_file is None:
        with open('schema.json', 'r') as file:
            st.session_state.target_schema = file.read()
        with open('format.json', 'r') as file:
            st.session_state.data_types = file.read()

    else:
        data = json.load(open(os.path.join('./prompt_edits', max_file)))
        st.session_state.target_schema = data['Target Schema']
        st.session_state.data_types = data['Data Types']

    st.session_state.filename = 'page_1.pdf'
    st.session_state.cosmos_logging_single = False
    st.session_state.cosmos_logging_batch = False
    st.session_state.cosmos_logging = False

st.session_state.processing_status = ''
st.session_state.agent_outputs = []

# Define the save_prompts function
def save_prompts():
    # Get the values of all text fields
    prompts_data = {
        "Target Schema": st.session_state.target_schema,
        "Data Types": st.session_state.data_types,
    }
    # Ensure the directory exists
    os.makedirs('prompt_edits', exist_ok=True)

    # Create a timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'prompt_edits/prompts_{timestamp}.json'

    # Save the prompts data to the file
    with open(filename, 'w') as f:
        json.dump(prompts_data, f, indent=4)

    project_client.agents.update_agent(agent_id=analyst_agent_id, instructions=st.session_state.analyst_prompt)
    project_client.agents.update_agent(agent_id=reviewer_agent_id, instructions=st.session_state.reviewer_prompt)
    project_client.agents.update_agent(agent_id=formatter_agent_id, instructions=st.session_state.formatter_prompt)

    # Show the filename in the success message
    st.success(f"Agents have been updated in Azure AI Foundry and data schemas have been successfully saved to {filename}!")

    st.json(prompts_data)  # Display the saved data (for debugging/demo purposes)

def get_cosmos_record(id):

    cosmos_container = os.environ['COSMOS_CONTAINER']
    cosmos_database = os.environ['COSMOS_DATABASE']
    cosmos_endpoint = os.environ['COSMOS_ENDPOINT']
    cosmos_key = os.environ['COSMOS_KEY']
    cosmos_id = id

    client = CosmosClient(cosmos_endpoint, cosmos_key)

    # Select the database
    database = client.get_database_client(cosmos_database)

    # Select the container
    container = database.get_container_client(cosmos_container)

    # Retrieve the existing record from Cosmos DB
    existing_record = container.read_item(item=cosmos_id, partition_key=cosmos_id)

    return existing_record

def cosmos_logging_changed_batch():
    print(st.session_state.cosmos_logging_batch)   
    st.session_state.cosmos_logging = st.session_state.cosmos_logging_batch
    print(st.session_state.cosmos_logging)

def cosmos_logging_changed_single():
    print(st.session_state.cosmos_logging_single)   
    st.session_state.cosmos_logging = st.session_state.cosmos_logging_single
    print(st.session_state.cosmos_logging)

# Define the analyze_document function
def analyze_document(filename, max_iterations):
    # Replace with actual analysis logic
    # st.success(f"Analyzing '{filename}' with a maximum of {max_iterations} iterations...")

    uri = os.getenv('FUNCTION_URI') + '/api/orchestrators/agent_document_analysis_orchestrator?code=' + os.getenv('FUNCTION_KEY')
    body = {
        'container': os.getenv('DOCUMENT_CONTAINER'),
        'filename': filename,
        'target_schema': st.session_state.target_schema,
        'schema_types': st.session_state.data_types,
        'max_iterations': st.session_state.max_iterations,
        'cosmos_logging': st.session_state.cosmos_logging
    }

    response = requests.post(uri, json=body)
    response.json()
    id = response.json()['id']
    st.session_state.id = id
    status_uri = response.json()['statusQueryGetUri']

    st.session_state.processing = True
    st.session_state.status_uri = status_uri


# Content for 'Prompts' tab
with tab1:
    # Create columns with spacers
    col1, spacer1, col2, spacer2, col3 = st.columns([5, 1, 5, 1, 5])

    # Add the first three text areas to columns
    with col1:
        st.markdown("### Analyst Prompt")  # Larger label
        st.text_area(
            "Instructions for analyzing incoming diagrams and generating extracts",
            key="analyst_prompt",
            placeholder="Enter instructions for the Analyst here...",
            height=500  # Approx. 15 lines
        )

    with col2:
        st.markdown("### Reviewer Prompt")  # Larger label
        st.text_area(
            "Instructions for reviewing diagram extracts and suggesting changes",
            key="reviewer_prompt",
            placeholder="Enter instructions for the Reviewer here...",
            height=500  # Approx. 15 lines
        )

    with col3:
        st.markdown("### Formatter Prompt")  # Larger label
        st.text_area(
            "Instructions for generating a formatted extract with expected data types",
            key="formatter_prompt",
            placeholder="Enter instructions for the Formatter here...",
            height=500  # Approx. 15 lines
        )

    # Add a break below the first row of columns
    st.markdown("---")  # Horizontal rule as a break

    # Create two columns with spacing for the remaining text areas
    col4, spacer3, col5 = st.columns([6, 1, 6])

    with col4:
        st.markdown("### Target Schema")  # Larger label
        st.text_area(
            "Description of information to be extracted from all diagrams",
            key="target_schema",
            placeholder="Describe the target schema here...",
            height=600  # Approx. 15 lines
        )

    with col5:
        st.markdown("### Data Types")  # Larger label
        st.text_area(
            "Data types associated with each field in the extract schema",
            key="data_types",
            placeholder="Describe the data types here...",
            height=600  # Approx. 15 lines
        )
    
    st.markdown("---") 

    # Add a "Save Prompts" button
    if st.button("Save Prompts"):
        save_prompts()

# Content for 'Agent Analysis' tab
with tab2:
    st.header("Agent Analysis")

    # Add a text box for the filename
    filename = st.text_input(
        "Filename",
        key="filename",
        placeholder="Enter the filename of the diagram..."
    )

    # Add a numerical input for max iterations
    max_iterations = st.number_input(
        "Max Iterations",
        key="max_iterations",
        min_value=1,
        max_value=100,
        value=10,  # Default value
        step=1
    )

    st.radio('Enable Cosmos Logging', [True, False], key="cosmos_logging_single", on_change=cosmos_logging_changed_single)

    # Add an "Analyze Document" button
    if st.button('Analyze Document'):
        if filename.strip():
            analyze_document(filename, max_iterations)
            # Create placeholders for the status and agent outputs
            status_placeholder = st.empty()
            output_placeholder = st.empty()

            with st.spinner(f'Running Agent Analysis on {filename}...'):
                while True:
                    resp = requests.get(st.session_state.status_uri)

                    # Extract status and outputs
                    status = resp.json().get('runtimeStatus', 'Unknown')
                    st.session_state.processing_status = status
                    status_placeholder.text(f"Status: {st.session_state.processing_status}")
                    if type(resp.json().get('customStatus', '')) == dict:
                        if st.session_state.cosmos_logging:
                            cosmos_record = get_cosmos_record(st.session_state.id)
                            responses = cosmos_record['responses'][::-1]
                            st.session_state.agent_outputs = (responses)
                            output_placeholder.json(responses)
                        else:
                            st.session_state.agent_outputs = resp.json().get('customStatus', '')
                            output_placeholder.json(st.session_state.agent_outputs)
                    else:
                        st.session_state.agent_outputs = resp.json().get('customStatus', '')
                        output_placeholder.markdown(st.session_state.agent_outputs)

                    # Update placeholders with new status and output
                   
                    

                    # Handle status updates
                    if status == 'Completed':
                        st.session_state.processing = False
                        break
                    elif status == 'Failed':
                        st.error("Analysis failed!")
                        st.session_state.processing = False
                        break

                    time.sleep(2)
        else:
            st.error('Analysis failed!')


with tab3:
    blob_service_client = BlobServiceClient.from_connection_string(os.getenv('STORAGE_CONN_STR'))
    container_name = os.getenv('DOCUMENT_CONTAINER')
    container_client = blob_service_client.get_container_client(container_name)
    blobs = container_client.list_blobs()

    files = []
    for blob in blobs:
        files.append(blob.name)
    df = pd.DataFrame(files, columns=['Filename'])
    st.session_state.df = df
    event = st.dataframe(
        st.session_state.df,
        key='data',
        on_select="rerun",
        selection_mode=["multi-row"],
        use_container_width=True,
        hide_index=True
    )

    st.radio('Enable Cosmos Logging', [True, False], key="cosmos_logging_batch", on_change=cosmos_logging_changed_batch)

    if st.button('Analyze Selected Files'):
        st.markdown("---")
        if event is not None:
            processing_dict = {}
            for index in event.selection.rows:
                filename = st.session_state.df.iloc[index]['Filename']
                print(filename)
                analyze_document(filename, 10)
                processing_dict[filename] = st.session_state.status_uri

            processing_placeholder = st.empty()
            done = False
            while not done:
                rows = []
                done = True
                for filename, uri in processing_dict.items():
                    resp = requests.get(uri)

                    # Extract status and outputs
                    status = resp.json().get('runtimeStatus', 'Unknown')
                    custom_status = resp.json().get('customStatus', '')
                    if status != 'Completed' and status != 'Failed':
                        done = False
                
                    rows.append([filename, status, custom_status])
                df = pd.DataFrame(rows, columns=['Filename', 'Status', 'Output'])
                processing_placeholder.dataframe(df, hide_index=True, use_container_width=True)
                time.sleep(2)


    if st.button('Retrieve Processed Results'):
        blob_service_client = BlobServiceClient.from_connection_string(os.getenv('STORAGE_CONN_STR'))
        result_container = os.getenv('DOCUMENT_CONTAINER') + '-processed-results'
        result_container_client = blob_service_client.get_container_client(result_container)
        results = []
        for blob in result_container_client.list_blobs():
            blob_client = result_container_client.get_blob_client(blob.name)
            result_data = {'Filename': blob.name}
            data = json.loads(blob_client.download_blob().readall())
            data = {**result_data, **data}
            results.append(data)
        
        # Lists to hold flattened data  
        revision_rows = []  
        bom_rows = []  
        rows = []
        
        # Process each object in the list  
        for data in results:  
            print(data)
            copy = dict(data).copy()
           
            rows.append(copy)
       
        print(rows)
        new_df = pd.DataFrame(rows)
        st.session_state.results_df = new_df
        st.markdown("---")
        st.dataframe(st.session_state.results_df, hide_index=True, use_container_width=True)
            