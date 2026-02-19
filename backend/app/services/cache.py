"""
3-layer caching service for reducing Groq API usage.

Layer 1: Embedding cache — avoids recomputing embeddings for repeated questions
Layer 2: Semantic response cache — returns cached answers for similar questions
Layer 3: Precomputed Q&A — placeholder for post-launch popular question caching
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List

import numpy as np

from app.services.embedding import EmbeddingService


@dataclass
class EmbeddingCacheEntry:
    """Cached embedding with timestamp."""
    embedding: np.ndarray
    timestamp: float


@dataclass
class SemanticCacheEntry:
    """Cached response with question embedding and scope metadata."""
    question_embedding: np.ndarray
    response_message: str
    response_references: list
    response_type: str
    lecture_order: int
    course_title: str
    timestamp: float


class CacheService:
    """3-layer caching for RAG pipeline responses."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        embedding_ttl_hours: float = 1.0,
        semantic_ttl_hours: float = 24.0,
        similarity_threshold: float = 0.95
    ):
        self.embedding_service = embedding_service
        self._embedding_ttl = embedding_ttl_hours * 3600
        self._semantic_ttl = semantic_ttl_hours * 3600
        self._similarity_threshold = similarity_threshold

        # Layer 1: Embedding cache
        self._embedding_cache: Dict[str, EmbeddingCacheEntry] = {}

        # Layer 2: Semantic response cache
        self._semantic_cache: List[SemanticCacheEntry] = []

        # Stats
        self._embedding_hits = 0
        self._embedding_misses = 0
        self._semantic_hits = 0
        self._semantic_misses = 0
        self._access_count = 0

    def _question_hash(self, question: str) -> str:
        """Hash a question for embedding cache key."""
        normalized = question.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()

    # --- Layer 1: Embedding Cache ---

    def get_embedding(self, question: str) -> Optional[np.ndarray]:
        """Get cached embedding for a question. Returns None on miss."""
        self._access_count += 1
        if self._access_count % 100 == 0:
            self._cleanup_expired()

        key = self._question_hash(question)
        entry = self._embedding_cache.get(key)

        if entry and (time.time() - entry.timestamp) < self._embedding_ttl:
            self._embedding_hits += 1
            return entry.embedding

        self._embedding_misses += 1
        return None

    def store_embedding(self, question: str, embedding: np.ndarray):
        """Store an embedding in the cache."""
        key = self._question_hash(question)
        self._embedding_cache[key] = EmbeddingCacheEntry(
            embedding=embedding,
            timestamp=time.time()
        )

    # --- Layer 2: Semantic Response Cache ---

    def get_semantic_match(
        self,
        question_embedding: np.ndarray,
        lecture_order: int,
        course_title: str
    ):
        """Find a cached response for a semantically similar question.

        Returns a RAGResponse-like object on hit, None on miss.
        Only matches within the same lecture_order + course_title scope.
        """
        now = time.time()

        for entry in self._semantic_cache:
            # Skip expired entries
            if (now - entry.timestamp) >= self._semantic_ttl:
                continue

            # Must match scope
            if entry.lecture_order != lecture_order or entry.course_title != course_title:
                continue

            # Compute cosine similarity
            similarity = float(np.dot(question_embedding, entry.question_embedding))

            if similarity >= self._similarity_threshold:
                self._semantic_hits += 1
                # Return a duck-typed response object
                from app.services.rag import RAGResponse, Reference
                references = []
                for ref_data in entry.response_references:
                    if isinstance(ref_data, Reference):
                        references.append(ref_data)
                    elif isinstance(ref_data, dict):
                        references.append(Reference(**ref_data))

                return RAGResponse(
                    message=entry.response_message,
                    references=references,
                    response_type=entry.response_type,
                    cache_hit=True
                )

        self._semantic_misses += 1
        return None

    def store_response(
        self,
        question_embedding: np.ndarray,
        response,  # RAGResponse
        lecture_order: int,
        course_title: str
    ):
        """Store a response in the semantic cache."""
        # Serialize references
        ref_list = []
        for ref in response.references:
            if hasattr(ref, '__dict__'):
                ref_list.append({
                    "lecture_title": ref.lecture_title,
                    "chapter_title": ref.chapter_title,
                    "timestamp": ref.timestamp,
                    "url": ref.url
                })
            else:
                ref_list.append(ref)

        self._semantic_cache.append(SemanticCacheEntry(
            question_embedding=question_embedding,
            response_message=response.message,
            response_references=ref_list,
            response_type=response.response_type,
            lecture_order=lecture_order,
            course_title=course_title,
            timestamp=time.time()
        ))

    # --- Housekeeping ---

    def _cleanup_expired(self):
        """Remove expired entries from both caches."""
        now = time.time()

        # Clean embedding cache
        expired_keys = [
            k for k, v in self._embedding_cache.items()
            if (now - v.timestamp) >= self._embedding_ttl
        ]
        for k in expired_keys:
            del self._embedding_cache[k]

        # Clean semantic cache
        self._semantic_cache = [
            e for e in self._semantic_cache
            if (now - e.timestamp) < self._semantic_ttl
        ]

    def get_stats(self) -> dict:
        """Return cache statistics for monitoring."""
        return {
            "embedding_cache_size": len(self._embedding_cache),
            "semantic_cache_size": len(self._semantic_cache),
            "embedding_hits": self._embedding_hits,
            "embedding_misses": self._embedding_misses,
            "semantic_hits": self._semantic_hits,
            "semantic_misses": self._semantic_misses,
            "embedding_hit_rate": round(
                self._embedding_hits / max(1, self._embedding_hits + self._embedding_misses) * 100, 1
            ),
            "semantic_hit_rate": round(
                self._semantic_hits / max(1, self._semantic_hits + self._semantic_misses) * 100, 1
            )
        }
