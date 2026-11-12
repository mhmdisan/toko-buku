# routes/transaction.py: endpoint transaksi dengan pemrosesan asinkron.
import asyncio
import os
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

import database as db
from models import TransactionAccepted, TransactionCreate, TransactionResponse

router = APIRouter(prefix="/transactions", tags=["Transactions"])


# Gembok konkurensi tingkat modul: SATU lock dipakai bersama oleh semua request
# di dalam proses ini. asyncio.Lock hanya mengatur coroutine dalam satu event loop.
stok_lock = asyncio.Lock()


# VERSI 1 - TANPA LOCK (rawan race condition, hanya untuk demonstrasi Tahap 1).
async def potong_stok_tanpa_lock(item_id: int, qty: int) -> bool:
    stok_terkini = await db.get_stok(item_id)  # 1) baca stok
    # Jeda buatan: saat coroutine ini menunggu, event loop menjalankan request
    # lain yang membaca stok LAMA yang sama -> jendela race condition terbuka.
    await asyncio.sleep(0.01)
    if stok_terkini is None or stok_terkini < qty:
        return False  # stok habis / tidak cukup
    await db.decrement_stok(item_id, qty)  # 2) tulis berdasarkan nilai usang
    return True


# VERSI 2 - DENGAN asyncio.Lock (aman).
async def potong_stok_dengan_lock(item_id: int, qty: int) -> bool:
    # Critical section: hanya SATU coroutine yang boleh masuk pada satu waktu.
    # Request kedua menunggu di sini sampai request pertama selesai menulis,
    # sehingga ia membaca stok TERBARU (bukan nilai usang).
    async with stok_lock:
        stok_terkini = await db.get_stok(item_id)
        await asyncio.sleep(0.01)  # jeda yang sama, kini aman karena dikunci
        if stok_terkini is None or stok_terkini < qty:
            return False
        await db.decrement_stok(item_id, qty)
        return True


# Pemilih mode pemotongan stok.
# Secara default menggunakan lock (USE_LOCK="1").
# Untuk pengujian Tahap 1 (race condition), set environment variable USE_LOCK="0"
# Contoh di PowerShell:
#   $env:USE_LOCK="0"; uvicorn main:app --port 8000
async def potong_stok(item_id: int, qty: int) -> bool:
    """Memanggil fungsi pemotongan stok sesuai konfigurasi lingkungan USE_LOCK."""
    # Dicek dinamis per pemanggilan agar mudah diuji/diubah
    use_lock = os.getenv("USE_LOCK", "1") != "0"
    if use_lock:
        return await potong_stok_dengan_lock(item_id, qty)
    else:
        return await potong_stok_tanpa_lock(item_id, qty)


# Fungsi pekerja internal di latar belakang (BUKAN endpoint HTTP).
# Dijadwalkan oleh BackgroundTasks FastAPI setelah respon HTTP 202 dikembalikan ke klien,
# sehingga endpoint POST /transactions tidak tertahan (non-blocking) menunggu proses selesai.
async def proses_transaksi_background(trx_id: int, item_id: int, qty: int) -> None:
    try:
        # Transisi status 1: pending -> processing
        await db.update_trx_status(trx_id, "processing")
        
        # Simulasi pekerjaan I/O intensif (misal: verifikasi pembayaran/komunikasi payment gateway).
        # await asyncio.sleep(3) menyerahkan giliran CPU ke event loop, sehingga ratusan
        # request lain tetap dapat diproses tanpa terblokir sama sekali.
        await asyncio.sleep(3)
        
        # Transisi status 2: processing -> completed
        await db.update_trx_status(trx_id, "completed")
    except Exception:
        # Kompensasi kesalahan: kembalikan stok yang sempat dipotong & tandai failed
        await db.increment_stok(item_id, qty)
        await db.update_trx_status(trx_id, "failed")


@router.post("", response_model=TransactionAccepted,
             status_code=status.HTTP_202_ACCEPTED)
async def create_transaction(data: TransactionCreate, bg: BackgroundTasks):
    """Endpoint untuk membuat transaksi baru secara asinkron.
    
    1. Memvalidasi keberadaan resource buku di basis data.
    2. Memeriksa kecukupan stok dan memotongnya secara atomic/aman (jika lock aktif).
    3. Menyimpan transaksi dengan status awal 'pending'.
    4. Mendaftarkan fungsi pekerja latar belakang ke BackgroundTasks.
    5. Mengembalikan respon instan HTTP 202 Accepted tanpa menunggu sleep(3) selesai.
    """
    # Validasi 1: buku harus terdaftar di basis data.
    if await db.get_book(data.item_id) is None:
        raise HTTPException(status_code=404, detail="Buku tidak ditemukan")

    # Validasi 2: stok mencukupi (sekaligus memotong stok).
    # Jika gagal (stok tidak cukup), kembalikan HTTP 409 Conflict.
    if not await potong_stok(data.item_id, data.qty):
        raise HTTPException(status_code=409, detail="Stok habis atau tidak mencukupi")

    trx_id = await db.insert_transaction(data.item_id, data.qty, status="pending")
    
    # Jadwalkan pekerjaan latar belakang; respon segera dikembalikan secara instan.
    bg.add_task(proses_transaksi_background, trx_id, data.item_id, data.qty)
    return {"id": trx_id, "status": "pending", "message": "Transaksi diproses"}


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(
    status: Literal["pending", "processing", "completed", "failed"] | None = Query(None, description="Filter transaksi berdasarkan status"),
    skip: int = Query(0, ge=0, description="Jumlah data yang dilewati"),
    limit: int = Query(10, ge=1, le=100, description="Jumlah maksimal data yang diambil"),
):
    """Mendapatkan daftar transaksi dengan dukungan pagination dan filter status."""
    return await db.list_transactions(status, skip, limit)


@router.get("/{trx_id}", response_model=TransactionResponse)
async def get_transaction(trx_id: int):
    trx = await db.get_transaction(trx_id)
    if trx is None:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    return trx
