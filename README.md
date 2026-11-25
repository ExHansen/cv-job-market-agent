# AI Agent Pembuat & Optimizer CV Berbasis Job Market Intelligence (Local LLM)

Folder ini berisi hasil riset komprehensif untuk membangun **AI Agent lokal** yang tidak hanya membantu membuat/merapikan CV, tetapi juga **memahami kondisi job market terkini** (misalnya untuk role *Data Engineer*), melakukan *gap analysis*, memperbaiki isi CV sesuai standar ATS & ekspektasi industri terbaru, serta menghasilkan PDF CV siap lamar secara otomatis.

---

## Ringkasan Eksekutif

Membangun AI Agent CV yang benar-benar efektif (bukan sekadar *wrapper* prompt chat biasa) membutuhkan **4 pilar utama**:

1. **Data Strategy (Job Market + Career Ground Truth)**
   - **Data Eksternal (Job Market):** Mengumpulkan lowongan kerja aktual via `python-jobspy` (LinkedIn, Indeed, Glassdoor, JobStreet/SEEK) dan *ATS-direct feeds* (Greenhouse, Lever, Ashby), lalu diagregasi di **DuckDB/SQLite** untuk membaca tren skill & frekuensi keyword secara objektif, serta diindeks ke Vector DB (**LanceDB/ChromaDB**) untuk *semantic matching*.
   - **Data Internal (Single Source of Truth):** Menyimpan seluruh riwayat karier, proyek, dan metrik user dalam format terstruktur (`master_profile.yaml`). Ini krusial sebagai *guardrail* agar LLM tidak pernah mengarang (halusinasi) pengalaman kerja palsu.
2. **Local LLM & Multilingual Embeddings**
   - **LLM Utama:** Keluarga **Qwen3** (`qwen3:8b` / `qwen3:14b` / `qwen3:32b` via Ollama) adalah pilihan terkuat saat ini untuk *tool calling*, *structured JSON output*, serta kualitas bahasa **Indonesia & Inggris** yang seimbang.
   - **Embeddings Lokal:** **`qwen3-embedding`** (0.6B/4B) atau **`bge-m3`** untuk pencocokan semantik lintas bahasa (CV bahasa Inggris/Indonesia vs JD lokal/global).
3. **Agentic Workflow (Stateful + Critic Loop + Human-in-the-Loop)**
   - Menggunakan **LangGraph** (untuk alur kerja *stateful*, loop revisi, dan checkpoint) dipadukan dengan **Pydantic / PydanticAI** (untuk memvalidasi output JSON dari local LLM agar tidak rusak).
   - Menyertakan tahap **Wawancara Interaktif (Interview Node)** ketika CV user kurang metrik/angka dampak, serta **Fact-Check Critic Node** untuk memastikan tidak ada klaim yang dibuat-buat.
4. **ATS-Friendly Rendering (Resume-as-Code)**
   - Menggunakan **RenderCV** (berbasis **Typst** + validasi **Pydantic** dari file YAML) untuk meng-compile CV menjadi PDF berformat rapi, *single-column*, *machine-readable*, dan lolos parsing ATS.

---

## Peta Dokumen Riset

Baca dokumen secara berurutan untuk memahami keseluruhan desain sistem:

| No | Dokumen | Fokus Bahasan |
| :--- | :--- | :--- |
| 01 | [01-data-strategy.md](./01-data-strategy.md) | Sumber data job market (Global & ID), strategi scraping/API, skema Master Profile, arsitektur DuckDB + Vector DB, dan manajemen kesegaran data. |
| 02 | [02-local-llm-guide.md](./02-local-llm-guide.md) | Pemilihan Local LLM terbaik (Qwen3, Gemma 3/4, DeepSeek-R1, Llama 3.3), estimasi VRAM per kelas hardware, dual-model routing, embeddings ID/EN, dan constrained decoding. |
| 03 | [03-agent-workflow-architecture.md](./03-agent-workflow-architecture.md) | Perbandingan framework agent (LangGraph vs PydanticAI vs CrewAI), arsitektur multi-step workflow (diagram Mermaid), anti-hallucination critic loop, dan Human-in-the-Loop. |
| 04 | [04-case-study-data-engineer.md](./04-case-study-data-engineer.md) | Studi kasus konkret untuk role **Data Engineer**: tren skill 2025/2026, standar ATS, transformasi bullet point (XYZ/STAR), dan contoh skema data YAML/JSON. |
| 05 | [05-implementation-roadmap.md](./05-implementation-roadmap.md) | Rekomendasi tech stack 100% lokal & open-source, struktur folder proyek, roadmap pembangunan bertahap (MVP -> Production), dan mitigasi risiko. |
| 06 | [06-portfolio-tech-stack.md](./06-portfolio-tech-stack.md) | Blueprint tech stack **Portfolio-Grade** (Data + AI + Full-Stack), strategi Live Demo agar bisa dicoba recruiter, observability/evals (Arize Phoenix), dan checklist bukti portofolio. |

---

## Rekomendasi Tech Stack Ringkas (100% Lokal & Open-Source)

```text
User CV (PDF/DOCX) ──► PyMuPDF4LLM / Docling ──► Master Profile (YAML)
                                                        │
Job Market Boards  ──► python-jobspy + ATS APIs ──► DuckDB + LanceDB (bge-m3 / qwen3-embedding)
                                                        │
                                                        ▼
                       LangGraph + PydanticAI + Ollama (Qwen3 8B/14B/32B)
                                                        │
                                                        ▼
                       Validated CV YAML ──► RenderCV (Typst) ──► ATS-Friendly PDF
```

---

## Quick Start (Jalur 2: Lean High-Impact Scaffold)

### 1. Siapkan Model Lokal Ollama (Optimal untuk RTX 4060 8 GB VRAM)
```powershell
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b
```
*(Untuk copywriting tambahan atau uji cepat sebelum pull `qwen3:8b`, kamu juga bisa set `OLLAMA_MODEL=qwen2.5-coder:7b` atau `gemma3:12b` di `.env`.)*

### 2. Salin Konfigurasi & Profil Dasar
```powershell
Copy-Item .env.example .env
Copy-Item data\master_profile.example.yaml data\master_profile.yaml
```

### 3. Jalankan Backend (FastAPI + LangGraph + DuckDB)
```powershell
cd backend
uv sync --extra dev --extra scraping --extra render
uv run pytest -v
uv run cv-agent market --role "Data Engineer" --region "Indonesia"
uv run uvicorn cv_agent.api.main:app --reload --port 8000
```

### 4. Jalankan Frontend (Next.js Dashboard)
```powershell
cd frontend
npm install
npm run dev
```
Buka `http://localhost:3000` untuk melihat **Job Market Skill Radar**, **Live LangGraph Trace**, dan **Before vs After CV Diff**.

