import pytesseract
from PIL import Image as PILImage, ImageEnhance
import re
import json
import os
from img2table.ocr import TesseractOCR
from img2table.document import Image as Img2TableImage

# ==== Image Path ====
image_path = r"C:\Users\Parthebhan\Documents\dataset\downloaded_dataset\images\image_0150.jpg"

# ==== Image Preprocessing ====
image = PILImage.open(image_path).convert("L")
image = image.resize((image.width * 2, image.height * 2))  # Upscale
image = ImageEnhance.Contrast(image).enhance(2)

# ==== pytesseract for header text ====
text = pytesseract.image_to_string(image)
text = re.sub(r'\n+', '\n', text).strip()

print("---------Start text-------")
print(text)
print("---------End text-------")

# ==== Helper function ====
def extract(pattern, text, group=1):
    match = re.search(pattern, text)
    return match.group(group).strip() if match else ""

# ==== Header fields ====
invoice_no = extract(r"Invoice no[:\s]*([0-9]+)", text)
invoice_date = extract(r"date\s*of\s*issue[:\s]*([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{4})", text.lower())
if not invoice_date:
    invoice_date = extract(r"\b([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{4})\b", text)

iban = extract(r"IBAN[:\s]*(GB[0-9A-Z]+)", text)

# ==== Seller and Client ====
seller_match = re.search(r"Seller:\s*(.*?)\s*Tax Id:", text, re.DOTALL)
seller_text = seller_match.group(1).replace('\n', ' ').strip() if seller_match else ""

client_match = re.search(r"Client:\s*(.*?)\s*Tax Id:", text, re.DOTALL)
client_text = client_match.group(1).replace('\n', ' ').strip() if client_match else ""

seller_tax_id = extract(r"Tax Id[:\s]*([0-9\-]+)", text.split("Client:")[0]) if "Client:" in text else ""
client_tax_id = extract(r"Tax Id[:\s]*([0-9\-]+)", text.split("Client:")[1]) if "Client:" in text else ""

# ==== img2table for item table ====
ocr = TesseractOCR(n_threads=1, lang="eng")
doc = Img2TableImage(image_path)

extracted_tables = doc.extract_tables(
    ocr=ocr,
    implicit_rows=True,
    borderless_tables=True,
    min_confidence=50
)

items = []
if extracted_tables:
    table = extracted_tables[0]
    rows = list(table.content.values())

    if rows:
        headers = [cell.value.lower().strip() if cell.value else "" for cell in rows[0]]

        desc_idx = headers.index("description") if "description" in headers else 0
        qty_idx = headers.index("qty") if "qty" in headers else 1
        net_price_idx = headers.index("net price") if "net price" in headers else 2
        net_worth_idx = headers.index("net worth") if "net worth" in headers else 3
        vat_idx = headers.index("vat [%]") if "vat [%]" in headers else 4
        gross_idx = headers.index("gross worth") if "gross worth" in headers else 5

        merged_items = []
        current_item = {}

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

            is_new_row = qty.replace(',', '').replace('.', '').isdigit() and net_price.replace(',', '').replace('.', '').isdigit()

            if is_new_row:
                if current_item:
                    merged_items.append(current_item)

                try:
                    vat_rate = float(vat.replace('%', '').strip()) / 100
                except:
                    vat_rate = 0.1

                try:
                    net_worth_val = float(net_worth.replace(',', '.'))
                    gross_worth_val = round(net_worth_val * (1 + vat_rate), 2)
                except:
                    net_worth_val = 0.0
                    gross_worth_val = 0.0

                current_item = {
                    "item_desc": desc,
                    "item_qty": qty,
                    "item_net_price": net_price,
                    "item_net_worth": net_worth,
                    "item_vat": f"{int(vat_rate * 100)}%",
                    "item_gross_worth": gross if gross else f"{gross_worth_val:.2f}".replace('.', ',')
                }

            else:
                if current_item:
                    current_item["item_desc"] += " " + desc

        if current_item:
            merged_items.append(current_item)

        items = merged_items

# ==== Summary Fields ====
summary_match = re.search(
    r"Net worth\s+(\d{1,3},\d{2})\s+VAT\s+(\d{1,3},\d{2}).*?Gross worth\s+(\d{1,3},\d{2})",
    text, re.DOTALL
)
if not summary_match:
    summary_match = re.search(
        r"\$?\s*(\d{1,3},\d{2})\s+\$?\s*(\d{1,3},\d{2})\s+\$?\s*(\d{1,3},\d{2})", text
    )

summary = {
    "total_net_worth": f"${summary_match.group(1)}" if summary_match else "",
    "total_vat": f"${summary_match.group(2)}" if summary_match else "",
    "total_gross_worth": f"$ {summary_match.group(3)}" if summary_match else ""
}

# ==== Final JSON Output ====
result = {
    "image": os.path.basename(image_path),
    "ground_truth": {
        "gt_parse": {
            "header": {
                "invoice_no": invoice_no,
                "invoice_date": invoice_date,
                "seller": seller_text,
                "client": client_text,
                "seller_tax_id": seller_tax_id,
                "client_tax_id": client_tax_id,
                "iban": iban
            },
            "items": items,
            "summary": summary
        }
    }
}

# ==== Output to Console ====
print(json.dumps(result, indent=2, ensure_ascii=False))
