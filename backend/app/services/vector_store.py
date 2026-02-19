"""
Qdrant vector store service for semantic search over transcript chunks.
Supports filtered search by lecture_order and course_title for context scoping.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue


@dataclass
class ScoredChunk:
    """A retrieved chunk with relevance score and metadata."""
    text: str
    score: float
    metadata: Dict[str, Any]


class VectorStoreService:
    """Qdrant client wrapper with lecture-scoped search methods."""

    def __init__(
        self,
        qdrant_url: str,
        qdrant_api_key: Optional[str] = None,
        collection_name: str = "course_transcripts"
    ):
        if qdrant_api_key:
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        else:
            self.client = QdrantClient(url=qdrant_url)

        self.collection_name = collection_name

    def search(
        self,
        query_vector: list,
        course_title: str,
        max_lecture_order: int,
        top_k: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[ScoredChunk]:
        """Search for relevant chunks within current + previous lectures.

        Applies filter: lecture_order <= max_lecture_order AND course_title = course_title

        Args:
            query_vector: Embedding vector of the query (384 dims)
            course_title: Current course title for scoping
            max_lecture_order: Maximum lecture order to include (current lecture)
            top_k: Number of results to return
            score_threshold: Minimum score threshold (optional)

        Returns:
            List of ScoredChunk objects sorted by relevance
        """
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="lecture_order",
                    range=Range(lte=max_lecture_order)
                ),
                FieldCondition(
                    key="course_title",
                    match=MatchValue(value=course_title)
                )
            ]
        )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query_filter=search_filter,
            query=query_vector,
            limit=top_k,
            score_threshold=score_threshold
        ).points

        return [
            ScoredChunk(
                text=r.payload.get("text", ""),
                score=r.score,
                metadata={
                    "course_title": r.payload.get("course_title", ""),
                    "chapter_title": r.payload.get("chapter_title", ""),
                    "lecture_title": r.payload.get("lecture_title", ""),
                    "lecture_order": r.payload.get("lecture_order", 0),
                    "lecture_id": r.payload.get("lecture_id", ""),
                    "chunk_index": r.payload.get("chunk_index", 0),
                    "timestamp_start": r.payload.get("timestamp_start", "00:00:00"),
                    "timestamp_end": r.payload.get("timestamp_end", "00:00:00"),
                    "duration_seconds": r.payload.get("duration_seconds", 0),
                    "player_embed_url": r.payload.get("player_embed_url", ""),
                }
            )
            for r in results
        ]

    def search_all_lectures(
        self,
        query_vector: list,
        course_title: str,
        top_k: int = 5
    ) -> List[ScoredChunk]:
        """Search across ALL lectures in a course (no lecture_order filter).

        Used for the second pass of future-topic detection:
        if the filtered search returns low scores, this search without
        the lecture_order filter determines if the topic is in a future
        lecture or completely off-topic.
        """
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="course_title",
                    match=MatchValue(value=course_title)
                )
            ]
        )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query_filter=search_filter,
            query=query_vector,
            limit=top_k
        ).points

        return [
            ScoredChunk(
                text=r.payload.get("text", ""),
                score=r.score,
                metadata={
                    "course_title": r.payload.get("course_title", ""),
                    "chapter_title": r.payload.get("chapter_title", ""),
                    "lecture_title": r.payload.get("lecture_title", ""),
                    "lecture_order": r.payload.get("lecture_order", 0),
                    "lecture_id": r.payload.get("lecture_id", ""),
                    "chunk_index": r.payload.get("chunk_index", 0),
                    "timestamp_start": r.payload.get("timestamp_start", "00:00:00"),
                    "timestamp_end": r.payload.get("timestamp_end", "00:00:00"),
                    "duration_seconds": r.payload.get("duration_seconds", 0),
                    "player_embed_url": r.payload.get("player_embed_url", ""),
                }
            )
            for r in results
        ]

    def search_current_lecture(
        self,
        query_vector: list,
        course_title: str,
        lecture_order: int = None,
        top_k: int = 5,
        lecture_id: Optional[str] = None
    ) -> List[ScoredChunk]:
        """Search STRICTLY within the current lecture.

        Prefers lecture_id for exact matching — it is a stable identifier
        across CSV and Qdrant data sources, avoiding the off-by-one mismatch
        that arises when the frontend sends a 0-based lecture_order while
        Qdrant stores 1-based sequential values from the ingestion script.

        Falls back to lecture_order if lecture_id is not provided.
        """
        if lecture_id:
            id_condition = FieldCondition(
                key="lecture_id",
                match=MatchValue(value=lecture_id)
            )
        else:
            id_condition = FieldCondition(
                key="lecture_order",
                match=MatchValue(value=lecture_order)
            )

        search_filter = Filter(
            must=[
                id_condition,
                FieldCondition(
                    key="course_title",
                    match=MatchValue(value=course_title)
                )
            ]
        )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query_filter=search_filter,
            query=query_vector,
            limit=top_k
        ).points

        return [
            ScoredChunk(
                text=r.payload.get("text", ""),
                score=r.score,
                metadata={
                    "course_title": r.payload.get("course_title", ""),
                    "chapter_title": r.payload.get("chapter_title", ""),
                    "lecture_title": r.payload.get("lecture_title", ""),
                    "lecture_order": r.payload.get("lecture_order", 0),
                    "lecture_id": r.payload.get("lecture_id", ""),
                    "chunk_index": r.payload.get("chunk_index", 0),
                    "timestamp_start": r.payload.get("timestamp_start", "00:00:00"),
                    "timestamp_end": r.payload.get("timestamp_end", "00:00:00"),
                    "duration_seconds": r.payload.get("duration_seconds", 0),
                    "player_embed_url": r.payload.get("player_embed_url", ""),
                }
            )
            for r in results
        ]

    def get_lecture_order_by_id(self, lecture_id: str) -> Optional[int]:
        """Look up the Qdrant-side lecture_order for a given lecture_id.

        Uses scroll() for a metadata-only lookup — no semantic query needed.
        This resolves the 0-based (frontend) vs 1-based (Qdrant) mismatch
        deterministically, unlike the previous probe-based approach which
        relied on semantic similarity and could fail for generic queries.

        Returns the lecture_order integer, or None if not found.
        """
        try:
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="lecture_id",
                            match=MatchValue(value=lecture_id)
                        )
                    ]
                ),
                limit=1,
                with_payload=["lecture_order"]
            )
            if results:
                return results[0].payload.get("lecture_order")
        except Exception:
            pass
        return None

    def health_check(self) -> bool:
        """Check if Qdrant is reachable and collection exists."""
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            return self.collection_name in collections
        except Exception:
            return False
