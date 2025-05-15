import json
import os
import re
import tempfile

from langchain_community.document_loaders.image import UnstructuredImageLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from  src.invoice_ocr.utils import create_prompt

class InvoiceProcessor:
    def __init__(self):
        """
        Initialize the invoice processor with OpenAI API credentials.
        Raises an error if the API key is not set in the environment.
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.llm = ChatOpenAI(model="gpt-4o-mini", api_key=self.api_key)

    def load_image_content_from_bytes(self, image_bytes):
        """
        Load text content from an image using Unstructured's image loader.
        Saves the image temporarily and returns extracted text content.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_file.write(image_bytes)
            tmp_file_path = tmp_file.name

        loader = UnstructuredImageLoader(tmp_file_path)
        data = loader.load()
        os.remove(tmp_file_path)
        return data[0]

    def extract_data(self, content, schema):
        """
        Extract structured data using an LLM and a predefined schema.
        Invokes the prompt chain and parses the LLM output into JSON.
        """
        prompt = create_prompt()
        output_parser = StrOutputParser()
        chain = prompt | self.llm | output_parser
        result = chain.invoke({"content": content, "schema": schema})
        cleaned_result = re.sub(r"^```(?:json)?\n|\n```$", "", result.strip())
        try:
            parsed_result = json.loads(cleaned_result)
        except json.JSONDecodeError as e:
            print("Failed to parse result to JSON:", e)
            parsed_result = {"error": "Invalid JSON", "raw_result": cleaned_result}
        return parsed_result

    def process_invoice(self, image_bytes):
        """
        Complete processing pipeline for an invoice image.
        Loads text, builds schema, and returns extracted structured data.
        """
        content = self.load_image_content_from_bytes(image_bytes)
        schema = {
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
        return self.extract_data(content, schema)
