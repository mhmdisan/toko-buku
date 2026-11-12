# main.py: inisialisasi FastAPI dan registrasi router.
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import init_db
from routes import resource, transaction


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Event lifecycle FastAPI: menginisialisasi basis data SQLite saat startup."""
    await init_db()
    yield


app = FastAPI(
    title="API Toko Buku - Komputasi Paralel & Terdistribusi",
    description=(
        "Implementasi REST API asinkron untuk UTS Komputasi Paralel dan Terdistribusi. "
        "Mendukung CRUD resource utama, transaksi latar belakang (BackgroundTasks), "
        "dan proteksi race condition dengan asyncio.Lock."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Registrasi Router
app.include_router(resource.router)
app.include_router(transaction.router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Selamat datang di API Toko Buku (UTS Komputasi Paralel & Terdistribusi)",
        "docs": "/docs",
        "endpoints": {
            "resource": "/books",
            "transaction": "/transactions"
        }
    }

