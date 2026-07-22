import os
import io
import zipfile
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF
from pypdf import PdfReader, PdfWriter

app = FastAPI(
    title="PDF Auto Editor API - MyWebby Agency",
    description="Microservizio veloce e potente per la gestione automatica e conversione intelligente di PDF in Moduli Compilabili.",
    version="1.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
IMAGES_DIR = os.path.join(BASE_DIR, "images")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if os.path.exists(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

INDEX_HTML_PATH = os.path.join(STATIC_DIR, "index.html")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    
    cwd_static = os.path.join(os.getcwd(), "static", "index.html")
    if os.path.exists(cwd_static):
        with open(cwd_static, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    return HTMLResponse(content="<h1>MyWebby PDF Auto Editor</h1><p>index.html non trovato.</p>")


@app.get("/health")
async def health_check():
    return {"status": "ok", "agency": "MyWebby Agency", "service": "pdf-auto-editor", "version": "1.4.0"}


def process_single_pdf_to_fillable(content: bytes) -> tuple[bytes, int, int]:
    doc = fitz.open(stream=content, filetype="pdf")
    text_fields_count = 0
    checkboxes_count = 0

    for page_num, page in enumerate(doc):
        # A) Underscores -> Text Fields
        underscore_rects = page.search_for("___")
        merged_text_rects = []
        for rect in underscore_rects:
            if not merged_text_rects:
                merged_text_rects.append(rect)
            else:
                last = merged_text_rects[-1]
                if abs(last.y0 - rect.y0) < 4 and (rect.x0 - last.x1) < 15:
                    merged_text_rects[-1] = fitz.Rect(last.x0, min(last.y0, rect.y0), max(last.x1, rect.x1), max(last.y1, rect.y1))
                else:
                    merged_text_rects.append(rect)

        for i, rect in enumerate(merged_text_rects):
            text_fields_count += 1
            widget = fitz.Widget()
            widget.field_name = f"Campo_Testo_P{page_num + 1}_{i + 1}"
            widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
            field_rect = fitz.Rect(rect.x0, rect.y0 - 4, rect.x1, rect.y1 + 2)
            widget.rect = field_rect
            widget.border_color = (0.7, 0.7, 0.7)
            widget.border_width = 0.5
            widget.fill_color = (0.94, 0.97, 1.0)
            widget.text_color = (0, 0, 0)
            widget.text_fontsize = 10
            page.add_widget(widget)

        # B) Checkbox Symbols & Drawings -> Checkboxes
        checkbox_rects = []
        for symbol in ["☐", "□", "[ ]", "▫", "■"]:
            checkbox_rects.extend(page.search_for(symbol))

        drawings = page.get_drawings()
        for draw in drawings:
            for item in draw.get("items", []):
                if item[0] == "re":
                    r = item[1]
                    w, h = r.width, r.height
                    if 6 <= w <= 20 and 6 <= h <= 20 and abs(w - h) < 3:
                        checkbox_rects.append(r)

        unique_checkbox_rects = []
        for r in checkbox_rects:
            if not any(abs(u.x0 - r.x0) < 5 and abs(u.y0 - r.y0) < 5 for u in unique_checkbox_rects):
                unique_checkbox_rects.append(r)

        for j, rect in enumerate(unique_checkbox_rects):
            checkboxes_count += 1
            widget = fitz.Widget()
            widget.field_name = f"Spunta_P{page_num + 1}_{j + 1}"
            widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
            widget.rect = fitz.Rect(rect.x0 - 1, rect.y0 - 1, rect.x1 + 1, rect.y1 + 1)
            widget.border_color = (0.4, 0.4, 0.4)
            widget.border_width = 1
            widget.fill_color = (1.0, 1.0, 1.0)
            page.add_widget(widget)

    out_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return out_bytes, text_fields_count, checkboxes_count


@app.post("/api/make-fillable")
async def make_fillable_pdf(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Nessun file PDF caricato.")

    if len(files) == 1:
        file = files[0]
        content = await file.read()
        out_bytes, t_count, c_count = process_single_pdf_to_fillable(content)
        total_created = t_count + c_count
        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={file.filename.replace('.pdf', '')}_compilabile.pdf",
                "X-Text-Fields": str(t_count),
                "X-Checkboxes": str(c_count),
                "X-Fields-Created": str(total_created)
            }
        )

    zip_buffer = io.BytesIO()
    total_t = 0
    total_c = 0
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file in files:
            content = await file.read()
            out_bytes, t_c, c_c = process_single_pdf_to_fillable(content)
            total_t += t_c
            total_c += c_c
            zip_file.writestr(f"{file.filename.replace('.pdf', '')}_compilabile.pdf", out_bytes)

    zip_bytes = zip_buffer.getvalue()
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=moduli_compilabili_batch.zip",
            "X-Text-Fields": str(total_t),
            "X-Checkboxes": str(total_c),
            "X-Fields-Created": str(total_t + total_c)
        }
    )


