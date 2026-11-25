# 04. Studi Kasus Nyata: Role Data Engineer (2025–2026)

Dokumen ini mengilustrasikan secara konkret bagaimana AI Agent bekerja ketika user adalah seorang **Data Engineer** yang ingin:
1. Mengetahui kondisi & ekspektasi job market Data Engineer saat ini.
2. Mengevaluasi dan memperbaiki (*fixing*) CV agar sesuai ketentuan ATS dan ekspektasi hiring manager modern.

---

## 1. Snapshot Kondisi Job Market Data Engineer (2025–2026)

Berdasarkan tren industri modern, ekspektasi pasar terhadap **Data Engineer** telah bergeser dari sekadar *"menulis script ETL cron job"* menjadi **scalable cloud lakehouse, analytics engineering, data quality, efisiensi biaya (FinOps), dan AI-ready data pipelines**.

### Peta Skill & Keyword ATS Utama (Data Engineer)

| Kategori | Core / Must-Have (Baseline Market) | Modern Differentiators (Nilai Jual Tinggi) |
| :--- | :--- | :--- |
| **Bahasa Pemrograman** | `SQL` (Advanced: window functions, CTE, query tuning), `Python` | `PySpark`, `Scala` / `Go` / `Rust` (untuk high-throughput) |
| **Transformasi & Modeling** | `dbt` (dbt-core / dbt Cloud), Dimensional Modeling (Star Schema, SCD Type 2) | Semantic Layer, SQLMesh, Data Contracts |
| **Orchestration** | `Apache Airflow` (termasuk Airflow 3 asset-aware scheduling) | `Dagster`, `Prefect`, `Mage` |
| **Cloud & Data Warehouse** | `Google BigQuery`, `Snowflake`, `Databricks`, `AWS Redshift` | `Microsoft Fabric`, ClickHouse, DuckDB |
| **Lakehouse & Table Formats** | `Parquet`, Object Storage (`S3` / `GCS` / `ADLS`) | **`Apache Iceberg`**, **`Delta Lake`** (ACID, partition evolution, time travel) |
| **Streaming & Distributed** | `Apache Spark`, `Apache Kafka` | `Apache Flink`, Debezium (CDC), Redpanda |
| **DataOps, Quality & IaC** | `Git`, `Docker`, `CI/CD` (GitHub Actions/GitLab CI), Data Quality Testing | `Terraform` (IaC), `Great Expectations` / `Soda`, Data Observability, Lineage |
| **AI-Ready Data Pipelines** | API / unstructured data ingestion | Vector/Embedding pipelines untuk RAG, Feature Stores, LLM data prep |

---

## 2. Ketentuan CV ATS-Friendly yang Ditegakkan oleh Agent

Ketika Agent mengaudit dan membuat ulang CV, aturan-aturan berikut dijadikan **hard constraints** (aturan wajib) di Critic Node & RenderCV template:

1. **Layout Single-Column Murni:** Hindari template Canva 2 kolom, *progress bar* skill (misal: `Python: 4/5 bintang` — tidak bisa dibaca ATS dan terlihat tidak profesional), ikon berlebihan, atau text box.
2. **Heading Standar:** Gunakan judul bagian yang langsung dikenali parser ATS: `Professional Summary`, `Technical Skills`, `Work Experience`, `Projects`, `Education`, `Certifications`.
3. **Format Tanggal & Lokasi Konsisten:** Contoh: `Jan 2024 – Present` atau `01/2024 – Present`.
4. **Panjang Ideal:**
   - Fresh graduate s.d. < 5 tahun pengalaman: **1 halaman padat**.
   - Senior / Lead (> 5 tahun pengalaman): **Maksimal 2 halaman** (halaman kedua minimal terisi >50%, jangan hanya menyisakan 3 baris).
5. **Kepadatan Keyword Secara Kontekstual:** Jangan menumpuk keyword di bagian `Skills` saja (*keyword stuffing*). Setiap skill utama yang diklaim di bagian `Skills` **harus muncul minimal 1 kali** di dalam bullet `Work Experience` atau `Projects` untuk membuktikan penggunaan nyata.
6. **File Output:** PDF berbasis teks vektor (*searchable text*) hasil kompilasi **Typst / RenderCV** atau LaTeX—bukan PDF hasil ekspor gambar.

---

## 3. Contoh Cara Agent Melakukan "CV Fixing" (Before vs After)

Agent menggunakan **Formula Google XYZ**:
> *"Accomplished **[X]** (hasil/dampak), as measured by **[Y]** (metrik terukur), by doing **[Z]** (alat/metode teknis yang digunakan)."*

### Contoh 1: ETL & Orchestration
- **Before (CV Lama — Terlalu Deskriptif & Lemah di ATS):**
  > *"Bertanggung jawab membuat dan menjaga ETL pipeline harian menggunakan Python dan Airflow untuk tim bisnis."*
