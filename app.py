from src.invoice_ocr.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.invoice_ocr.main:app", host="0.0.0.0", port=8000, reload=False)
