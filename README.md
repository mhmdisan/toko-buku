Tautan Video Presentasi: https://youtu.be/contoh_video_unlisted (Ganti dengan URL video YouTube Unlisted Anda)

# Proyek UTS Komputasi Paralel dan Terdistribusi
**Tema Aplikasi:** API Toko Buku  
**Teknologi:** FastAPI (Python 3.10+), aiosqlite, asyncio.Lock, BackgroundTasks, Uvicorn, Locust  
**Program Studi:** Teknik Informatika, Universitas Muhammadiyah Pontianak  

---

## Daftar Isi
1. [Deskripsi Proyek](#deskripsi-proyek)
2. [Struktur Direktori](#struktur-direktori)
3. [Panduan Instalasi](#panduan-instalasi)
4. [Inisialisasi Data Awal (Seeding)](#inisialisasi-data-awal-seeding)
5. [Menjalankan Server](#menjalankan-server)
6. [Daftar Endpoint API](#daftar-endpoint-api)
7. [Pengujian Race Condition (B3)](#pengujian-race-condition-b3)
8. [Pengujian Beban / Benchmark Locust (C1)](#pengujian-beban--benchmark-locust-c1)
9. [Laporan UTS](#laporan-uts)

---

## 1. Deskripsi Proyek
Aplikasi ini merupakan RESTful API backend toko buku yang dirancang secara asinkron (*non-blocking*) menggunakan framework **FastAPI** dan pustaka **aiosqlite** untuk penyimpanan SQLite. Proyek ini mengimplementasikan konsep komputasi paralel dan konkurensi meliputi:
* **Asynchronous Database Operations:** Semua query SQLite dieksekusi secara asinkron tanpa memblokir event loop.
* **Background Tasks:** Pemrosesan transaksi diproses di latar belakang secara asinkron dengan status `pending -> processing -> completed / failed`.
* **Concurrency Locking:** Proteksi *race condition* (mencegah *overselling*) pada pengurangan stok menggunakan `asyncio.Lock()`.
* **Multi-Worker Deployment:** Pengujian performa konkurensi menggunakan 1 worker vs 4 worker Uvicorn dan diukur dengan Locust.

---

## 2. Struktur Direktori
```text
toko_buku/
├── main.py              # Inisialisasi FastAPI dan registrasi router
├── database.py          # Koneksi aiosqlite dan inisialisasi tabel
├── models.py            # Skema Pydantic (request & response)
├── seed.py              # Skrip inisialisasi 12 data buku awal
├── test_race.py         # Skrip pengujian mandiri race condition
├── locustfile.py        # Skenario pengujian beban Locust (Read & Write)
├── requirements.txt     # Daftar dependensi pustaka Python
├── .gitignore           # File pengabaian git
├── README.md            # Dokumentasi panduan instalasi dan eksekusi
├── routes/
│   ├── __init__.py
│   ├── resource.py      # Endpoint CRUD resource utama (Buku)
│   └── transaction.py   # Endpoint transaksi asinkron & locking
└── docs/
    └── laporan_uts.pdf  # Berkas laporan hasil pengujian dan analisis
```

---

## 3. Panduan Instalasi
Pastikan Python 3.10 atau versi lebih baru telah terpasang di komputer Anda.

1. **Clone repositori dan masuk ke direktori proyek:**
   ```bash
   git clone <URL_REPOSITORI_GITHUB_ANDA>
   cd toko_buku
   ```

2. **(Opsional/Disarankan) Buat dan aktifkan lingkungan virtual (virtual environment):**
   * Di Windows (Command Prompt / PowerShell):
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```

3. **Pasang dependensi pustaka:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 4. Inisialisasi Data Awal (Seeding)
Jalankan skrip `seed.py` untuk mengisi basis data SQLite dengan 12 data buku awal:
```bash
python seed.py
```
*Catatan:* Jika ingin mengosongkan dan mengisi ulang data dari awal, gunakan:
```bash
python seed.py --reset
```

---

## 5. Menjalankan Server
Untuk menjalankan API server FastAPI menggunakan Uvicorn:

* **Mode 1 Worker (Default):**
  ```bash
  uvicorn main:app --port 8000
  ```
* **Mode 4 Worker:**
  ```bash
  uvicorn main:app --workers 4 --port 8000
  ```

Buka antarmuka interaktif **Swagger UI** di browser:
👉 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 6. Daftar Endpoint API

### Resource Utama (`/books`)
| Method | Path | Deskripsi | Status Code |
|---|---|---|---|
| `GET` | `/books?skip=0&limit=10` | Menampilkan daftar seluruh buku (paginasi) | `200 OK` |
| `GET` | `/books/{id}` | Menampilkan detail satu buku berdasarkan ID | `200 OK` / `404 Not Found` |
| `POST` | `/books` | Menambahkan buku baru (validasi Pydantic) | `201 Created` / `422 Unprocessable` |
| `PUT` | `/books/{id}` | Memperbarui data buku | `200 OK` / `404 Not Found` |
| `DELETE` | `/books/{id}` | Menghapus data buku permanen (*hard delete*) | `200 OK` / `404 Not Found` |

### Transaksi Asinkron (`/transactions`)
| Method | Path | Deskripsi | Status Code |
|---|---|---|---|
| `POST` | `/transactions` | Membuat transaksi baru; respon instan kembali dengan status `pending` dan diproses di latar belakang | `202 Accepted` / `409 Conflict` |
| `GET` | `/transactions?status=pending` | Menampilkan riwayat transaksi (opsional filter status) | `200 OK` |
| `GET` | `/transactions/{id}` | Melihat status transaksi terkini (`pending`/`processing`/`completed`/`failed`) | `200 OK` / `404 Not Found` |

---

## 7. Pengujian Race Condition (B3)

Pengujian ini membandingkan penanganan konkurensi ketika 2 request memesan buku yang sama secara serentak dalam milidetik yang sama saat stok buku hanya tersisa 1.

### Tahap 1: Kondisi Tanpa Lock (Melihat Race Condition / Overselling)
1. Di **Terminal 1**, jalankan server FastAPI tanpa lock (di PowerShell):
   ```powershell
   $env:USE_LOCK="0"; uvicorn main:app --port 8000
   ```
   *(Atau di CMD: `set USE_LOCK=0 && uvicorn main:app --port 8000`)*
2. Di **Terminal 2**, jalankan skrip pengujian:
   ```bash
   python test_race.py
   ```
3. **Hasil yang diamati:** Kedua request sukses (`202 Accepted`) dan stok akhir menjadi `-1` (*overselling*).  
   *Ambil tangkapan layar terminal kedua untuk dokumen laporan.*

### Tahap 2: Kondisi Dengan Lock (Proteksi via `asyncio.Lock`)
1. Di **Terminal 1**, jalankan server FastAPI dengan lock (default):
   ```powershell
   $env:USE_LOCK="1"; uvicorn main:app --port 8000
   ```
2. Di **Terminal 2**, jalankan kembali skrip pengujian:
   ```bash
   python test_race.py
   ```
3. **Hasil yang diamati:** Satu request sukses (`202 Accepted`), sedangkan request kedua ditolak dengan status `409 Conflict` ("Stok habis atau tidak mencukupi"). Stok akhir tersisa `0`.  
   *Ambil tangkapan layar terminal kedua untuk dokumen laporan.*

---

## 8. Pengujian Beban / Benchmark Locust (C1)

Pengujian beban membandingkan performa server antara **1 worker** vs **4 worker**.

### 1. Skenario Read (GET /books: 100 request, konkurensi 20)
* **Jalankan server 1 worker:**
  ```bash
  uvicorn main:app --workers 1 --port 8000
  ```
  Di terminal terpisah jalankan benchmark:
  ```bash
  locust -f locustfile.py ReadUser --headless -u 20 -r 20 --host http://127.0.0.1:8000
  ```
* **Jalankan server 4 worker:**
  ```bash
  uvicorn main:app --workers 4 --port 8000
  ```
  Di terminal terpisah jalankan benchmark:
  ```bash
  locust -f locustfile.py ReadUser --headless -u 20 -r 20 --host http://127.0.0.1:8000
  ```

### 2. Skenario Write (POST /transactions: 50 request, konkurensi 10)
* **Pada server 1 worker:**
  ```bash
  locust -f locustfile.py WriteUser --headless -u 10 -r 10 --host http://127.0.0.1:8000
  ```
* **Pada server 4 worker:**
  ```bash
  locust -f locustfile.py WriteUser --headless -u 10 -r 10 --host http://127.0.0.1:8000
  ```

Catat metrik **Total Waktu**, **Throughput**, dan **Rata-rata Latensi** yang tercetak di akhir pengujian ke dalam tabel laporan UTS.

---

## 9. Laporan UTS
Dokumen laporan lengkap disimpan pada folder [`docs/laporan_uts.pdf`](docs/laporan_uts.pdf) mencakup jawaban konsep Bagian A (Concurrency vs Paralelisme, GIL, dan Diagram Arsitektur), hasil uji race condition, serta analisis performa benchmark.

