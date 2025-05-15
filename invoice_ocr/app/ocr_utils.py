import json
import os
import re
import tempfile

from langchain_community.document_loaders.image import UnstructuredImageLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# Load API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Initialize the LLM
llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)

def load_image_content_from_bytes(image_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
        tmp_file.write(image_bytes)
        tmp_file_path = tmp_file.name
    loader = UnstructuredImageLoader(tmp_file_path)
    data = loader.load()
    os.remove(tmp_file_path)
    return data[0]

def create_prompt():
    template = """
    You are an AI assistant tasked with extracting structured information from invoice text.
    Given the following content, extract the required fields and format them according to the provided schema.

    Content:
    {content}

    Schema:
    {schema}

    Please ensure the output strictly adheres to the schema format.
    """
    return PromptTemplate(input_variables=["content", "schema"], template=template)

def extract_data(content, schema):
    prompt = create_prompt()
    output_parser = StrOutputParser()
    chain = prompt | llm | output_parser
    result = chain.invoke({"content": content, "schema": schema})
    cleaned_result = re.sub(r"^```(?:json)?\n|\n```$", "", result.strip())
    try:
        parsed_result = json.loads(cleaned_result)
    except json.JSONDecodeError as e:
        print("Failed to parse result to JSON:", e)
        parsed_result = {"error": "Invalid JSON", "raw_result": cleaned_result}
    return parsed_result

def process_invoice(image_bytes):
    content = load_image_content_from_bytes(image_bytes)
    schema = {
        "image": "filebudget/s3.pdf",
        "extracted_parse": [
            {"label": "Invoice Number"},
            {"label": "Invoice Date"},
            {"label": "Buyer Name"},
            {"label": "Seller Name"},
            {
                "label": "Items",
                "type": "table",
                "columns": ["Item", "Quantity", "Rate", "Amount"],
            },
            {"label": "Tax Amount"},
            {"label": "Total Amount"},
            {"label": "PO Number"},
            {"label": "Payment Terms"},
            {"label": "Currency"},
        ],
    }
    return extract_data(content, schema)