- **Pertanyaan Interview Agent (HITL):**
  > *"Pipeline ini menarik data dari sumber apa ke warehouse apa? Berapa besar datanya dan apakah ada peningkatan kecepatan atau penurunan error setelah kamu buat?"*
- **After (Diperbaiki Agent — Terukur & Kaya Keyword Market):**
  > *"Architected automated ELT pipelines using **Python** and **Apache Airflow** to ingest 15M+ daily rows from REST APIs and PostgreSQL into **BigQuery**, reducing daily executive reporting latency from 4 hours to 35 minutes."*

### Contoh 2: Transformasi Data & Data Quality
- **Before (CV Lama):**
  > *"Menulis query SQL untuk membersihkan data dan membuat tabel laporan."*
- **After (Diperbaiki Agent):**
  > *"Built 45+ modular **dbt** transformation models implementing **Star Schema dimensional modeling** and automated **data quality tests** (not-null, uniqueness, freshness), cutting downstream BI dashboard incidents by 60%."*

### Contoh 3: Storage / Lakehouse & Cost Optimization
- **Before (CV Lama):**
  > *"Mengelola data lake di AWS S3 dan optimasi query Snowflake."*
- **After (Diperbaiki Agent):**
  > *"Migrated raw JSON/Parquet landing tables to **Apache Iceberg** on **AWS S3** with automated partitioning and compaction, lowering **Snowflake** query scan volume and monthly compute costs by 32%."*

---

## 4. Contoh Struktur Data Internal (`master_profile.yaml` & `market_snapshot.json`)

### A. Contoh `master_profile.yaml` (Single Source of Truth User)
```yaml
profile:
  name: "Nama Lengkap"
  target_roles: ["Data Engineer", "Analytics Engineer"]
  location: "Jakarta, Indonesia (Open to Remote)"
  links:
    github: "https://github.com/username"
    linkedin: "https://linkedin.com/in/username"

skills_verified:
  languages: ["Python", "SQL", "PySpark"]
  transformation: ["dbt", "Dimensional Modeling", "Star Schema"]
  orchestration: ["Apache Airflow"]
  warehouses_cloud: ["Google BigQuery", "Snowflake", "AWS S3", "Docker"]
  data_quality_ops: ["Git", "GitHub Actions", "Great Expectations"]

experiences:
  - id: "exp_01"
    company: "PT Contoh Teknologi"
    role: "Data Engineer"
    period: "Jan 2024 - Present"
    bullets:
      - id: "exp_01_b1"
        raw_fact: "Bangun pipeline ingest API & Postgres ke BigQuery pakai Python & Airflow"
        metrics:
          volume: "15M+ rows/day"
          impact: "reporting latency turun dari 4 jam ke 35 menit"
          verified_by_user: true
        tools_used: ["Python", "Apache Airflow", "PostgreSQL", "Google BigQuery"]
      - id: "exp_01_b2"
        raw_fact: "Buat 45 model dbt dengan star schema dan automated data quality tests"
        metrics:
          impact: "dashboard incidents turun 60%"
          verified_by_user: true
        tools_used: ["dbt", "SQL", "BigQuery"]
```

### B. Contoh `market_snapshot.json` (Hasil Agregasi DuckDB)
```json
{
  "role": "Data Engineer",
  "region": "Indonesia & Remote APAC",
  "snapshot_date": "2026-11-25",
  "sample_size_jobs": 120,
  "top_mandatory_skills": [
    {"skill": "SQL", "frequency_pct": 95.8},
    {"skill": "Python", "frequency_pct": 91.7},
    {"skill": "Apache Airflow", "frequency_pct": 66.7},
    {"skill": "dbt", "frequency_pct": 54.2},
    {"skill": "Apache Spark", "frequency_pct": 50.0},
    {"skill": "BigQuery", "frequency_pct": 45.8},
    {"skill": "Snowflake", "frequency_pct": 38.3}
  ],
  "rising_differentiators": [
    {"skill": "Apache Iceberg", "frequency_pct": 24.1},
    {"skill": "Dagster", "frequency_pct": 18.3},
    {"skill": "Terraform", "frequency_pct": 29.2},
    {"skill": "Kafka", "frequency_pct": 31.7}
  ],
  "common_gap_recommendations": [
    "Jika belum pernah memakai Apache Iceberg atau Kafka di kantor, buat 1 portfolio project end-to-end (misal: streaming CDC -> Iceberg -> dbt -> dashboard) dan taruh di bagian Projects."
  ]
}
```

Dengan dua file terstruktur seperti ini, AI Agent bisa secara objektif menjawab:
- *"Skill apa yang paling banyak dicari di market Data Engineer sekarang tapi belum ada di CV saya?"*
- *"Tolong perbaiki CV saya agar ATS-friendly untuk melamar ke lowongan Data Engineer di perusahaan X tanpa mengarang pengalaman palsu."*
