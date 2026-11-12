# routes/resource.py: endpoint CRUD untuk resource utama (buku).
from fastapi import APIRouter, HTTPException, Query, status

import database as db
from models import BookCreate, BookResponse

router = APIRouter(prefix="/books", tags=["Books"])


@router.get("", response_model=list[BookResponse])
async def list_books(skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100)):
    # `await` melepas kendali ke event loop selama query berjalan.
    return await db.list_books(skip, limit)


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: int):
    book = await db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Buku tidak ditemukan")
    return book


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(data: BookCreate):
    new_id = await db.insert_book(**data.model_dump())
    return await db.get_book(new_id)


@router.put("/{book_id}", response_model=BookResponse)
async def update_book(book_id: int, data: BookCreate):
    if not await db.update_book(book_id, **data.model_dump()):
        raise HTTPException(status_code=404, detail="Buku tidak ditemukan")
    return await db.get_book(book_id)  # kembalikan data terbaru


@router.delete("/{book_id}")
async def delete_book(book_id: int):
    if not await db.delete_book(book_id):
        raise HTTPException(status_code=404, detail="Buku tidak ditemukan")
    return {"message": f"Buku {book_id} berhasil dihapus"}
