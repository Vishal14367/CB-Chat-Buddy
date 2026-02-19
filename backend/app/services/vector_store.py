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

    # ---- Course catalog methods (used in RAG mode instead of CSV) ----

    def get_all_courses(self) -> List[Dict[str, Any]]:
        """Extract unique courses from Qdrant with chapter/lecture counts."""
        courses: Dict[str, Dict[str, set]] = {}
        offset = None

        while True:
            results, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=250,
                offset=offset,
                with_payload=["course_title", "chapter_title", "lecture_id"]
            )
            if not results:
                break

            for point in results:
                ct = point.payload.get("course_title", "")
                ch = point.payload.get("chapter_title", "")
                lid = point.payload.get("lecture_id", "")
                if ct not in courses:
                    courses[ct] = {"chapters": set(), "lectures": set()}
                if ch:
                    courses[ct]["chapters"].add(ch)
                if lid:
                    courses[ct]["lectures"].add(lid)

            if offset is None:
                break

        result = []
        for course_title, data in sorted(courses.items()):
            course_id = course_title.lower().replace(' ', '-')
            result.append({
                "course_id": course_id,
                "course_title": course_title,
                "chapter_count": len(data["chapters"]),
                "lecture_count": len(data["lectures"]),
            })
        return result

    def get_course_detail(self, course_title: str) -> Optional[Dict[str, Any]]:
        """Build full course structure (chapters + lectures) from Qdrant."""
        chapters: Dict[str, Dict[str, Dict]] = {}
        chapter_min_order: Dict[str, int] = {}
        offset = None

        while True:
            results, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="course_title",
                            match=MatchValue(value=course_title)
                        )
                    ]
                ),
                limit=250,
                offset=offset,
                with_payload=[
                    "course_title", "chapter_title", "lecture_title",
                    "lecture_id", "lecture_order", "player_embed_url",
                    "duration_seconds"
                ]
            )
            if not results:
                break

            for point in results:
                p = point.payload
                ch = p.get("chapter_title", "Unknown Chapter")
                lid = str(p.get("lecture_id", ""))
                lorder = p.get("lecture_order", 0)

                if ch not in chapters:
                    chapters[ch] = {}
                    chapter_min_order[ch] = lorder
                if lorder < chapter_min_order[ch]:
                    chapter_min_order[ch] = lorder

                if lid and lid not in chapters[ch]:
                    chapters[ch][lid] = {
                        "lecture_id": lid,
                        "lecture_title": p.get("lecture_title", ""),
                        "thumbnail_url": p.get("player_embed_url", ""),
                        "duration": p.get("duration_seconds"),
                        "lecture_order": lorder,
                    }

            if offset is None:
                break

        if not chapters:
            return None

        course_id = course_title.lower().replace(' ', '-')
        sorted_chapters = sorted(chapter_min_order.items(), key=lambda x: x[1])

        return {
            "course_id": course_id,
            "course_title": course_title,
            "chapters": [
                {
                    "chapter_title": ch_title,
                    "lectures": sorted(
                        chapters[ch_title].values(),
                        key=lambda x: x["lecture_order"]
                    )
                }
                for ch_title, _ in sorted_chapters
            ]
        }

    def get_lecture_detail(self, lecture_id: str) -> Optional[Dict[str, Any]]:
        """Get lecture metadata + reassembled transcript from Qdrant chunks."""
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
            limit=500,
            with_payload=True
        )

        if not results:
            return None

        sorted_chunks = sorted(results, key=lambda r: r.payload.get("chunk_index", 0))
        first = sorted_chunks[0].payload
        transcript = " ".join(r.payload.get("text", "") for r in sorted_chunks)

        return {
            "lecture_id": lecture_id,
            "lecture_title": first.get("lecture_title", ""),
            "course_title": first.get("course_title", ""),
            "chapter_title": first.get("chapter_title", ""),
            "transcript": transcript,
            "thumbnail_url": first.get("player_embed_url", ""),
            "duration": first.get("duration_seconds"),
            "lecture_order": first.get("lecture_order", 0),
        }

    def health_check(self) -> bool:
        """Check if Qdrant is reachable and collection exists."""
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            return self.collection_name in collections
        except Exception:
            return False
