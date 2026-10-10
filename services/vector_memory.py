"""
JARVIS v10 APEX PRIME — Vector Tabanlı Semantik Hafıza
=======================================================
Mevcut LongMemory (JSON profil) ve SQLite yapısını BOZMAZ.
ChromaDB üzerine sentence-transformers ile embed yaparak
anlamsal (semantic) arama sağlar.

Bağımlılıklar (opsiyonel):
    pip install chromadb sentence-transformers

Kurulu değilse: basit SQLite anahtar kelime aramasına düşer (fallback).
"""
from __future__ import annotations

import datetime
import re
import threading
import time
from pathlib import Path
from typing import Optional

from logger_setup import logger

# ── Yol sabitleri ────────────────────────────────────────────────────────
APP_DATA_DIR = Path.home() / ".jarvis"
VECTOR_DB_DIR = APP_DATA_DIR / "vector_memory"
VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
try:
    import os; os.chmod(str(VECTOR_DB_DIR), 0o700)
except OSError:
    pass

# ── ChromaDB import (opsiyonel) ───────────────────────────────────────────
_CHROMA_OK = False
_EMBED_OK   = False
_chroma_client = None
_collection    = None
_embedder      = None
_init_lock = threading.Lock()
_initialized   = False


def _lazy_init():
    """İlk kullanımda ChromaDB + embedder başlat."""
    global _CHROMA_OK, _EMBED_OK, _chroma_client, _collection, _embedder, _initialized
    with _init_lock:
        if _initialized:
            return
        _initialized = True
        try:
            import chromadb
            _chroma_client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
            _collection = _chroma_client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"hnsw:space": "cosine"},
            )
            _CHROMA_OK = True
            logger.info("[VectorMemory] ChromaDB hazır. Koleksiyon: jarvis_memory")
        except ImportError:
            logger.warning("[VectorMemory] ChromaDB kurulu değil. Anahtar kelime aramasına geçildi.")
        except Exception as exc:
            logger.warning("[VectorMemory] ChromaDB başlatılamadı: %s", exc)

        try:
            from sentence_transformers import SentenceTransformer
            # Türkçe destekli çok dilli model (~400 MB, ilk çalıştırmada indirilir)
            _embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            _EMBED_OK = True
            logger.info("[VectorMemory] SentenceTransformer yüklendi.")
        except ImportError:
            logger.warning("[VectorMemory] sentence-transformers kurulu değil.")
        except Exception as exc:
            logger.warning("[VectorMemory] Embedder başlatılamadı: %s", exc)


