from fastapi import FastAPI
from  src.invoice_ocr.routes import router

app = FastAPI()
app.include_router(router)
