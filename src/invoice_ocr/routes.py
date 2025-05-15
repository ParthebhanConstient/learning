import json
from typing import List

import numpy as np
from fastapi import APIRouter, File, UploadFile

from  src.invoice_ocr.jpg_extraction import InvoiceProcessor
from  src.invoice_ocr.utils import make_serializable

router = APIRouter()
processor = InvoiceProcessor()

@router.post("/upload-invoices/")
async def upload_invoices(files: List[UploadFile] = File(...)):
    all_results = []

    for file in files:
        content = await file.read()
        result = processor.process_invoice(content)

        output = {"image": file.filename, "ground_truth": {"gt_parse": result}}

        with open("parsed_output.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(make_serializable(output), ensure_ascii=False) + "\n")

        all_results.append(output)

    return {
        "message": f"{len(files)} invoices processed.",
        "results": make_serializable(all_results),
    }