# ── Zaman ifadesi → tarih aralığı ─────────────────────────────────────────
def _parse_time_filter(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    'geçen hafta', 'dün', 'bu ay' gibi ifadeleri ISO tarih aralığına çevirir.
    Returns: (start_iso, end_iso) veya (None, None)
    """
    t = text.lower()
    now = datetime.datetime.now()

    if any(k in t for k in ["geçen hafta", "gecen hafta", "last week"]):
        start = now - datetime.timedelta(days=now.weekday() + 7)
        end   = start + datetime.timedelta(days=7)
        return start.isoformat(), end.isoformat()

    if any(k in t for k in ["bu hafta", "this week"]):
        start = now - datetime.timedelta(days=now.weekday())
        return start.isoformat(), now.isoformat()

    if any(k in t for k in ["dün", "yesterday"]):
        yesterday = now - datetime.timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end   = yesterday.replace(hour=23, minute=59, second=59)
        return start.isoformat(), end.isoformat()

    if any(k in t for k in ["bugün", "today"]):
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.isoformat(), now.isoformat()

    if any(k in t for k in ["bu ay", "this month"]):
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start.isoformat(), now.isoformat()

    if any(k in t for k in ["geçen ay", "gecen ay", "last month"]):
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_end = first_this - datetime.timedelta(seconds=1)
        last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0)
        return last_month_start.isoformat(), last_month_end.isoformat()

    # "X gün önce"
    m = re.search(r"(\d+)\s*gün önce", t)
    if m:
        days_ago = int(m.group(1))
        start = now - datetime.timedelta(days=days_ago + 1)
        end   = now - datetime.timedelta(days=days_ago)
        return start.isoformat(), end.isoformat()

    return None, None


# ── Hafıza kayıt fonksiyonu ────────────────────────────────────────────────
def save_message(
    content: str,
    role: str,
    session_id: int,
    ts: Optional[str] = None,
):
    """
    Bir mesajı vektör veritabanına kaydeder.
    
    Args:
        content   : Mesaj içeriği
        role      : "user" | "assistant"
        session_id: SQLite session_id
        ts        : ISO timestamp (None ise şu an)
    """
    _lazy_init()
    if not _CHROMA_OK or not _EMBED_OK:
        return  # Sessizce çık

    if not content or len(content.strip()) < 5:
        return

    ts = ts or datetime.datetime.now().isoformat()
    doc_id = f"{session_id}_{role}_{int(time.time() * 1000)}"

    try:
        embedding = _embedder.encode(content[:1000], convert_to_list=True)
        _collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content[:2000]],
            metadatas=[{
                "role": role,
                "session_id": session_id,
                "ts": ts,
                "ts_epoch": datetime.datetime.fromisoformat(ts).timestamp(),
            }],
        )
    except Exception as exc:
        logger.warning("[VectorMemory] Kayıt hatası: %s", exc)


def save_messages_batch(messages: list[dict], session_id: int):
    """
    Çoklu mesajları toplu kaydeder.
    messages: [{"role": "user"/"assistant", "content": "...", "ts": "..."}]
    """
    for msg in messages:
        save_message(
            content=msg.get("content", ""),
            role=msg.get("role", "user"),
            session_id=session_id,
            ts=msg.get("ts"),
        )


# ── Anlamsal arama ────────────────────────────────────────────────────────
def semantic_search(
    query: str,
    n: int = 5,
    date_filter_text: str = "",
    role_filter: Optional[str] = None,
    session_id: Optional[int] = None,
) -> list[dict]:
    """
    Anlamsal arama yapar.
    
    Args:
        query           : Aranacak metin / soru
        n               : Döndürülecek maksimum sonuç sayısı
        date_filter_text: 'geçen hafta', 'dün' gibi doğal dil zaman filtresi
        role_filter     : "user" | "assistant" | None (hepsi)
        session_id      : Belirli bir oturumla sınırla (None = hepsi)
    
    Returns:
        [{"content": str, "role": str, "ts": str, "score": float}]
    """
    _lazy_init()
    if not _CHROMA_OK or not _EMBED_OK:
        return _fallback_search(query, n)

    try:
        # Zaman filtresi
        where_conditions = []
        start_ts, end_ts = _parse_time_filter(date_filter_text)
        if start_ts and end_ts:
            start_epoch = datetime.datetime.fromisoformat(start_ts).timestamp()
            end_epoch   = datetime.datetime.fromisoformat(end_ts).timestamp()
            where_conditions.append({"ts_epoch": {"$gte": start_epoch}})
            where_conditions.append({"ts_epoch": {"$lte": end_epoch}})

        if role_filter:
            where_conditions.append({"role": {"$eq": role_filter}})

        if session_id is not None:
            where_conditions.append({"session_id": {"$eq": session_id}})

        # where filtresi
        where = None
        if len(where_conditions) == 1:
            where = where_conditions[0]
        elif len(where_conditions) > 1:
            where = {"$and": where_conditions}

        # Embed sorgu
        query_embedding = _embedder.encode(query[:500], convert_to_list=True)

        results = _collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n, max(1, _collection.count())),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            score = max(0.0, 1.0 - dist)  # cosine distance → similarity
            output.append({
                "content": doc,
                "role": meta.get("role", "?"),
                "ts": meta.get("ts", ""),
                "session_id": meta.get("session_id", -1),
                "score": round(score, 3),
            })
        # Skorla sırala (en iyi önce)
        output.sort(key=lambda x: x["score"], reverse=True)
        return output

    except Exception as exc:
        logger.warning("[VectorMemory] Arama hatası: %s", exc)
        return _fallback_search(query, n)


def _fallback_search(query: str, n: int) -> list[dict]:
    """
    ChromaDB yoksa SQLite üzerinde basit anahtar kelime araması.
    """
    try:
        import sqlite3

        from config import DB_PATH
        keywords = [w for w in query.lower().split() if len(w) > 2]
        if not keywords:
            return []
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        placeholders = " OR ".join(["LOWER(m.content) LIKE ?" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords]
        rows = con.execute(
            f"SELECT m.content, m.role, m.ts, m.session_id "
            f"FROM messages m WHERE {placeholders} "
            f"ORDER BY m.id DESC LIMIT ?",
            params + [n],
        ).fetchall()
        con.close()
        return [
            {"content": r["content"], "role": r["role"], "ts": r["ts"],
             "session_id": r["session_id"], "score": 0.5}
            for r in rows
        ]
    except Exception as exc:
        logger.warning("[VectorMemory] Fallback arama hatası: %s", exc)
        return []


def format_search_results(results: list[dict], max_chars: int = 3000) -> str:
    """Arama sonuçlarını insan okunabilir formatta birleştirir."""
    if not results:
        return "Hafızada ilgili konuşma bulunamadı."

    parts = []
    total_chars = 0
    for i, r in enumerate(results, 1):
        ts_str = r.get("ts", "")[:16].replace("T", " ")
        role_str = "Ben" if r.get("role") == "user" else "JARVIS"
        snippet = r["content"][:400].replace("\n", " ")
        chunk = f"[{i}] {ts_str} — {role_str}: {snippet}"
        if total_chars + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total_chars += len(chunk)

    return "\n".join(parts)


def is_memory_query(text: str) -> bool:
    """Kullanıcı metninin anlamsal hafıza sorgusu olup olmadığını hızla kontrol eder."""
    triggers = [
        "geçen hafta", "gecen hafta", "dün", "bugün", "bu ay", "geçen ay",
        "ne zaman konuşmuştuk", "bahsetmiştim", "bahsetmiştik", "söylemiştim",
        "hatırlıyor musun", "hatırla", "önceden", "eskiden", "o zaman",
        "konuşmuştuk", "demiştim", "demiştin", "yazmıştım",
        "proje", "not", "kayıt", "anlat bakalım", "ne söylemiştim",
    ]
    t = text.lower()
    return any(trigger in t for trigger in triggers)


def get_memory_context_for_ai(query: str, n: int = 4) -> str:
    """
    AI'ya ekstra bağlam olarak verilecek hafıza özeti döndürür.
    is_memory_query() true döndüğünde çağrılır.
    """
    date_filter = query  # zaman ifadesi de sorguda olabilir
    results = semantic_search(query, n=n, date_filter_text=date_filter)
    if not results:
        return ""
    formatted = format_search_results(results)
    return f"İLGİLİ HAFIZA KAYITLARI:\n{formatted}"


def delete_memory(session_id: Optional[int] = None, before_ts: Optional[str] = None):
    """
    Hafıza kayıtlarını siler.
    session_id verilirse o oturuma ait kayıtlar silinir.
    before_ts (ISO) verilirse o tarihten önceki kayıtlar silinir.
    İkisi de None ise tüm hafıza silinir.
    """
    _lazy_init()
    if not _CHROMA_OK:
        return "ChromaDB kurulu değil, vektör hafıza temizliği yapılamadı."

    try:
        if session_id is not None:
            results = _collection.get(where={"session_id": {"$eq": session_id}})
            ids = results.get("ids", [])
        elif before_ts is not None:
            epoch = datetime.datetime.fromisoformat(before_ts).timestamp()
            results = _collection.get(where={"ts_epoch": {"$lt": epoch}})
            ids = results.get("ids", [])
        else:
            ids = _collection.get()["ids"]

        if ids:
            _collection.delete(ids=ids)
            return f"{len(ids)} vektör hafıza kaydı silindi."
        return "Silinecek kayıt bulunamadı."
    except Exception as exc:
        return f"Hafıza silme hatası: {exc}"


def memory_stats() -> str:
    """Vektör hafıza istatistiklerini döndürür."""
    _lazy_init()
    if not _CHROMA_OK:
        return "ChromaDB kurulu değil. pip install chromadb sentence-transformers"
    try:
        count = _collection.count()
        status = "✓ Aktif (ChromaDB + sentence-transformers)"
        return (
            f"Vektör Hafıza İstatistikleri:\n"
            f"  Durum:           {status}\n"
            f"  Toplam kayıt:    {count}\n"
            f"  Depolama yeri:   {VECTOR_DB_DIR}\n"
            f"  Embed modeli:    paraphrase-multilingual-MiniLM-L12-v2 (Türkçe destekli)"
        )
    except Exception as exc:
        return f"İstatistik alınamadı: {exc}"

