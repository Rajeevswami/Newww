"""Tenant-scoped Qdrant collections for resume and job embeddings."""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)
from app.core.config import settings

VECTOR_SIZE = 1536
RESUME_COLLECTION = "resumes"
JOB_COLLECTION = "jobs"
_client: QdrantClient | None = None


def reset_client():
    global _client
    _client = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        url = (settings.qdrant_url or "").strip()
        if url in {":memory:", "memory", "memory://"}:
            _client = QdrantClient(":memory:")
        else:
            _client = QdrantClient(url=url, timeout=10)
    return _client


def ensure_collections():
    client = get_client()
    existing = {item.name for item in client.get_collections().collections}
    for name in (RESUME_COLLECTION, JOB_COLLECTION):
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
        if not getattr(client, "_is_client_local", False) and settings.qdrant_url not in {
            ":memory:",
            "memory",
            "memory://",
        }:
            try:
                client.create_payload_index(
                    collection_name=name,
                    field_name="tenant_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass


def upsert_resume_vector(tenant_id: str, resume_id: str, user_id: str, vector: list[float]):
    get_client().upsert(
        collection_name=RESUME_COLLECTION,
        points=[
            PointStruct(
                id=resume_id,
                vector=vector,
                payload={"tenant_id": tenant_id, "resume_id": resume_id, "user_id": user_id},
            )
        ],
    )


def upsert_job_vector(tenant_id: str, job_id: str, vector: list[float]):
    get_client().upsert(
        collection_name=JOB_COLLECTION,
        points=[
            PointStruct(
                id=job_id,
                vector=vector,
                payload={"tenant_id": tenant_id, "job_id": job_id},
            )
        ],
    )


def search_resumes(tenant_id: str, vector: list[float], limit: int = 50):
    """Search resume vectors. tenant_id is required and is the only tenant that can match."""
    if not tenant_id:
        raise ValueError("tenant_id is required for vector search")
    result = get_client().query_points(
        collection_name=RESUME_COLLECTION,
        query=vector,
        query_filter=Filter(
            must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
        ),
        limit=limit,
        with_payload=True,
    )
    return result.points


def score_resume_against_job(
    tenant_id: str, resume_id: str, job_vector: list[float]
) -> float | None:
    hits = search_resumes(tenant_id, job_vector, limit=100)
    for hit in hits:
        payload = hit.payload or {}
        if payload.get("tenant_id") != tenant_id:
            continue
        if payload.get("resume_id") == resume_id:
            return round(max(0, min(100, float(hit.score) * 100)), 1)
    return None
