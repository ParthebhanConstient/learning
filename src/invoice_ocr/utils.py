import numpy as np
from langchain_core.prompts import PromptTemplate

def make_serializable(data):
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="ignore")
    elif isinstance(data, dict):
        return {k: make_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_serializable(v) for v in data]
    elif isinstance(data, (np.integer, np.floating)):
        return data.item()
    elif hasattr(data, "item"):
        try:
            return data.item()
        except Exception:
            return str(data)
    return data

def create_prompt():
    template = """
You are an AI assistant tasked with extracting structured information from invoice text.
Given the following content, extract the required fields and format them according to the provided schema.

if the key doesn't have any values add "N/A"

Content:
{content}

Schema:
{schema}

Please ensure the output strictly adheres to the schema format.
"""
    return PromptTemplate(input_variables=["content", "schema"], template=template)
