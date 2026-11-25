# 02. Local LLM, Embedding Models & Hardware Guide

Memilih Local LLM untuk **AI Agent** berbeda dengan memilih LLM untuk sekadar ngobrol. Untuk kasus CV + Job Market Agent, model lokal wajib kuat di **4 kemampuan spesifik**:
1. **Tool / Function Calling** yang stabil (tidak error format JSON di tengah loop).
2. **Structured Output** ketat (patuh pada skema Pydantic/YAML untuk ekstraksi JD & generate RenderCV).
3. **Kemampuan Bilingual (Bahasa Indonesia & Inggris)** yang natural—karena user berdiskusi dalam Bahasa Indonesia, namun banyak JD tech & CV profesional ditulis dalam Bahasa Inggris.
4. **Instruction Following & Non-Hallucination** (patuh pada aturan *"jangan mengarang skill yang tidak ada di Master Profile"*).

---

## 1. Perbandingan Keluarga Local LLM Terbaik (2025–2026)

| Keluarga Model | Contoh Model di Ollama | Kekuatan Utama | Catatan untuk CV & Market Agent |
| :--- | :--- | :--- | :--- |
| **Qwen3 / Qwen3.5 / Qwen3.8** *(Rekomendasi #1)* | `qwen3:8b`, `qwen3:14b`, `qwen3:32b` (serta varian MoE seperti `qwen3:30b-a3b`) | Juara untuk **tool calling**, **JSON structured output**, **multilingual (ID & EN sangat baik)**, dan punya hybrid *thinking mode*. | **Pilihan utama terbaik.** Paling jarang merusak skema JSON saat loop multi-turn dan paham konteks kerja di Indonesia maupun global. |
| **Gemma 3 / Gemma 4** | `gemma3:12b`, `gemma3:27b` (dan varian multimodal Gemma 4) | Kualitas penulisan prosa sangat rapi, *lightweight*, mendukung multimodal (bisa baca screenshot layout PDF CV untuk visual QA!). | Sangat bagus sebagai **CV Copywriter** atau **Visual Layout Reviewer** (memeriksa screenshot hasil PDF RenderCV). Untuk tool calling, pastikan memakai template/constrained decoding yang tepat. |
| **DeepSeek-R1 (Distilled)** | `deepseek-r1:8b`, `deepseek-r1:14b`, `deepseek-r1:32b` | Sangat kuat untuk *deep reasoning*, audit logika, dan *gap analysis* yang kritis. | Output `<think>` memakan KV cache/context lebih banyak dan kadang kurang disiplin untuk *strict tool calling*. Cocok dipakai khusus di **Critic / Auditor Node**, bukan sebagai orchestrator tool utama. |
| **Llama 3.3 / Llama 3.1** | `llama3.1:8b`, `llama3.3:70b` | Standar ekosistem framework agent (LangGraph, CrewAI, PydanticAI). | Varian `70B` sangat kuat tapi butuh >= 48GB VRAM. Untuk ukuran kecil-menengah (8B–32B), **Qwen3** umumnya lebih unggul di Bahasa Indonesia dan ketepatan JSON. |

---

## 2. Panduan Pemilihan Model Berdasarkan Hardware (VRAM / RAM)

Aturan praktis untuk kuantisasi default Ollama (**Q4_K_M**): kebutuhan VRAM sekitar **0.55–0.65 GB per miliar parameter** ditambah **15–25% headroom** untuk KV Cache (panjang context window, misalnya 8K–16K token untuk menampung CV + 5 JD sekaligus).

| Tier Hardware | Estimasi Spec | Model Rekomendasi (Ollama) | Context Window Aman | Performa Agent |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Entry / Laptop GPU** | 8 GB VRAM (RTX 3060/4060 Laptop) atau 16 GB RAM Mac | `qwen3:8b` (utama) atau `qwen3.5:9b` | 8K tokens | Cukup baik untuk CLI agent & ekstraksi bertahap. Hindari menyuapkan 20 JD mentah sekaligus dalam 1 prompt. |
| **Tier 2: Mid-Range Sweet Spot** | 12–16 GB VRAM (RTX 3060 12GB, RTX 4060 Ti 16GB, RTX 4070) atau 24–32 GB Unified Mac | `qwen3:14b` (utama) + `gemma3:12b` (opsional visual/copy) | 16K tokens | **Sweet spot terbaik.** Sangat stabil untuk tool calling, gap analysis mendalam, dan penulisan bullet point tajam. |
| **Tier 3: High-End Local** | 24 GB VRAM (RTX 3090 / 4090) atau 48–64 GB Mac | `qwen3:32b` atau `qwen3:30b-a3b` (MoE super cepat) + `deepseek-r1:32b` (auditor) | 16K–32K tokens | Mendekati kualitas model cloud untuk rewriting CV & penalaran karier yang bernuansa. |
| **Tier 4: CPU-Only (Tanpa GPU Dedicated)** | RAM 16–32 GB (CPU modern) | `qwen3:4b` / `qwen3:8b` (atau MoE aktif kecil seperti `30b-a3b` jika RAM >= 32GB) | 4K–8K tokens | Bisa jalan, namun latensi per turn lambat (5–15 token/detik). Gunakan ekstraksi rule-based semaksimal mungkin agar beban LLM minimal. |

---

## 3. Strategi Dual-Model Routing (Mengoptimalkan Kecepatan vs Kualitas)

Daripada memaksa satu model besar mengerjakan semuanya, workflow agent bisa membagi peran berdasarkan kompleksitas tugas:

1. **Fast / Structured Worker Model** (misal: `qwen3:8b` atau `qwen3:14b`, `temperature=0.0–0.2`)
   - Ekstraksi JSON skill & persyaratan dari puluhan JD hasil scraping.
   - Parsing teks CV lama ke skema `master_profile.yaml`.
   - Menjalankan tool calling rutin (query DuckDB, panggil JobSpy).
2. **Reasoning / Critic & Writer Model** (misal: `qwen3:14b/32b` atau `gemma3:27b`, `temperature=0.3–0.5`)
   - Melakukan *Gap Analysis* strategis terhadap tren market.
   - Menulis ulang *Professional Summary* dan *Experience Bullets* (formula XYZ/STAR) agar terdengar natural dan berdampak.
   - Melakukan audit anti-halusinasi (*Fact-Check Loop*).

> **Catatan Manajemen VRAM:** Di Ollama, jika kamu memakai 2 model berbeda pada GPU 12–16 GB, Ollama akan otomatis meng-unload model pertama sebelum memuat model kedua (ada jeda ~2–5 detik saat *swap*). Oleh karena itu, pada mesin <= 16 GB VRAM, lebih efisien menggunakan **1 model serba bisa (`qwen3:14b`)** dan cukup membedakan parameter `temperature` + mode *thinking* (on/off).

---

## 4. Local Embedding Models (Khusus Bilingual Indonesia & Inggris)

Karena lowongan kerja dan CV user sering mencampur istilah Inggris dan Indonesia (*code-switching*), jangan gunakan embedding khusus Inggris saja.

| Model Embedding (Ollama) | Ukuran | Context | Dukungan ID + EN | Fitur Unggulan |
| :--- | :--- | :--- | :--- | :--- |
| **`qwen3-embedding:0.6b`** *(atau `4b`)* | ~0.6B (~600 MB) | Hingga 32K tokens | **Sangat Baik** | Top-tier MTEB multilingual, mendukung Matryoshka (dimensi fleksibel), bisa meng-embed JD panjang utuh tanpa banyak chunking. |
| **`bge-m3`** | ~567M (~2.2 GB) | 8,192 tokens | **Sangat Baik** (100+ bahasa) | Mendukung **Dense + Sparse (lexical) + Multi-vector** sekaligus; sangat matang untuk produksi dan berlisensi MIT. |
| **`nomic-embed-text`** | ~137M | 8,192 tokens | Sedang (dominan Inggris) | Sangat ringan untuk CPU lemah, tetapi kurang presisi jika banyak teks Bahasa Indonesia. |

**Rekomendasi:** Gunakan **`qwen3-embedding:0.6b`** atau **`bge-m3`** via Ollama (`ollama pull bge-m3` / `ollama pull qwen3-embedding`).

---

## 5. Inference Engine & Teknik Wajib untuk Stabilitas Agent

### Pilihan Serving Engine
- **Ollama (Rekomendasi Utama untuk Windows/Mac Personal):** Paling mudah di-setup, mendukung native tool calling + structured JSON output (`format=schema`), manajemen VRAM otomatis, dan kompatibel dengan OpenAI API (`http://localhost:11434/v1`).
- **vLLM / SGLang:** Cocok jika suatu saat ingin di-deploy di server Linux dengan banyak user paralel (*high throughput* / *batching*).
- **LM Studio / llama.cpp:** Alternatif bagus di Windows jika ingin kontrol GUI atas kuantisasi GGUF dan *GPU offload layers*.

### 3 Teknik Wajib Agar Local LLM Tidak "Ngaco" Saat Jadi Agent
1. **Constrained Decoding / Structured Outputs:** Selalu paksa output ekstraksi dan output CV menggunakan JSON Schema (via Pydantic + fitur native structured output Ollama). Ini menghilangkan ~90% error parsing JSON.
2. **Jangan Lempar Data Mentah Besar ke Context:** Jika ada 50 JD hasil scraping, **jangan** masukkan 50 teks JD ke prompt LLM! Agregasi dulu lewat SQL di DuckDB menjadi tabel ringkasan statistik (misal: Top 25 skills + persentase kemunculan + 3 contoh snippet kalimat requirement), baru kirim ringkasannya ke LLM.
3. **Kontrol `num_ctx` Secara Eksplisit:** Default `num_ctx` di Ollama sering kali hanya `4096` token! Untuk CV Agent, set eksplisit ke **`8192` atau `16384`** di konfigurasi client agar sistem tidak diam-diam memotong instruksi awal (*silent truncation*).
