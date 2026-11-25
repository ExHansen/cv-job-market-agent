# 05. Tech Stack & Roadmap Implementasi

Dokumen ini merangkum pilihan tech stack 100% lokal & open-source, struktur direktori proyek yang direkomendasikan saat siap coding, serta roadmap bertahap dari MVP hingga aplikasi utuh.

---

## 1. Rekomendasi Tech Stack Final (Python Ecosystem)

| Layer | Pilihan Utama | Alternatif | Alasan Pemilihan |
| :--- | :--- | :--- | :--- |
| **Language & Env** | Python 3.12 + `uv` | Poetry / pip | `uv` sangat cepat untuk manajemen dependency; Python 3.12 cocok untuk RenderCV & AI stack. |
| **Local LLM Runner** | **Ollama** | LM Studio / vLLM | Setup paling mudah di Windows/Mac, mendukung structured output & tool calling native. |
| **Model LLM** | **`qwen3:14b`** (16GB VRAM) atau **`qwen3:8b`** (8GB VRAM) | `qwen3:32b` (24GB VRAM), `gemma3:12b` | Terbaik untuk tool calling + JSON + Bahasa Indonesia/Inggris. |
| **Embedding Lokal** | **`bge-m3`** atau **`qwen3-embedding:0.6b`** | `nomic-embed-text` | Akurasi tinggi untuk semantik bilingual ID & EN. |
| **Agent Orchestration** | **LangGraph** + **Pydantic / PydanticAI** | PydanticAI standalone | Tahan banting untuk local LLM berkat validasi skema ketat, cyclic critic loop, dan checkpointing. |
| **Job Market Ingestion** | **`python-jobspy`** + Greenhouse/Lever JSON fetcher | Adzuna / Arbeitnow API | Mendukung LinkedIn, Indeed, Glassdoor, dan JobStreet (SEEK) dalam satu library. |
| **CV Document Parser** | **`pymupdf4llm`** (+ fallback **`docling`**) | `pdfplumber` | Cepat untuk PDF standar, akurat untuk CV 2 kolom/sidebar lewat Docling. |
| **Analytical & Vector DB** | **DuckDB** + **LanceDB** | SQLite + ChromaDB | Keduanya *embedded* (file-based, tanpa Docker/server), ringan, dan sangat cepat. |
| **PDF CV Renderer** | **`rendercv[full]`** (Typst engine) | WeasyPrint / LaTeX | Validasi Pydantic otomatis, output PDF ATS-friendly super rapi, berbasis YAML. |
| **UI (Phase 3)** | **Streamlit** atau **FastAPI + Next.js** | CLI (`Typer` + `Rich`) | Mulai dari CLI dulu agar fokus ke kualitas agent, baru tambahkan UI web. |

---

## 2. Struktur Folder Proyek yang Direkomendasikan

```text
cv-job-market-agent/
├── pyproject.toml                  # Dependency management (uv)
├── .env.example                    # Konfigurasi Ollama host, model name, proxy opsional
├── config/
│   ├── skills_taxonomy.yaml        # Kamus normalisasi skill & sinonim (dbt, Iceberg, dll.)
│   └── ats_rules.yaml              # Aturan keras ATS (max kata/bullet, forbidden sections)
├── data/                           # (gitignore) Data lokal privat
│   ├── master_profile.yaml         # Single Source of Truth karier user
│   ├── market.duckdb               # Database analitik lowongan & tren skill
│   ├── vectors.lancedb/            # Vector store untuk semantic JD matching
│   └── outputs/                    # Hasil CV YAML, PDF, & Audit Report
├── src/
│   ├── ingestion/
│   │   ├── cv_parser.py            # PyMuPDF4LLM / Docling -> MasterProfile
│   │   ├── jobspy_fetcher.py       # Wrapper python-jobspy + deduplikasi
│   │   ├── ats_fetcher.py          # Fetcher Greenhouse / Lever public boards
│   │   └── skill_extractor.py      # Two-stage extractor (Regex taxonomy + Local LLM)
│   ├── storage/
│   │   ├── market_db.py            # Query agregasi tren DuckDB
│   │   └── vector_store.py         # LanceDB + Ollama embeddings
│   ├── agent/
│   │   ├── state.py                # TypedDict / Pydantic Graph State
│   │   ├── prompts.py              # System prompts per node (bilingual-aware)
│   │   ├── nodes/
│   │   │   ├── profile_intake.py   # Parsing & Interactive Interview (HITL)
│   │   │   ├── market_intel.py     # Market cache check & trend synthesizer
│   │   │   ├── gap_auditor.py      # Gap Analysis & ATS scoring
│   │   │   ├── cv_rewriter.py      # XYZ/STAR bullet rewriting
│   │   │   └── critic_verifier.py  # Deterministic anti-hallucination + LLM review
│   │   └── graph.py                # Definisi LangGraph workflow & checkpointer
│   ├── renderer/
│   │   └── rendercv_bridge.py      # Mapping Pydantic CV -> RenderCV YAML -> PDF
│   └── cli.py                      # Entrypoint CLI (Typer + Rich)
└── tests/
    ├── test_fact_checker.py        # Unit test guardrail anti-halusinasi
    └── test_rendercv_compile.py    # Test validasi skema & kompilasi PDF
```

