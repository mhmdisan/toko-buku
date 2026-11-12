# test_race.py: skrip pengujian mandiri race condition (2 request serentak ke /transactions).
# Pengujian ini membandingkan 2 kondisi:
#   1. Kondisi Tanpa Lock : kedua request berhasil, stok akhir bernilai minus (overselling).
#   2. Kondisi Dengan Lock : 1 request berhasil (202), 1 request ditolak (409 Conflict).
import asyncio
import os
import sys

import httpx

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
ITEM_ID = 1


async def reset_stok_jadi_1(client: httpx.AsyncClient) -> None:
    """Mengatur stok buku uji (item_id=1) menjadi tepat 1 lewat endpoint PUT."""
    try:
        res = await client.get(f"/books/{ITEM_ID}")
    except httpx.ConnectError:
        print(f"[ERROR] Gagal terhubung ke {BASE}.")
        print("Pastikan server FastAPI sudah aktif (contoh: uvicorn main:app --port 8000).")
        sys.exit(1)

    if res.status_code == 404:
        print(f"[ERROR] Buku dengan ID {ITEM_ID} belum ada di basis data.")
        print("Silakan jalankan 'python seed.py' terlebih dahulu untuk mengisi data awal.")
        sys.exit(1)

    book = res.json()
    book.pop("id", None)
    book["stok"] = 1
    put_res = await client.put(f"/books/{ITEM_ID}", json=book)
    if put_res.status_code != 200:
        print(f"[ERROR] Gagal mereset stok ke 1: {put_res.text}")
        sys.exit(1)


async def main() -> None:
    url = f"{BASE}/transactions"
    payload = {"item_id": ITEM_ID, "qty": 1}

    async with httpx.AsyncClient(base_url=BASE, timeout=10.0) as client:
        # 1. Pastikan stok awal = 1
        await reset_stok_jadi_1(client)
        buku_awal = (await client.get(f"/books/{ITEM_ID}")).json()
        print("==================================================")
        print("   PENGUJIAN KONKURENSI / RACE CONDITION")
        print("==================================================")
        print(f"Target Resource : Buku ID {ITEM_ID} ('{buku_awal.get('judul')}')")
        print(f"Stok Awal       : {buku_awal.get('stok')}")
        print("Mengirim 2 request POST /transactions serentak (qty=1)...")
        print("--------------------------------------------------")

        # 2. Kirim dua request secara serentak dalam milidetik yang sama menggunakan asyncio.gather
        req1 = client.post(url, json=payload)
        req2 = client.post(url, json=payload)
        res1, res2 = await asyncio.gather(req1, req2)

        # 3. Cetak respon kedua request
        print("Respon Request 1:", res1.status_code, res1.json())
        print("Respon Request 2:", res2.status_code, res2.json())
        print("--------------------------------------------------")

        # 4. Ambil dan cetak stok akhir setelah kedua request selesai diproses
        stok_akhir = (await client.get(f"/books/{ITEM_ID}")).json().get("stok")
        print(f"Stok Akhir      : {stok_akhir}")
        print("==================================================")

        # Analisis ringkas untuk kemudahan tangkapan layar terminal
        if res1.status_code == 202 and res2.status_code == 202 and stok_akhir < 0:
            print("[STATUS] TERJADI RACE CONDITION (OVERSELLING)!")
            print("         Kedua transaksi sukses dan stok akhir bernilai minus.")
            print("         -> Cocok untuk tangkapan layar Tahap 1 (Tanpa Lock).")
        elif (res1.status_code == 202 and res2.status_code == 409) or (res1.status_code == 409 and res2.status_code == 202):
            print("[STATUS] RACE CONDITION TERCEGAH DENGAN AMAN!")
            print("         Satu request sukses (202), satu request ditolak (409 Conflict).")
            print("         -> Cocok untuk tangkapan layar Tahap 2 (Dengan Lock).")
        print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
