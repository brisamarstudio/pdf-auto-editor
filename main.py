import os
import io
import zipfile
import base64
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF
from pypdf import PdfReader, PdfWriter

app = FastAPI(
    title="PDF Auto Editor API",
    description="Microservizio veloce e potente per elaborazione e modifica automatica di PDF.",
    version="1.0.0"
)

# Enable CORS for external API integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return HTMLResponse("<h2>PDF Auto Editor API is running!</h2>")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "pdf-auto-editor", "version": "1.0.0"}


@app.post("/api/merge")
async def merge_pdfs(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Fornire almeno 2 file PDF per l'unione.")
    
    merged_doc = fitz.open()
    try:
        for file in files:
            content = await file.read()
            src_doc = fitz.open(stream=content, filetype="pdf")
            merged_doc.insert_pdf(src_doc)
            src_doc.close()
            
        out_bytes = merged_doc.tobytes(garbage=4, deflate=True)
        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=merged.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'unione: {str(e)}")
    finally:
        merged_doc.close()


@app.post("/api/split")
async def split_pdf(file: UploadFile = File(...), pages: Optional[str] = Form(None)):
    content = await file.read()
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        total_pages = len(doc)
        
        selected_indices = []
        if pages and pages.strip():
            parts = pages.split(",")
            for part in parts:
                part = part.strip()
                if "-" in part:
                    start_str, end_str = part.split("-")
                    s = max(1, int(start_str))
                    e = min(total_pages, int(end_str))
                    selected_indices.extend(range(s - 1, e))
                else:
                    p = int(part)
                    if 1 <= p <= total_pages:
                        selected_indices.append(p - 1)
        else:
            selected_indices = list(range(total_pages))

        selected_indices = sorted(list(set(selected_indices)))

        if not selected_indices:
            raise HTTPException(status_code=400, detail="Nessuna pagina valida selezionata.")

        new_doc = fitz.open()
        for idx in selected_indices:
            new_doc.insert_pdf(doc, from_page=idx, to_page=idx)
            
        out_bytes = new_doc.tobytes(garbage=4, deflate=True)
        new_doc.close()
        doc.close()

        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=split_extracted.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante la divisione: {str(e)}")


@app.post("/api/rotate")
async def rotate_pdf(file: UploadFile = File(...), angle: int = Form(90)):
    content = await file.read()
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        for page in doc:
            page.set_rotation((page.rotation + angle) % 360)
            
        out_bytes = doc.tobytes(garbage=4, deflate=True)
        doc.close()

        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=rotated.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante la rotazione: {str(e)}")


@app.post("/api/compress")
async def compress_pdf(file: UploadFile = File(...)):
    content = await file.read()
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        out_bytes = doc.tobytes(garbage=4, deflate=True, clean=True)
        doc.close()

        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=compressed.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante la compressione: {str(e)}")


@app.post("/api/watermark")
async def watermark_pdf(file: UploadFile = File(...), text: str = Form("RISERVATO")):
    content = await file.read()
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        for page in doc:
            rect = page.rect
            point = fitz.Point(rect.width / 4, rect.height / 2)
            page.insert_text(
                point,
                text,
                fontsize=48,
                color=(0.7, 0.7, 0.7),
                rotate=45,
                overlay=True
            )
            
        out_bytes = doc.tobytes(garbage=4, deflate=True)
        doc.close()

        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=watermarked.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore applicazione filigrana: {str(e)}")


@app.post("/api/extract-text")
async def extract_text(file: UploadFile = File(...)):
    content = await file.read()
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        full_text = []
        for i, page in enumerate(doc):
            full_text.append(f"--- PAGINA {i + 1} ---\n")
            full_text.append(page.get_text())
            full_text.append("\n\n")
            
        doc.close()
        text_output = "".join(full_text)

        return Response(
            content=text_output.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=extracted_text.txt"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore estrazione testo: {str(e)}")


@app.post("/api/protect")
async def protect_pdf(file: UploadFile = File(...), password: str = Form(...)):
    content = await file.read()
    try:
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(user_password=password, owner_password=password)

        out_stream = io.BytesIO()
        writer.write(out_stream)
        out_bytes = out_stream.getvalue()

        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=protected.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante protezione: {str(e)}")


@app.post("/api/render-preview")
async def render_preview(file: UploadFile = File(...)):
    content = await file.read()
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        pages_b64 = []
        max_preview_pages = min(len(doc), 10)
        
        for i in range(max_preview_pages):
            page = doc[i]
            pix = page.get_pixmap(dpi=72)
            img_bytes = pix.tobytes("png")
            b64_str = base64.b64encode(img_bytes).decode("utf-8")
            pages_b64.append(b64_str)
            
        doc.close()
        return {"pages": pages_b64, "total_pages": len(doc)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore generazione anteprima: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
