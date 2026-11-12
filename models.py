# models.py: skema Pydantic untuk validasi request dan serialisasi response.
from pydantic import BaseModel, Field


class BookBase(BaseModel):
    judul: str = Field(..., min_length=1, max_length=200, description="Judul buku")
    penulis: str = Field(..., min_length=1, max_length=100, description="Nama penulis buku")
    kategori: str = Field(..., min_length=1, max_length=50, description="Kategori buku")
    harga: float = Field(..., gt=0, description="Harga buku (harus lebih besar dari 0)")


class BookCreate(BookBase):
    """Body untuk POST /books dan PUT /books/{id}. Stok wajib bernilai non-negatif (>= 0)."""
    stok: int = Field(..., ge=0, description="Jumlah stok buku (harus >= 0 saat dibuat/diupdate)")


class BookResponse(BookBase):
    """Response data buku.
    Catatan: field 'stok' di sini tidak dibatasi ge=0 agar saat pengujian race condition
    (Tahap 1 tanpa lock), nilai stok negatif (overselling) tetap dapat diserialisasi
    dan ditampilkan dengan status 200 OK (bukan error 500).
    """
    id: int
    stok: int


# ---------------------- Transaksi ----------------------
class TransactionCreate(BaseModel):
    item_id: int = Field(..., gt=0, description="ID resource buku yang dibeli")
    qty: int = Field(..., gt=0, description="Jumlah yang dipesan (harus > 0)")


class TransactionAccepted(BaseModel):
    """Respon instan POST /transactions (status selalu pending)."""
    id: int
    status: str
    message: str


class TransactionResponse(BaseModel):
    id: int
    item_id: int
    qty: int
    status: str
    created_at: str
    updated_at: str

