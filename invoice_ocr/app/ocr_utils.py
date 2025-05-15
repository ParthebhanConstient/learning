import io
import os
import re

import pytesseract
from img2table.document import Image as Img2TableImage
from img2table.ocr import TesseractOCR
from PIL import Image as PILImage
from PIL import ImageEnhance


def extract(pattern, text, group=1):
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(group).strip() if match else ""


def find_bounding_box(word, data):
    for i, text in enumerate(data["text"]):
        if text.strip().lower() == word.strip().lower():
            return {
                "page": 1,
                "x": int(data["left"][i]),
                "y": int(data["top"][i]),
                "width": int(data["width"][i]),
                "height": int(data["height"][i]),
            }
    return None


def process_invoice(file):
    image = PILImage.open(io.BytesIO(file)).convert("L")
    image = image.resize((image.width * 2, image.height * 2))
    image = ImageEnhance.Contrast(image).enhance(2)

    # Get OCR text and positional data
    text = pytesseract.image_to_string(image)
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    text = re.sub(r"\n+", "\n", text).strip()

    invoice_no = extract(r"Invoice no[:\s]*([0-9]+)", text)
    invoice_date = extract(
        r"date\s*of\s*issue[:\s]*([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{4})", text.lower()
    )
    if not invoice_date:
        invoice_date = extract(r"\b([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{4})\b", text)
    iban = extract(r"IBAN[:\s]*(GB[0-9A-Z]+)", text)

    seller_text = extract(r"Seller:?\s*(.*?)\s+(?=Client:|Tax Id:)", text)
    client_text = extract(r"Client:?\s*(.*?)(?=\s+Tax Id:|$)", text)
    seller_text = seller_text.replace("\n", " ").strip()
    client_text = client_text.replace("\n", " ").strip()

    seller_tax_id = extract(r"Seller:.*?Tax Id[:\s]*([0-9\-]+)", text)
    client_tax_id = extract(r"Client:.*?Tax Id[:\s]*([0-9\-]+)", text)

    # Build labeled fields with positions
    labeled_fields = []
    for label, value in [
        ("Invoice Number", invoice_no),
        ("Invoice Date", invoice_date),
        ("Seller Name", seller_text),
        ("Buyer Name", client_text),
        ("Seller Tax ID", seller_tax_id),
        ("Client Tax ID", client_tax_id),
        ("IBAN", iban),
    ]:
        if value:
            box = find_bounding_box(value.split()[0], data)
            if box:
                labeled_fields.append({"label": label, "value": value, "position": box})

    # Table extraction
    temp_file_path = "temp_invoice.jpg"
    with open(temp_file_path, "wb") as f:
        f.write(file)

    ocr = TesseractOCR(n_threads=1, lang="eng")
    doc = Img2TableImage(temp_file_path)
    extracted_tables = doc.extract_tables(
        ocr=ocr, implicit_rows=True, borderless_tables=True, min_confidence=50
    )
    os.remove(temp_file_path)

    items = []
    table_box = None
    if extracted_tables:
        table = extracted_tables[0]
        table_box = {
            "page": 1,
            "table_region": {
                "x": table.bbox.x1,
                "y": table.bbox.y1,
                "width": table.bbox.x2 - table.bbox.x1,
                "height": table.bbox.y2 - table.bbox.y1,
            },
        }
        rows = list(table.content.values())
        if rows:
            headers = [c.value.lower().strip() if c.value else "" for c in rows[0]]

            def find_idx(keyword, default=0):
                for i, h in enumerate(headers):
                    if keyword in h:
                        return i
                return default

            desc_idx = find_idx("description", 0)
            qty_idx = find_idx("qty", 1)
            net_price_idx = find_idx("net price", 2)
            net_worth_idx = find_idx("net worth", 3)
            vat_idx = find_idx("vat", 4)
            gross_idx = find_idx("gross", 5)

            merged_items, current_item = [], {}
            for row in rows[1:]:
                cells = [cell.value.strip() if cell.value else "" for cell in row]
                if len(cells) < 3:
                    continue

                desc = cells[desc_idx] if desc_idx < len(cells) else ""
                qty = cells[qty_idx] if qty_idx < len(cells) else ""
                net_price = cells[net_price_idx] if net_price_idx < len(cells) else ""
                net_worth = cells[net_worth_idx] if net_worth_idx < len(cells) else ""
                vat = cells[vat_idx] if vat_idx < len(cells) else ""
                gross = cells[gross_idx] if gross_idx < len(cells) else ""

                valid_qty = re.match(r"^\d+([.,]\d+)?$", qty)
                valid_net = re.match(r"^\d+([.,]\d+)?$", net_price)
                is_new_row = bool(valid_qty and valid_net)

                if is_new_row:
                    if current_item:
                        merged_items.append(current_item)
                    try:
                        vat_rate = (
                            float(re.findall(r"\d+", vat)[0]) / 100 if vat else 0.1
                        )
                    except:
                        vat_rate = 0.1
                    try:
                        net_worth_val = float(net_worth.replace(",", "."))
                        gross_calc = round(net_worth_val * (1 + vat_rate), 2)
                    except:
                        gross_calc = 0.0

                    current_item = {
                        "item_desc": desc,
                        "item_qty": qty,
                        "item_net_price": net_price,
                        "item_net_worth": net_worth,
                        "item_vat": f"{int(vat_rate * 100)}%",
                        "item_gross_worth": gross
                        if gross
                        else f"{gross_calc:.2f}".replace(".", ","),
                    }
                else:
                    if current_item:
                        current_item["item_desc"] += " " + desc

            if current_item:
                merged_items.append(current_item)
            items = merged_items

    summary_match = re.search(
        r"Net worth\s+(\d{1,3},\d{2})\s+VAT\s+(\d{1,3},\d{2}).*?Gross worth\s+(\d{1,3},\d{2})",
        text,
        re.DOTALL,
    )
    if not summary_match:
        summary_match = re.search(
            r"\$?\s*(\d{1,3},\d{2})\s+\$?\s*(\d{1,3},\d{2})\s+\$?\s*(\d{1,3},\d{2})",
            text,
        )

    summary = {
        "total_net_worth": f"${summary_match.group(1)}" if summary_match else "",
        "total_vat": f"${summary_match.group(2)}" if summary_match else "",
        "total_gross_worth": f"$ {summary_match.group(3)}" if summary_match else "",
    }

    if summary_match:
        for label, val in [
            ("Tax Amount", summary["total_vat"]),
            ("Total Amount", summary["total_gross_worth"]),
        ]:
            box = find_bounding_box(val.replace("$", "").strip(), data)
            if box:
                labeled_fields.append({"label": label, "value": val, "position": box})

    if table_box:
        labeled_fields.append({"label": "Items", "value": items, "position": table_box})

    return {
        "image": file[:5],
        "results_with_positions": labeled_fields,
        "extracted": {
            "gt_parse": {
                "header": {
                    "invoice_no": invoice_no,
                    "invoice_date": invoice_date,
                    "seller": seller_text,
                    "client": client_text,
                    "seller_tax_id": seller_tax_id,
                    "client_tax_id": client_tax_id,
                    "iban": iban,
                },
                "items": items,
                "summary": summary,
            }
        },
    }
