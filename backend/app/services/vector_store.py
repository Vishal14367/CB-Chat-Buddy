"""
Qdrant vector store service for semantic search over transcript chunks.
Supports filtered search by lecture_order and course_title for context scoping.
"""

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue

# Cache TTL: 10 minutes (catalog data rarely changes during a session)
_CACHE_TTL = 600


def _slugify(title: str) -> str:
    """Generate URL-safe slug from course title."""
    slug = title.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


def _natural_sort_key(lecture: dict) -> tuple:
    """Sort by lecture_order, then extract leading number from title as tiebreaker."""
    order = lecture.get("lecture_order", 0)
    title = lecture.get("lecture_title", "")
    match = re.match(r'^(\d+)', title.strip())
    title_num = int(match.group(1)) if match else 999
    return (order, title_num, title)


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

        # In-memory cache for catalog data (avoids scrolling 18k+ points per request)
        self._courses_cache: Optional[List[Dict[str, Any]]] = None
        self._courses_cache_time: float = 0
        self._course_detail_cache: Dict[str, Dict[str, Any]] = {}
        self._course_detail_cache_time: Dict[str, float] = {}
        # Slug → course_title mapping (populated from get_all_courses)
        self._slug_to_title: Dict[str, str] = {}

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
        """Extract unique courses from Qdrant with chapter/lecture counts.

        Results are cached in-memory for _CACHE_TTL seconds to avoid
        scrolling through all ~18k+ points on every page load.
        """
        now = time.time()
        if self._courses_cache and (now - self._courses_cache_time) < _CACHE_TTL:
            return self._courses_cache

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
            course_id = _slugify(course_title)
            result.append({
                "course_id": course_id,
                "course_title": course_title,
                "chapter_count": len(data["chapters"]),
                "lecture_count": len(data["lectures"]),
            })
            self._slug_to_title[course_id] = course_title

        self._courses_cache = result
        self._courses_cache_time = now
        return result

    def resolve_course_title(self, course_id_slug: str) -> Optional[str]:
        """Fast slug-to-title resolution using cached mapping.

        Tries exact match first, then normalized slug, then substring fallback.
        """
        # Try exact match
        if course_id_slug in self._slug_to_title:
            return self._slug_to_title[course_id_slug]

        # Normalize the incoming slug and try again
        normalized = _slugify(course_id_slug.replace('-', ' '))
        if normalized in self._slug_to_title:
            return self._slug_to_title[normalized]

        # Cache miss — populate it
        self.get_all_courses()

        if course_id_slug in self._slug_to_title:
            return self._slug_to_title[course_id_slug]
        if normalized in self._slug_to_title:
            return self._slug_to_title[normalized]

        # Substring fallback for resilience
        for slug, title in self._slug_to_title.items():
            if course_id_slug in slug or slug in course_id_slug:
                return title

        return None

    def get_course_detail(self, course_title: str) -> Optional[Dict[str, Any]]:
        """Build full course structure (chapters + lectures) from Qdrant.

        Results are cached in-memory for _CACHE_TTL seconds.
        """
        now = time.time()
        cached = self._course_detail_cache.get(course_title)
        cached_time = self._course_detail_cache_time.get(course_title, 0)
        if cached and (now - cached_time) < _CACHE_TTL:
            return cached

        chapters: Dict[str, Dict[str, Dict]] = {}       # ch_key -> {lid -> lecture}
        chapter_min_order: Dict[str, int] = {}          # ch_key -> min_order
        chapter_display_title: Dict[str, str] = {}      # ch_key -> first-seen title
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
                ch_key = ch.strip().lower()  # Normalized key for dedup
                lid = str(p.get("lecture_id", ""))
                lorder = p.get("lecture_order", 0)

                if ch_key not in chapters:
                    chapters[ch_key] = {}
                    chapter_min_order[ch_key] = lorder
                    chapter_display_title[ch_key] = ch.strip()
                if lorder < chapter_min_order[ch_key]:
                    chapter_min_order[ch_key] = lorder

                if lid and lid not in chapters[ch_key]:
                    chapters[ch_key][lid] = {
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

        course_id = _slugify(course_title)
        sorted_chapters = sorted(chapter_min_order.items(), key=lambda x: x[1])

        result = {
            "course_id": course_id,
            "course_title": course_title,
            "chapters": [
                {
                    "chapter_title": chapter_display_title[ch_key],
                    "lectures": sorted(
                        chapters[ch_key].values(),
                        key=_natural_sort_key
                    )
                }
                for ch_key, _ in sorted_chapters
            ]
        }

        self._course_detail_cache[course_title] = result
        self._course_detail_cache_time[course_title] = now
        return result

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
