# 🚀 PDF Auto Editor - Microservizio & Web App per Modifica PDF

Un'applicazione web e microservizio API **100% gratuito** e pronto per il deployment su **Render.com** per la gestione automatizzata dei documenti PDF.

---

## 🌟 Caratteristiche Principali

- 🧩 **Unione PDF (Merge)**: Combina più file PDF in un unico documento.
- ✂️ **Divisione Pagine (Split)**: Estrai intervalli specifici (es. 1-3, 5, 8-10) o pagine singole.
- 🔄 **Rotazione Pagine**: Ruota le pagine a 90°, 180° o 270°.
- 🗜️ **Compressione**: Riduce il peso dei file senza perdita di qualità percettibile.
- 💧 **Filigrana**: Aggiungi watermark di testo personalizzati su ogni pagina.
- 📝 **Estrazione Testo**: Estrai tutto il testo dal PDF in formato `.txt`.
- 🔒 **Protezione Password**: Cifra i tuoi documenti con crittografia forte.
- 🖼️ **Anteprima Visiva**: Visualizza le miniature delle pagine in tempo reale prima di procedere.

---

## 🛠️ Requisiti & Architettura

- **Backend**: Python 3 (FastAPI + PyMuPDF + pypdf + Uvicorn)
- **Frontend**: HTML5, Vanilla CSS Glassmorphism, JavaScript ES6
- **Deploy**: Render.com (Web Service Gratuito)

---

## 🚀 Guida al Deployment su Render.com

### Step 1: Carica il Progetto su GitHub

1. Vai su [GitHub.com](https://github.com) e crea un nuovo repository pubblico o privato (es. `pdf-auto-editor`).
2. Nella cartella del progetto sul tuo PC, esegui i seguenti comandi nel terminale:

```bash
git init
git add .
git commit -m "Initial commit - PDF Auto Editor"
git branch -M main
git remote add origin https://github.com/IL_TUO_USERNAME/pdf-auto-editor.git
git push -u origin main
```

---

### Step 2: Crea il Web Service su Render.com

1. Accedi a [Render.com](https://render.com) (puoi registrarti rapidamente con il tuo account GitHub).
2. Nel Dashboard, clicca in alto a destra su **New +** -> **Web Service**.
3. Seleziona **Build and deploy from a Git repository** e collega il tuo repository `pdf-auto-editor`.
4. Compila i dettagli del servizio:
   - **Name**: `pdf-auto-editor` (o a tua scelta)
   - **Region**: Frankfurt (UE) o la più vicina
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free`
5. Clicca su **Create Web Service**.

---

### ⏱️ Risultato
Nel giro di circa 2 minuti Render installerà le dipendenze e avvierà l'applicazione!
Riceverai un URL pubblico del tipo:

👉 **`https://pdf-auto-editor.onrender.com`**

---

## 💻 Test in Locale

Per testare l'applicazione sul tuo computer prima di distribuirla:

```bash
pip install -r requirements.txt
python main.py
```

Apri il browser su `http://localhost:8000`.
