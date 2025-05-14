import pytesseract
from PIL import Image
import re
import json
import os

# Input image path
image_path = r"C:\Users\Parthebhan\Documents\dataset\downloaded_dataset\images\image_0150.jpg"
image = Image.open(image_path)
text = pytesseract.image_to_string(image)

# Normalize text
text = re.sub(r'\n+', '\n', text).strip()

# Helper function to extract with regex fallback
def extract(pattern, text, group=1):
    match = re.search(pattern, text)
    return match.group(group).strip() if match else ""

# Extract header information
invoice_no = extract(r"Invoice no[:\s]*([0-9]+)", text)
invoice_date = extract(r"Date of issue[:\s]*([0-9/]+)", text)
iban = extract(r"IBAN[:\s]*(GB[0-9A-Z]+)", text)

# Extract seller and client blocks
seller_match = re.search(r"Seller:\s*(.*?)\s*Tax Id:", text, re.DOTALL)
seller_text = seller_match.group(1).replace('\n', ' ').strip() if seller_match else ""

client_match = re.search(r"Client:\s*(.*?)\s*Tax Id:", text, re.DOTALL)
client_text = client_match.group(1).replace('\n', ' ').strip() if client_match else ""

# Extract tax IDs
seller_tax_id = extract(r"Tax Id[:\s]*([0-9\-]+)", text.split("Client:")[0])
client_tax_id = extract(r"Tax Id[:\s]*([0-9\-]+)", text.split("Client:")[1])

# Extract item lines between "ITEMS" and "SUMMARY"
lines = text.split('\n')
item_lines = []
inside_items = False

for line in lines:
    if "ITEMS" in line:
        inside_items = True
    elif "SUMMARY" in line:
        break
    elif inside_items and re.search(r"^\s*\d+\.", line):  # starts with numbered item
        item_lines.append(line)
    elif inside_items and len(item_lines) > 0:
        # continuation of previous item line
        item_lines[-1] += " " + line.strip()

# Parse item lines with better pattern matching
items = []
for line in item_lines:
    # Extract numeric values from the end of the line
    number_matches = re.findall(r"\d{1,3}(?:,\d{2})", line)

    # Assume the last three numbers are: net_worth, VAT (if any), gross_worth
    if len(number_matches) >= 3:
        gross_worth = number_matches[-1]
        net_worth = number_matches[-2]
        net_price = number_matches[-3]
        quantity = number_matches[-4] if len(number_matches) >= 4 else ""

        # Remove the number portion from description
        desc = re.sub(r"[\d]{1,3},\d{2}", "", line)
        desc = re.sub(r"^\d+\.\s*", "", desc).strip()
        desc = re.sub(r"\s+", " ", desc).strip()

        items.append({
            "item_desc": desc,
            "item_qty": quantity,
            "item_net_price": net_price,
            "item_net_worth": net_worth,
            "item_vat": "10%",
            "item_gross_worth": gross_worth
        })
    else:
        # Fallback: unknown format
        items.append({
            "item_desc": line.strip(),
            "item_qty": "",
            "item_net_price": "",
            "item_net_worth": "",
            "item_vat": "10%",
            "item_gross_worth": ""
        })


# Extract summary section
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

# Final JSON structure
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

# Output result
print(json.dumps(result, indent=2, ensure_ascii=False))
