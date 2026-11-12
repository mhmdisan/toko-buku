# locustfile.py: skenario pengujian beban Locust.
#
# Dua skenario (dijalankan terpisah, pilih nama kelasnya):
#   ReadUser  : GET /books          -> 100 request, konkurensi 20
#   WriteUser : POST /transactions  ->  50 request, konkurensi 10
#
# Contoh (server harus sudah berjalan di port 8000):
#   locust -f locustfile.py ReadUser  --headless -u 20 -r 20 --host http://127.0.0.1:8000
#   locust -f locustfile.py WriteUser --headless -u 10 -r 10 --host http://127.0.0.1:8000
#
# Locust tidak punya "berhenti setelah N request" bawaan, jadi dibuat penghitung
# sendiri: tiap user "mengklaim" satu jatah request; setelah jatah habis dan semua
# respon selesai, tes dihentikan dan ringkasan (total waktu, throughput, latensi)
# dicetak.
import random
import time

import httpx
from locust import HttpUser, events, task
from locust.exception import StopUser

JUMLAH_BUKU_SEED = 12  # sesuai seed.py


class Benchmark:
    """Penghitung request + pengukur waktu untuk satu skenario."""

    def __init__(self, nama: str, max_requests: int):
        self.nama = nama
        self.max_requests = max_requests
        self.claimed = 0       # jatah request yang sudah diambil user
        self.done = 0          # request yang sudah selesai
        self.total_latency = 0.0
        self.t_start = None
        self.t_end = None

    def claim(self) -> bool:
        """Ambil satu jatah request. False jika jatah sudah habis."""
        if self.claimed >= self.max_requests:
            return False
        if self.t_start is None:
            self.t_start = time.perf_counter()
        self.claimed += 1
        return True

    def finish_one(self, latency_ms: float, environment) -> None:
        self.done += 1
        self.total_latency += latency_ms
        if self.done >= self.max_requests:
            self.t_end = time.perf_counter()
            environment.runner.quit()  # semua request selesai -> hentikan tes

    def ringkasan(self) -> None:
        if not self.t_end:
            return
        total = self.t_end - self.t_start
        print("\n" + "=" * 52)
        print(f"RINGKASAN BENCHMARK: {self.nama}")
        print(f"  Total request     : {self.done}")
        print(f"  Total waktu       : {total:.3f} detik")
        print(f"  Throughput        : {self.done / total:.2f} request/detik")
        print(f"  Rata-rata latensi : {self.total_latency / self.done:.2f} ms")
        print("=" * 52)


read_bench = Benchmark("GET /books (100 request, konkurensi 20)", 100)
write_bench = Benchmark("POST /transactions (50 request, konkurensi 10)", 50)


@events.test_start.add_listener
def siapkan_stok(environment, **kwargs):
    """Isi stok semua buku menjadi 1000 agar POST tidak ditolak 409 saat uji beban Write."""
    host = environment.host or "http://127.0.0.1:8000"
    try:
        with httpx.Client(base_url=host, timeout=10.0) as c:
            for book_id in range(1, JUMLAH_BUKU_SEED + 1):
                res = c.get(f"/books/{book_id}")
                if res.status_code != 200:
                    continue
                book = res.json()
                book.pop("id", None)
                book["stok"] = 1000
                c.put(f"/books/{book_id}", json=book)
    except Exception as e:
        print(f"[locust] Catatan siapkan_stok: {e}")


@events.test_stop.add_listener
def cetak_ringkasan(environment, **kwargs):
    read_bench.ringkasan()
    write_bench.ringkasan()


class ReadUser(HttpUser):
    """Skenario Read: GET /books, tanpa jeda antar request."""

    @task
    def baca_buku(self):
        if not read_bench.claim():
            raise StopUser()
        with self.client.get("/books?skip=0&limit=10", name="GET /books",
                             catch_response=True) as res:
            res.success() if res.status_code == 200 else res.failure(
                f"status {res.status_code}")
        read_bench.finish_one(res.request_meta["response_time"], self.environment)


class WriteUser(HttpUser):
    """Skenario Write: POST /transactions (respon instan, proses di background)."""

    @task
    def buat_transaksi(self):
        if not write_bench.claim():
            raise StopUser()
        payload = {"item_id": random.randint(1, JUMLAH_BUKU_SEED), "qty": 1}
        with self.client.post("/transactions", json=payload,
                              name="POST /transactions",
                              catch_response=True) as res:
            res.success() if res.status_code == 202 else res.failure(
                f"status {res.status_code}")
        write_bench.finish_one(res.request_meta["response_time"], self.environment)
