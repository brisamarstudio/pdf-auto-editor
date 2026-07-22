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

INDEX_HTML_PATH = os.path.join(STATIC_DIR, "index.html")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    # Try reading static/index.html first
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    
    # Also check current working directory static/index.html
    cwd_static = os.path.join(os.getcwd(), "static", "index.html")
    if os.path.exists(cwd_static):
        with open(cwd_static, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    # Fallback to embedded HTML
    return HTMLResponse(content=HTML_EMBEDDED)


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


HTML_EMBEDDED = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Auto Editor - Tool Gratuito Online per Modificare PDF</title>
    <meta name="description" content="Modifica, unisci, dividi, ruota, comprimi ed estrai testo dai tuoi PDF in modo veloce, sicuro e gratuito.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-dark: #0A0D14;
            --card-bg: rgba(18, 24, 38, 0.75);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent-primary: #6366F1;
            --accent-glow: rgba(99, 102, 241, 0.35);
            --accent-secondary: #8B5CF6;
            --accent-pink: #EC4899;
            --accent-emerald: #10B981;
            --text-main: #F3F4F6;
            --text-muted: #9CA3AF;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }

        body {
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(at 10% 10%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
                radial-gradient(at 90% 90%, rgba(236, 72, 153, 0.12) 0px, transparent 50%),
                radial-gradient(at 50% 50%, rgba(139, 92, 246, 0.1) 0px, transparent 50%);
            background-attachment: fixed;
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        header {
            border-bottom: 1px solid var(--card-border);
            backdrop-filter: blur(16px);
            background: rgba(10, 13, 20, 0.7);
            position: sticky;
            top: 0;
            z-index: 50;
        }

        .navbar {
            max-width: 1200px;
            margin: 0 auto;
            padding: 1rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 1.4rem;
            background: linear-gradient(135deg, #A5B4FC, #6366F1, #EC4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-decoration: none;
        }

        .logo-icon {
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-pink));
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.1rem;
            box-shadow: 0 4px 15px var(--accent-glow);
        }

        .badge-render {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34D399;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        .badge-pulse {
            width: 8px;
            height: 8px;
            background-color: #10B981;
            border-radius: 50%;
            box-shadow: 0 0 8px #10B981;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        main { flex: 1; max-width: 1200px; width: 100%; margin: 0 auto; padding: 2.5rem 1.5rem; }

        .hero { text-align: center; margin-bottom: 2.5rem; }
        .hero h1 { font-family: 'Outfit', sans-serif; font-size: 2.8rem; font-weight: 700; margin-bottom: 0.75rem; line-height: 1.2; }
        .hero p { color: var(--text-muted); font-size: 1.1rem; max-width: 650px; margin: 0 auto; }

        .tabs-container { display: flex; justify-content: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 2rem; }
        .tab-btn {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--card-border);
            color: var(--text-muted);
            padding: 0.75rem 1.25rem;
            border-radius: 12px;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.25s ease;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .tab-btn:hover { background: rgba(255, 255, 255, 0.07); color: var(--text-main); border-color: rgba(255, 255, 255, 0.15); }
        .tab-btn.active {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(139, 92, 246, 0.2));
            border-color: var(--accent-primary);
            color: white;
            box-shadow: 0 4px 20px var(--accent-glow);
        }

        .workspace-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 24px;
            backdrop-filter: blur(20px);
            padding: 2rem;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            margin-bottom: 3rem;
        }

        .dropzone {
            border: 2px dashed rgba(99, 102, 241, 0.4);
            border-radius: 16px;
            padding: 3.5rem 2rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: rgba(99, 102, 241, 0.03);
            position: relative;
        }
        .dropzone:hover, .dropzone.dragover {
            border-color: var(--accent-primary);
            background: rgba(99, 102, 241, 0.08);
            transform: translateY(-2px);
        }
        .dropzone-icon { font-size: 3rem; color: var(--accent-primary); margin-bottom: 1rem; }
        .file-input { display: none; }

        .tool-panel { display: none; margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid var(--card-border); }
        .tool-panel.active { display: block; animation: fadeIn 0.3s ease forwards; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        .form-group { margin-bottom: 1.25rem; }
        .form-label { display: block; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.5rem; color: #D1D5DB; }
        .form-control {
            width: 100%;
            padding: 0.75rem 1rem;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            color: white;
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.2s ease;
        }
        .form-control:focus { border-color: var(--accent-primary); }

        .btn-action {
            width: 100%;
            padding: 1rem;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            border: none;
            border-radius: 12px;
            color: white;
            font-weight: 700;
            font-size: 1.05rem;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px var(--accent-glow);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }
        .btn-action:hover { opacity: 0.95; transform: translateY(-2px); box-shadow: 0 6px 25px var(--accent-glow); }
        .btn-action:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        .file-list { margin-top: 1.5rem; display: flex; flex-direction: column; gap: 0.75rem; }
        .file-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: rgba(0, 0, 0, 0.25);
            border: 1px solid var(--card-border);
            padding: 0.85rem 1.25rem;
            border-radius: 12px;
        }
        .file-info { display: flex; align-items: center; gap: 0.75rem; }
        .file-name { font-weight: 600; font-size: 0.95rem; }
        .file-size { color: var(--text-muted); font-size: 0.8rem; }
        .btn-remove { background: transparent; border: none; color: #EF4444; cursor: pointer; font-size: 1.1rem; padding: 0.4rem; border-radius: 6px; }
        .btn-remove:hover { background: rgba(239, 68, 68, 0.15); }

        .result-box {
            display: none;
            margin-top: 1.5rem;
            padding: 1.5rem;
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 16px;
            text-align: center;
        }
        .result-box.active { display: block; animation: fadeIn 0.3s ease forwards; }

        .btn-download {
            background: linear-gradient(135deg, #10B981, #059669);
            color: white;
            padding: 0.85rem 1.75rem;
            border-radius: 12px;
            text-decoration: none;
            font-weight: 700;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 1rem;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
            transition: all 0.25s ease;
        }
        .btn-download:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4); }

        .spinner {
            display: none;
            width: 24px;
            height: 24px;
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        footer { border-top: 1px solid var(--card-border); text-align: center; padding: 1.5rem; color: var(--text-muted); font-size: 0.9rem; }
    </style>
</head>
<body>
    <header>
        <div class="navbar">
            <a href="#" class="logo">
                <div class="logo-icon"><i class="fa-solid fa-file-pdf"></i></div>
                <span>PDF Auto Editor</span>
            </a>
            <div class="badge-render">
                <div class="badge-pulse"></div>
                Online su Render.com
            </div>
        </div>
    </header>

    <main>
        <section class="hero">
            <h1>Modifica i tuoi PDF con facilità 🚀</h1>
            <p>Unisci, dividi, ruota, comprimi e proteggi i tuoi file in pochi secondi. 100% gratuito e sicuro.</p>
        </section>

        <div class="tabs-container">
            <button class="tab-btn active" onclick="switchTool('merge')"><i class="fa-solid fa-object-group"></i> Unisci PDF</button>
            <button class="tab-btn" onclick="switchTool('split')"><i class="fa-solid fa-scissors"></i> Dividi Pagine</button>
            <button class="tab-btn" onclick="switchTool('rotate')"><i class="fa-solid fa-rotate-right"></i> Ruota Pagine</button>
            <button class="tab-btn" onclick="switchTool('compress')"><i class="fa-solid fa-file-contract"></i> Comprimi</button>
            <button class="tab-btn" onclick="switchTool('watermark')"><i class="fa-solid fa-stamp"></i> Filigrana</button>
            <button class="tab-btn" onclick="switchTool('extract')"><i class="fa-solid fa-file-lines"></i> Estrai Testo</button>
            <button class="tab-btn" onclick="switchTool('protect')"><i class="fa-solid fa-lock"></i> Proteggi</button>
        </div>

        <div class="workspace-card">
            <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
                <div class="dropzone-icon"><i class="fa-solid fa-cloud-arrow-up"></i></div>
                <h3 style="margin-bottom: 0.5rem; font-size: 1.2rem;">Trascina qui i tuoi file PDF</h3>
                <p style="color: var(--text-muted); font-size: 0.9rem;">oppure clicca per selezionare dal tuo computer</p>
                <input type="file" id="fileInput" class="file-input" accept=".pdf" multiple onchange="handleFileSelect(event)">
            </div>

            <div class="file-list" id="fileList"></div>

            <div class="tool-panel active" id="panel-merge">
                <p style="color: var(--text-muted); margin-bottom: 1rem; font-size: 0.9rem;">Seleziona 2 o più file PDF per unirli in un unico documento.</p>
                <button class="btn-action" id="btn-merge" onclick="executeMerge()" disabled>
                    <div class="spinner" id="spinner-merge"></div> <i class="fa-solid fa-object-group"></i> Unisci PDF Ora
                </button>
            </div>

            <div class="tool-panel" id="panel-split">
                <div class="form-group">
                    <label class="form-label">Intervallo di Pagine (es. 1-3, 5, 8-10):</label>
                    <input type="text" id="split-pages" class="form-control" placeholder="Lascia vuoto per estrarre tutte le pagine">
                </div>
                <button class="btn-action" id="btn-split" onclick="executeSplit()" disabled>
                    <div class="spinner" id="spinner-split"></div> <i class="fa-solid fa-scissors"></i> Dividi PDF Ora
                </button>
            </div>

            <div class="tool-panel" id="panel-rotate">
                <div class="form-group">
                    <label class="form-label">Angolo di Rotazione:</label>
                    <select id="rotate-angle" class="form-control">
                        <option value="90">90° in senso orario</option>
                        <option value="180">180° Capovolto</option>
                        <option value="270">270° in senso antiorario</option>
                    </select>
                </div>
                <button class="btn-action" id="btn-rotate" onclick="executeRotate()" disabled>
                    <div class="spinner" id="spinner-rotate"></div> <i class="fa-solid fa-rotate-right"></i> Ruota PDF Ora
                </button>
            </div>

            <div class="tool-panel" id="panel-compress">
                <p style="color: var(--text-muted); margin-bottom: 1rem; font-size: 0.9rem;">Riduce le dimensioni del file ottimizzando il documento.</p>
                <button class="btn-action" id="btn-compress" onclick="executeCompress()" disabled>
                    <div class="spinner" id="spinner-compress"></div> <i class="fa-solid fa-file-contract"></i> Comprimi PDF Ora
                </button>
            </div>

            <div class="tool-panel" id="panel-watermark">
                <div class="form-group">
                    <label class="form-label">Testo Filigrana:</label>
                    <input type="text" id="watermark-text" class="form-control" value="RISERVATO">
                </div>
                <button class="btn-action" id="btn-watermark" onclick="executeWatermark()" disabled>
                    <div class="spinner" id="spinner-watermark"></div> <i class="fa-solid fa-stamp"></i> Applica Filigrana
                </button>
            </div>

            <div class="tool-panel" id="panel-extract">
                <p style="color: var(--text-muted); margin-bottom: 1rem; font-size: 0.9rem;">Estrai tutto il testo contenuto nel PDF in formato TXT pulito.</p>
                <button class="btn-action" id="btn-extract" onclick="executeExtractText()" disabled>
                    <div class="spinner" id="spinner-extract"></div> <i class="fa-solid fa-file-lines"></i> Estrai Testo Ora
                </button>
            </div>

            <div class="tool-panel" id="panel-protect">
                <div class="form-group">
                    <label class="form-label">Password di Protezione:</label>
                    <input type="password" id="protect-password" class="form-control" placeholder="Inserisci una password sicura">
                </div>
                <button class="btn-action" id="btn-protect" onclick="executeProtect()" disabled>
                    <div class="spinner" id="spinner-protect"></div> <i class="fa-solid fa-lock"></i> Proteggi PDF con Password
                </button>
            </div>

            <div class="result-box" id="resultBox">
                <i class="fa-solid fa-circle-check" style="font-size: 2.5rem; color: #10B981; margin-bottom: 0.5rem;"></i>
                <h3 style="font-size: 1.25rem;">Operazione Completata con Successo!</h3>
                <p style="color: var(--text-muted); font-size: 0.9rem; margin-top: 0.25rem;">Il tuo nuovo file è pronto.</p>
                <a href="#" id="downloadLink" class="btn-download" download><i class="fa-solid fa-download"></i> Scarica File Elaborato</a>
            </div>
        </div>
    </main>

    <footer>
        <p>PDF Auto Editor • Powered by Python 3 & FastAPI • Online su Render.com 🚀</p>
    </footer>

    <script>
        let selectedFiles = [];
        let currentTool = 'merge';

        const dropzone = document.getElementById('dropzone');
        ['dragenter', 'dragover'].forEach(eName => dropzone.addEventListener(eName, (e) => { e.preventDefault(); dropzone.classList.add('dragover'); }, false));
        ['dragleave', 'drop'].forEach(eName => dropzone.addEventListener(eName, (e) => { e.preventDefault(); dropzone.classList.remove('dragover'); }, false));
        dropzone.addEventListener('drop', (e) => handleFiles(e.dataTransfer.files));

        function handleFileSelect(e) { handleFiles(e.target.files); }

        function handleFiles(files) {
            for (let i = 0; i < files.length; i++) {
                if (files[i].type === 'application/pdf') selectedFiles.push(files[i]);
            }
            renderFileList();
            updateButtonStates();
        }

        function renderFileList() {
            const listEl = document.getElementById('fileList');
            listEl.innerHTML = '';
            selectedFiles.forEach((file, idx) => {
                const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
                listEl.innerHTML += `
                    <div class="file-item">
                        <div class="file-info">
                            <i class="fa-solid fa-file-pdf" style="color: #6366F1; font-size: 1.3rem;"></i>
                            <div>
                                <div class="file-name">${file.name}</div>
                                <div class="file-size">${sizeMb} MB</div>
                            </div>
                        </div>
                        <button class="btn-remove" onclick="removeFile(${idx})"><i class="fa-solid fa-trash-can"></i></button>
                    </div>
                `;
            });
        }

        function removeFile(index) {
            selectedFiles.splice(index, 1);
            renderFileList();
            updateButtonStates();
        }

        function switchTool(tool) {
            currentTool = tool;
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tool-panel').forEach(panel => panel.classList.remove('active'));
            event.currentTarget.classList.add('active');
            document.getElementById(`panel-${tool}`).classList.add('active');
            document.getElementById('resultBox').classList.remove('active');
            updateButtonStates();
        }

        function updateButtonStates() {
            const hasFiles = selectedFiles.length > 0;
            document.getElementById('btn-merge').disabled = selectedFiles.length < 2;
            document.getElementById('btn-split').disabled = !hasFiles;
            document.getElementById('btn-rotate').disabled = !hasFiles;
            document.getElementById('btn-compress').disabled = !hasFiles;
            document.getElementById('btn-watermark').disabled = !hasFiles;
            document.getElementById('btn-extract').disabled = !hasFiles;
            document.getElementById('btn-protect').disabled = !hasFiles;
        }

        function showLoading(tool, isLoading) {
            const btn = document.getElementById(`btn-${tool}`);
            const spinner = document.getElementById(`spinner-${tool}`);
            btn.disabled = isLoading;
            spinner.style.display = isLoading ? 'inline-block' : 'none';
        }

        function showResult(blob, filename) {
            const url = URL.createObjectURL(blob);
            const downloadLink = document.getElementById('downloadLink');
            downloadLink.href = url;
            downloadLink.download = filename;
            document.getElementById('resultBox').classList.add('active');
            document.getElementById('resultBox').scrollIntoView({ behavior: 'smooth' });
        }

        async function executeMerge() {
            if (selectedFiles.length < 2) return;
            showLoading('merge', true);
            const formData = new FormData();
            selectedFiles.forEach(f => formData.append('files', f));
            try {
                const res = await fetch('/api/merge', { method: 'POST', body: formData });
                if (!res.ok) throw new Error('Errore durante unione');
                showResult(await res.blob(), 'pdf_unito.pdf');
            } catch (err) { alert('Errore: ' + err.message); }
            finally { showLoading('merge', false); }
        }

        async function executeSplit() {
            if (selectedFiles.length === 0) return;
            showLoading('split', true);
            const formData = new FormData();
            formData.append('file', selectedFiles[0]);
            formData.append('pages', document.getElementById('split-pages').value);
            try {
                const res = await fetch('/api/split', { method: 'POST', body: formData });
                if (!res.ok) throw new Error('Errore durante divisione');
                showResult(await res.blob(), 'pagine_estratte.pdf');
            } catch (err) { alert('Errore: ' + err.message); }
            finally { showLoading('split', false); }
        }

        async function executeRotate() {
            if (selectedFiles.length === 0) return;
            showLoading('rotate', true);
            const formData = new FormData();
            formData.append('file', selectedFiles[0]);
            formData.append('angle', document.getElementById('rotate-angle').value);
            try {
                const res = await fetch('/api/rotate', { method: 'POST', body: formData });
                if (!res.ok) throw new Error('Errore durante rotazione');
                showResult(await res.blob(), 'pdf_ruotato.pdf');
            } catch (err) { alert('Errore: ' + err.message); }
            finally { showLoading('rotate', false); }
        }

        async function executeCompress() {
            if (selectedFiles.length === 0) return;
            showLoading('compress', true);
            const formData = new FormData();
            formData.append('file', selectedFiles[0]);
            try {
                const res = await fetch('/api/compress', { method: 'POST', body: formData });
                if (!res.ok) throw new Error('Errore durante compressione');
                showResult(await res.blob(), 'pdf_compresso.pdf');
            } catch (err) { alert('Errore: ' + err.message); }
            finally { showLoading('compress', false); }
        }

        async function executeWatermark() {
            if (selectedFiles.length === 0) return;
            showLoading('watermark', true);
            const formData = new FormData();
            formData.append('file', selectedFiles[0]);
            formData.append('text', document.getElementById('watermark-text').value);
            try {
                const res = await fetch('/api/watermark', { method: 'POST', body: formData });
                if (!res.ok) throw new Error('Errore filigrana');
                showResult(await res.blob(), 'pdf_filigranato.pdf');
            } catch (err) { alert('Errore: ' + err.message); }
            finally { showLoading('watermark', false); }
        }

        async function executeExtractText() {
            if (selectedFiles.length === 0) return;
            showLoading('extract', true);
            const formData = new FormData();
            formData.append('file', selectedFiles[0]);
            try {
                const res = await fetch('/api/extract-text', { method: 'POST', body: formData });
                if (!res.ok) throw new Error('Errore estrazione testo');
                showResult(await res.blob(), 'testo_estratto.txt');
            } catch (err) { alert('Errore: ' + err.message); }
            finally { showLoading('extract', false); }
        }

        async function executeProtect() {
            if (selectedFiles.length === 0) return;
            const pass = document.getElementById('protect-password').value;
            if (!pass) { alert('Inserisci una password!'); return; }
            showLoading('protect', true);
            const formData = new FormData();
            formData.append('file', selectedFiles[0]);
            formData.append('password', pass);
            try {
                const res = await fetch('/api/protect', { method: 'POST', body: formData });
                if (!res.ok) throw new Error('Errore protezione');
                showResult(await res.blob(), 'pdf_protetto.pdf');
            } catch (err) { alert('Errore: ' + err.message); }
            finally { showLoading('protect', false); }
        }
    </script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
