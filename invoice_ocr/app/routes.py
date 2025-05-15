import json
from typing import List

import numpy as np
from fastapi import APIRouter, File, UploadFile

from .ocr_utils import process_invoice

router = APIRouter()


def make_serializable(data):
    """Recursively make data JSON serializable."""
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

@router.post("/upload-invoices/")
async def upload_invoices(files: List[UploadFile] = File(...)):
    all_results = []

    for file in files:
        content = await file.read()
        result = process_invoice(content)

        output = {"image": file.filename, "ground_truth": {"gt_parse": result}}       

        # Save each result to the JSONL file
        with open("parsed_output.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(make_serializable(output), ensure_ascii=False) + "\n")

        all_results.append(output)

    return {
        "message": f"{len(files)} invoices processed.",
        "results": make_serializable(all_results),  
    }