---

## 3. Roadmap Pembangunan Bertahap

### Phase 1: MVP — Local CV Auditor & Generator (Minggu 1)
*Fokus: Pipeline dasar berjalan mulus end-to-end dengan 1 role dan 1 JD.*
- Setup Ollama (`qwen3:8b` atau `qwen3:14b`) dan verifikasi structured output dengan Pydantic.
- Bangun `cv_parser.py` (`pymupdf4llm`) untuk membaca CV lama user ke `master_profile.yaml`.
- Bangun `cv_rewriter.py` + `critic_verifier.py` sederhana (deterministic fact-checker).
- Integrasikan `rendercv` untuk meng-compile hasil perbaikan menjadi PDF ATS-friendly.
- Antarmuka awal: CLI interaktif (`cv-agent audit`, `cv-agent tailor`).

### Phase 2: Job Market Intelligence Engine (Minggu 2)
*Fokus: Agent benar-benar "melek" kondisi job market terkini.*
- Integrasikan `python-jobspy` (LinkedIn, Indeed, JobStreet/SEEK) + `ats_fetcher.py` (Greenhouse/Lever).
- Bangun skema **DuckDB** (`job_postings`, `job_skills`, `market_snapshots`) + kamus `skills_taxonomy.yaml`.
- Integrasikan **LanceDB** + `bge-m3` / `qwen3-embedding` untuk semantic matching antara proyek user dan JD.
- Sambungkan semua node ke **LangGraph** lengkap dengan *SQLite checkpointer* dan *Human-in-the-Loop* interview mode.

### Phase 3: Polish, Visual QA & Web Dashboard (Minggu 3+)
*Fokus: Kenyamanan pemakaian & fitur lanjutan.*
- Bangun antarmuka Web (Streamlit atau Next.js + FastAPI):
  - Dashboard tren skill job market per role (grafik persentase skill wajib & tren terbaru).
  - Diff viewer *Before vs After* untuk setiap bullet point CV.
  - Live PDF preview + tombol download.
- Tambahkan **Visual Layout QA** opsional menggunakan model multimodal lokal (`gemma3:12b` / Gemma 4) untuk mengecek PNG hasil RenderCV (memastikan layout tidak bocor ke halaman 2 dengan 2 baris sisa).
- Fitur tambahan: Cover Letter generator lokal & Interview Prep questions berdasarkan *skill gap* yang ditemukan di CV.

---

## 4. Risiko Utama & Cara Mitigasinya

| Risiko | Dampak | Solusi Mitigasi |
| :--- | :--- | :--- |
| **Halusinasi Local LLM** (mengarang skill/angka) | Fatal saat interview teknis dengan recruiter. | Terapkan **Master Profile Grounding** + **Deterministic Python Checker** (verifikasi ketat bahwa semua skill & angka di CV baru ada di `master_profile.yaml`). |
| **Blokir / Rate-Limit Scraper** (LinkedIn/Indeed) | Gagal mengambil data job market. | Gunakan **batch caching mingguan** di DuckDB, batasi `results_wanted` per query (20–50 job), kombinasikan dengan **ATS direct APIs** (Greenhouse/Lever), dan beri opsi input manual file/teks JD. |
| **Local LLM Merusak Format JSON / YAML** | Pipeline crash saat compile RenderCV. | Gunakan native **Structured Outputs (Ollama)** + **Pydantic validation retry loop** (maks 3x self-correction). |
| **Context Window Penuh / Lambat di GPU Lokal** | Response lama atau instruksi terpotong. | Selalu agregasi data JD di **DuckDB** terlebih dahulu (kirim ringkasan statistik, bukan 50 JD mentah) dan set `num_ctx` eksplisit (`8192`–`16384`). |
| **Bahasa Campur (ID–EN) Tidak Konsisten** | CV terlihat kurang profesional. | Pisahkan bahasa diskusi (Bahasa Indonesia di chat/interview) dengan bahasa dokumen output (`output_language: "en"` atau `"id"` di konfigurasi CV). |