# --- NUOVA FUNZIONE 1: DA PDF A IMMAGINI (PNG/JPG) ---
@app.post("/api/pdf-to-images")
async def pdf_to_images(file: UploadFile = File(...)):
    content = await file.read()
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        if len(doc) == 1:
            pix = doc[0].get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            doc.close()
            return Response(
                content=img_bytes,
                media_type="image/png",
                headers={"Content-Disposition": "attachment; filename=pagina_1.png"}
            )
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                zip_file.writestr(f"pagina_{i + 1}.png", img_bytes)
        
        doc.close()
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=pagine_pdf_immagini.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore conversione PDF a immagini: {str(e)}")


# --- NUOVA FUNZIONE 2: DA IMMAGINI (JPG/PNG) A PDF ---
@app.post("/api/images-to-pdf")
async def images_to_pdf(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Nessuna immagine caricata.")
    try:
        out_doc = fitz.open()
        for file in files:
            img_data = await file.read()
            img_doc = fitz.open(stream=img_data, filetype=file.filename.split('.')[-1].lower())
            pdf_bytes = img_doc.convert_to_pdf()
            img_doc.close()
            page_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            out_doc.insert_pdf(page_doc)
            page_doc.close()

        out_bytes = out_doc.tobytes(garbage=4, deflate=True)
        out_doc.close()
        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=immagini_convertite.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore conversione immagini a PDF: {str(e)}")


# --- NUOVA FUNZIONE 3: APPLICA FIRMA O TIMBRO SU PDF ---
@app.post("/api/add-signature")
async def add_signature(
    file: UploadFile = File(...),
    signature: UploadFile = File(...),
    page_num: int = Form(1),
    position: str = Form("bottom-right")
):
    pdf_content = await file.read()
    sig_content = await signature.read()
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        target_page_idx = min(max(0, page_num - 1), len(doc) - 1)
        page = doc[target_page_idx]
        rect = page.rect

        sig_w, sig_h = 160, 60
        if position == "bottom-right":
            sig_rect = fitz.Rect(rect.width - sig_w - 30, rect.height - sig_h - 30, rect.width - 30, rect.height - 30)
        elif position == "bottom-left":
            sig_rect = fitz.Rect(30, rect.height - sig_h - 30, 30 + sig_w, rect.height - 30)
        elif position == "bottom-center":
            sig_rect = fitz.Rect((rect.width - sig_w) / 2, rect.height - sig_h - 30, (rect.width + sig_w) / 2, rect.height - 30)
        else:
            sig_rect = fitz.Rect((rect.width - sig_w) / 2, (rect.height - sig_h) / 2, (rect.width + sig_w) / 2, (rect.height + sig_h) / 2)

        page.insert_image(sig_rect, stream=sig_content)
        out_bytes = doc.tobytes(garbage=4, deflate=True)
        doc.close()
        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=pdf_firmato.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore inserimento firma: {str(e)}")


# --- NUOVA FUNZIONE 4: ELIMINA PAGINE DA PDF ---
@app.post("/api/delete-pages")
async def delete_pages(file: UploadFile = File(...), pages_to_delete: str = Form(...)):
    content = await file.read()
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        total_pages = len(doc)
        
        pages_to_remove = set()
        for part in pages_to_delete.split(","):
            part = part.strip()
            if part.isdigit():
                p = int(part)
                if 1 <= p <= total_pages:
                    pages_to_remove.add(p - 1)

        sorted_pages = sorted(list(pages_to_remove), reverse=True)
        for idx in sorted_pages:
            doc.delete_page(idx)

        out_bytes = doc.tobytes(garbage=4, deflate=True)
        doc.close()
        return Response(
            content=out_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=pdf_modificato.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore eliminazione pagine: {str(e)}")


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
            headers={"Content-Disposition": "attachment; filename=pdf_unito.pdf"}
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
