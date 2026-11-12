# database.py: koneksi aiosqlite dan inisialisasi tabel.
# Sesuai ketentuan UTS: Penyimpanan data WAJIB menggunakan SQLite yang diakses
# melalui pustaka aiosqlite secara asinkron (non-blocking).
import aiosqlite

DB_PATH = "toko_buku.db"

# Tabel resource utama: 5 kolom selain id (judul, penulis, kategori, harga, stok).
# Kolom kuantitas wajib: stok INTEGER NOT NULL.
# Catatan: CHECK(stok >= 0) tidak dipasang pada skema DDL SQLite agar fenomena
# overselling (stok minus) dapat teramati jelas pada pengujian konkurensi B3 Tahap 1
# (kondisi tanpa lock). Pada kondisi ber-lock, non-negatif dijamin oleh validasi
# Pydantic dan mekanisme locking asyncio.Lock.
CREATE_BOOKS_TABLE = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    penulis TEXT NOT NULL,
    kategori TEXT NOT NULL,
    harga REAL NOT NULL,
    stok INTEGER NOT NULL
);
"""

# Tabel transaksi: status mengikuti alur pending -> processing -> completed / failed.
CREATE_TRANSACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES books(id),
    qty INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db() -> None:
    """Membuat tabel jika belum ada (dipanggil saat aplikasi start)."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        # Aktifkan Write-Ahead Logging (WAL) agar mendukung multi-worker concurrency
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA busy_timeout = 5000;")
        await db.execute(CREATE_BOOKS_TABLE)
        await db.execute(CREATE_TRANSACTIONS_TABLE)
        await db.commit()


# ---------------------- CRUD resource utama (books) ----------------------
async def list_books(skip: int, limit: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM books ORDER BY id LIMIT ? OFFSET ?", (limit, skip)
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_book(book_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def insert_book(judul: str, penulis: str, kategori: str,
                      harga: float, stok: int) -> int:
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        cur = await db.execute(
            "INSERT INTO books (judul, penulis, kategori, harga, stok) "
            "VALUES (?, ?, ?, ?, ?)",
            (judul, penulis, kategori, harga, stok),
        )
        await db.commit()
        return cur.lastrowid


async def update_book(book_id: int, judul: str, penulis: str, kategori: str,
                      harga: float, stok: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        cur = await db.execute(
            "UPDATE books SET judul=?, penulis=?, kategori=?, harga=?, stok=? "
            "WHERE id=?",
            (judul, penulis, kategori, harga, stok, book_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_book(book_id: int) -> bool:
    """Hard delete: baris dihapus permanen dari basis data."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        cur = await db.execute("DELETE FROM books WHERE id = ?", (book_id,))
        await db.commit()
        return cur.rowcount > 0


# ---------------------- Stok (dipakai transaksi) ----------------------
async def get_stok(item_id: int) -> int | None:
    """Mengembalikan stok saat ini, atau None jika buku tidak ada."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        cur = await db.execute("SELECT stok FROM books WHERE id = ?", (item_id,))
        row = await cur.fetchone()
        return row[0] if row else None


async def decrement_stok(item_id: int, qty: int) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("UPDATE books SET stok = stok - ? WHERE id = ?", (qty, item_id))
        await db.commit()


async def increment_stok(item_id: int, qty: int) -> None:
    """Mengembalikan stok (dipakai saat transaksi gagal/kompensasi)."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("UPDATE books SET stok = stok + ? WHERE id = ?", (qty, item_id))
        await db.commit()


# ---------------------- Transaksi ----------------------
async def insert_transaction(item_id: int, qty: int, status: str = "pending") -> int:
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        cur = await db.execute(
            "INSERT INTO transactions (item_id, qty, status) VALUES (?, ?, ?)",
            (item_id, qty, status),
        )
        await db.commit()
        return cur.lastrowid


async def update_trx_status(trx_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute(
            "UPDATE transactions SET status = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (status, trx_id),
        )
        await db.commit()


async def get_transaction(trx_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM transactions WHERE id = ?", (trx_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_transactions(status: str | None, skip: int, limit: int) -> list[dict]:
    query = "SELECT * FROM transactions"
    params: list = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY id LIMIT ? OFFSET ?"
    params += [limit, skip]
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        return [dict(r) for r in await cur.fetchall()]
