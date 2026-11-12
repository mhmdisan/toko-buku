# seed.py: skrip inisialisasi minimal 10 data awal buku.
# Cara pakai:
#   python seed.py          (mengisi data jika tabel masih kosong)
#   python seed.py --reset  (menghapus dan mengisi ulang 12 data buku)
import asyncio
import sys

import aiosqlite

from database import DB_PATH, init_db, insert_book

DATA = [
    ("Laskar Pelangi", "Andrea Hirata", "Novel", 85000, 20),
    ("Bumi Manusia", "Pramoedya Ananta Toer", "Novel", 110000, 15),
    ("Filosofi Teras", "Henry Manampiring", "Self-Improvement", 98000, 25),
    ("Atomic Habits", "James Clear", "Self-Improvement", 120000, 30),
    ("Clean Code", "Robert C. Martin", "Teknologi", 350000, 10),
    ("Belajar Python", "Eric Matthes", "Teknologi", 275000, 12),
    ("Sapiens", "Yuval Noah Harari", "Sejarah", 135000, 18),
    ("Cantik Itu Luka", "Eka Kurniawan", "Novel", 95000, 14),
    ("Dilan 1990", "Pidi Baiq", "Novel", 79000, 22),
    ("Pemrograman Web", "Budi Raharjo", "Teknologi", 150000, 16),
    ("Negeri 5 Menara", "Ahmad Fuadi", "Novel", 89000, 19),
    ("Rich Dad Poor Dad", "Robert Kiyosaki", "Bisnis", 105000, 17),
]


async def main():
    await init_db()
    reset = "--reset" in sys.argv or "-r" in sys.argv

    async with aiosqlite.connect(DB_PATH) as db:
        if reset:
            await db.execute("DELETE FROM books")
            await db.execute("DELETE FROM transactions")
            await db.commit()
            print("[INFO] Data lama berhasil direset.")
        else:
            cur = await db.execute("SELECT COUNT(*) FROM books")
            count = (await cur.fetchone())[0]
            if count > 0:
                print(f"[INFO] Basis data sudah memiliki {count} data buku. Seed dilewati (gunakan '--reset' jika ingin mengulang).")
                return

    for row in DATA:
        await insert_book(*row)
    print(f"[SUKSES] {len(DATA)} data buku berhasil diinisialisasi ke basis data SQLite.")


if __name__ == "__main__":
    asyncio.run(main())
