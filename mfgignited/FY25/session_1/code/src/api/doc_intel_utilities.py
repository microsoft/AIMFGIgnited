from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, ContentFormat, AnalyzeResult, DocumentAnalysisFeature
from azure.core.credentials import AzureKeyCredential
import os
import time
import logging

def table_to_html(table):
    """
    Converts a table object to an HTML table.

    Args:
    table (Table): The table object to be converted.

    Returns:
    table_html (str): The HTML representation of the table.
    """
    import html
    
    # Start the HTML table element
    table_html = "<table>"
    # Create rows based on the row_count and order cells by column_index
    rows = [sorted([cell for cell in table.cells if cell.row_index == i], key=lambda cell: cell.column_index) for i in range(table.row_count)]
    # Generate HTML for each row and cell
    for row_cells in rows:
        table_html += "<tr>"
        for cell in row_cells:
            # Use "th" for header cells and "td" for data cells
            tag = "th" if (cell.kind == "columnHeader" or cell.kind == "rowHeader") else "td"
            cell_spans = ""
            if cell.column_span > 1: cell_spans += f" colSpan={cell.column_span}"
            if cell.row_span > 1: cell_spans += f" rowSpan={cell.row_span}"
            # Escape the cell content to prevent HTML injection
            table_html += f"<{tag}{cell_spans}>{html.escape(cell.content)}</{tag}>"
        table_html +="</tr>"
    table_html += "</table>"
    return table_html

def extract_results(afr_result, source_file_name):
    """
    Extracts text and tables from Azure Form Recognizer analysis results and maps them to page numbers.

    Args:
    afr_result (AnalyzeResult): The result from Azure Form Recognizer analysis.
    source_file_name (str): The name of the source PDF file.

    Returns:
    page_map (list of tuples): A list of tuples containing the page number, page text, new file name, and source file name.
    """
    import re

    afr_result = AnalyzeResult.from_dict(afr_result)
    
    # Define the regex pattern to extract page ranges from file names
    pattern = r'__(\d+)-(\d+)\.pdf'
    match = re.search(pattern, source_file_name)
    
    # Default to the first page if no range is found in the file name
    start_page = 1
    
    # If a range is found, use the starting page from the range
    if match:
        start_page = int(match.group(1))
        
    page_map = []
    
    # Process each page in the analysis result
    for page_num, page in enumerate(afr_result.pages):
        # Identify tables present on the current page
        tables_on_page = [table for table in afr_result.tables if table.bounding_regions[0].page_number == page_num + 1]

        # Prepare to mark table characters in the page text
        page_offset = page.spans[0].offset
        page_length = page.spans[0].length
        table_chars = [-1] * page_length
        for table_id, table in enumerate(tables_on_page):
            for span in table.spans:
                for i in range(span.length):
                    idx = span.offset - page_offset + i
                    if 0 <= idx < page_length:
                        table_chars[idx] = table_id

        # Build the page text and insert HTML tables where appropriate
        page_text = ""
        added_tables = set()
        for idx, table_id in enumerate(table_chars):
            if table_id == -1:
                page_text += afr_result.content[page_offset + idx]
            elif table_id not in added_tables:
                page_text += table_to_html(tables_on_page[table_id])
                added_tables.add(table_id)
        
        # Calculate the actual page number in the document
        actual_page_num = page_num + start_page
        page_text += " "
        # Create a file name for the extracted page
        new_file_name = source_file_name.replace('.pdf', '') + '_' + str(actual_page_num) + '.pdf'
        # Add the page details to the page map
        page_map.append((actual_page_num, page_text, new_file_name, source_file_name))
    return page_map

# Analyze a document using Azure Document Intelligence's "prebuilt-document" model
def analyze_pdf(data, document_model):

    document_analysis_client = DocumentIntelligenceClient(endpoint=os.environ['DOC_INTEL_ENDPOINT'], credential=AzureKeyCredential(os.environ['DOC_INTEL_KEY']))
    json_result = {}

    processed = False
    while not processed:
        try:
            # Begin analysis of the document  
            poller = document_analysis_client.begin_analyze_document("prebuilt-layout", AnalyzeDocumentRequest(bytes_source=data), 
                                                                     output_content_format=ContentFormat.MARKDOWN,
                                                                     )  
            processed = True
            
            # Get the result of the analysis  
            result = poller.result()  
            
            # Convert the result to a dictionary  
            json_result = result.as_dict()  
        except Exception as e:
            time.sleep(5)
            print(e)
            logging.info(e)

    return json_result

# Read a document using Azure Document Intelligence's "prebuilt-read" model
def read_document(data):

    document_analysis_client = DocumentIntelligenceClient(endpoint=os.environ['DOC_INTEL_ENDPOINT'], credential=AzureKeyCredential(os.environ['DOC_INTEL_KEY']), api_version='2024-11-30')
    json_result = {}

    processed = False
    while not processed:
        try:
            # Begin analysis of the document  
            start = time.time()
            poller = document_analysis_client.begin_analyze_document(model_id="prebuilt-layout", document=data)  
            processed = True
            stop = time.time()
            
            # Get the result of the analysis  
            result = poller.result()  

            # Convert the result to a dictionary  
            json_result = result.to_dict()  
        except Exception as e:
            time.sleep(5)
            print(e)

    return json_result