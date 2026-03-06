"""
RAG Pipeline Orchestrator.
Coordinates embedding, vector search, context classification,
LLM generation, and response post-processing.
"""

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, AsyncGenerator

import numpy as np

from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStoreService, ScoredChunk
from app.services.llm import GroqLLMService

logger = logging.getLogger(__name__)


# Thresholds
RELEVANCE_THRESHOLD = 0.35      # Below this = not relevant
HIGH_RELEVANCE_THRESHOLD = 0.7  # Above this = use fewer chunks (save tokens)
CURRENT_LECTURE_MIN_SCORE = 0.30  # Below this for current lecture = topic not covered here
REPHRASE_SIMILARITY_THRESHOLD = 0.6  # Above this = user is rephrasing a redirected question

# Response types that indicate a redirect
REDIRECT_RESPONSE_TYPES = {"off_topic", "covered_elsewhere", "future_topic", "blocked"}

# SQL injection patterns — always blocked (never appropriate in a learning chatbot)
_SQL_INJECTION_PATTERNS = re.compile(
    r"(?i)"
    r"(;\s*(DROP|DELETE|TRUNCATE|ALTER|INSERT|UPDATE|EXEC)\b)"
    r"|(\bUNION\s+(ALL\s+)?SELECT\b)"
    r"|('+\s*(OR|AND)\s+['\d].*=)"
    r"|(\bEXEC\s*\()"
    r"|(xp_cmdshell)"
    r"|(INFORMATION_SCHEMA)"
    r"|(\bSLEEP\s*\()"
    r"|(\bBENCHMARK\s*\()"
)

# Dangerous patterns in LLM output — triggers safety disclaimer
_DANGEROUS_OUTPUT_PATTERNS = re.compile(
    r"(?i)"
    r"(DROP\s+(TABLE|DATABASE|INDEX|VIEW|SCHEMA)\s+\w+)"
    r"|(TRUNCATE\s+TABLE\s+\w+)"
    r"|(DELETE\s+FROM\s+\w+\s*;)"
    r"|(ALTER\s+TABLE\s+\w+\s+DROP\b)"
)

_SAFETY_DISCLAIMER = (
    "\n\n**Safety Note:** The SQL above includes destructive operations. "
    "Always test on a backup or staging environment first. "
    "Never run DROP, DELETE, or TRUNCATE on production data without a verified backup."
)


@dataclass
class Reference:
    """A lecture reference with timestamp deep-link."""
    lecture_title: str
    chapter_title: str
    timestamp: str    # "02:15" display format
    url: str          # Vimeo deep-link with #t=Xs


@dataclass
class RAGResponse:
    """Complete RAG pipeline response."""
    message: str
    references: List[Reference] = field(default_factory=list)
    response_type: str = "in_scope"  # "in_scope", "covered_elsewhere", "future_topic", "off_topic"
    cache_hit: bool = False
    tokens_used: Optional[int] = None


class RAGPipeline:
    """Orchestrates the full RAG pipeline for answering learner questions."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreService,
        llm_service: GroqLLMService,
        rate_limiter=None,
        cache_service=None
    ):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.llm_service = llm_service
        self.rate_limiter = rate_limiter
        self.cache = cache_service

    async def process_question(
        self,
        question: str,
        course_title: str,
        current_lecture_order: int,
        lecture_id: str,
        api_key: str,
        history: List[Dict[str, str]] = None,
        chapter_title: str = "",
        lecture_title: str = ""
    ) -> RAGResponse:
        """Process a learner question through the full RAG pipeline.

        Steps:
        1. Enrich query + embed
        2. Search Qdrant with lecture_order filter (Pass 1)
        3. Classify: in-scope, future-topic, or off-topic
        4. Build context string
        5. Call LLM with fallback
        6. Post-process response
        7. Return RAGResponse
        """
        correlation_id = str(uuid.uuid4())[:8]
        logger.info(
            f"[{correlation_id}] RAG request: lecture_id={lecture_id} | course={course_title}"
        )

        # Step 0: Pre-filter for SQL injection patterns
        block_message = self._check_dangerous_query(question)
        if block_message:
            return RAGResponse(message=block_message, response_type="blocked")

        # Step 1: Enrich query with lecture context for better semantic matching.
        # "What is this lecture about?" has no useful signal for the embedding model.
        # Prepending the chapter + lecture title gives it the semantic anchor it needs.
        enriched_query = question
        if chapter_title and lecture_title:
            enriched_query = f"[{chapter_title} - {lecture_title}]: {question}"
        elif lecture_title:
            enriched_query = f"[{lecture_title}]: {question}"

        embedding = None
        if self.cache:
            embedding = self.cache.get_embedding(enriched_query)

        if embedding is None:
            embedding = self.embedding_service.encode(enriched_query)
            if self.cache:
                self.cache.store_embedding(enriched_query, embedding)

        query_vector = embedding.tolist()

        # Step 1.5: Check semantic cache using RAW question embedding.
        # We must NOT use the enriched embedding for cache lookup because the
        # lecture prefix dominates the vector, making all questions about the
        # same lecture appear similar (>0.92 cosine), causing false cache hits.
        raw_embedding = self.embedding_service.encode(question)

        # Redirect persistence — block rephrased off-topic questions
        redirect_msg = self._is_redirect_persistence(raw_embedding, history or [])
        if redirect_msg:
            return RAGResponse(message=redirect_msg, response_type="off_topic")

        if self.cache:
            cached = self.cache.get_semantic_match(
                raw_embedding, current_lecture_order, course_title
            )
            if cached:
                cached.cache_hit = True
                return cached

        # Step 2: Check rate limiter
        if self.rate_limiter:
            rate_status = await self.rate_limiter.acquire()
            if rate_status.status == "blocked":
                return RAGResponse(
                    message=rate_status.message,
                    response_type="rate_limited"
                )
            if rate_status.status == "cached_only":
                return RAGResponse(
                    message=rate_status.message,
                    response_type="rate_limited"
                )

        # Step 3: Dual-Search Strategy (Current Priority + Broader Context)
        chunks = self._perform_dual_search(
            query_vector, course_title, current_lecture_order, question, lecture_id, correlation_id
        )

        logger.info(
            f"[{correlation_id}] Search returned {len(chunks)} chunks | top_scores={[f'{c.score:.3f}' for c in chunks[:3]]}"
        )

        # Conversation drift detection — count consecutive redirects for escalation
        redirect_count = self._count_consecutive_redirects(history or [])

        # Step 4: Classify the response type (pass intent so "previous" queries aren't rejected)
        detected_intent = self._detect_intent(question)
        response_type, chunks_to_use = self._classify_results(
            chunks, query_vector, course_title, intent=detected_intent,
            current_lecture_id=lecture_id
        )

        if response_type == "off_topic":
            return RAGResponse(
                message=self._off_topic_message(course_title, redirect_count),
                response_type="off_topic"
            )

        if response_type == "covered_elsewhere":
            elsewhere_info = ""
            if chunks_to_use:
                ec = chunks_to_use[0]
                elsewhere_info = (
                    f" in **{ec.metadata.get('lecture_title', '')}** "
                    f"(Chapter: {ec.metadata.get('chapter_title', '')})"
                )
            return RAGResponse(
                message=self._covered_elsewhere_message(course_title, elsewhere_info, redirect_count),
                response_type="covered_elsewhere"
            )

        if response_type == "future_topic":
            # Get info about which future lecture covers this
            future_chunks = self.vector_store.search_all_lectures(
                query_vector=query_vector,
                course_title=course_title,
                top_k=1
            )
            future_info = ""
            if future_chunks:
                fc = future_chunks[0]
                future_info = (
                    f" in **{fc.metadata['lecture_title']}** "
                    f"(Chapter: {fc.metadata['chapter_title']})"
                )
            return RAGResponse(
                message=self._future_topic_message(course_title, future_info, redirect_count),
                response_type="future_topic"
            )

        # Step 5: Extract current lecture info from chunks
        current_chapter = ""
        current_lecture = ""
        if chunks_to_use:
            for c in chunks_to_use:
                if c.metadata.get("lecture_id") == lecture_id:
                    current_chapter = c.metadata.get("chapter_title", "")
                    current_lecture = c.metadata.get("lecture_title", "")
                    break
            if not current_lecture and chunks_to_use:
                current_chapter = chunks_to_use[0].metadata.get("chapter_title", "")
                current_lecture = chunks_to_use[0].metadata.get("lecture_title", "")

        # Step 6: Build context string with current lecture awareness
        context_string = self._build_context_string(
            chunks_to_use,
            course_title=course_title,
            chapter_title=current_chapter,
            lecture_title=current_lecture,
            current_lecture_order=current_lecture_order,
            current_lecture_id=lecture_id
        )

        # Step 7: Call LLM (non-streaming)
        try:
            response_text, tokens_used = await self._call_llm(
                api_key=api_key,
                query=question,
                context_string=context_string,
                course_title=course_title,
                chapter_title=current_chapter,
                lecture_title=current_lecture,
                history=history
            )
        except Exception as e:
            return RAGResponse(
                message=str(e),
                response_type="error"
            )

        # Record rate limit usage
        if self.rate_limiter and tokens_used:
            self.rate_limiter.record_usage(tokens_used)

        # Step 8: Build references (only from other lectures) and post-process
        references = self._build_references(chunks_to_use, current_lecture_order, lecture_id)
        response_text = self._post_process_response(
            response_text, chunks_to_use, current_lecture_order, lecture_id
        )

        # Post-filter: append safety disclaimer if LLM output contains dangerous SQL
        safety_addendum = self._post_filter_safety(response_text)
        if safety_addendum:
            response_text += safety_addendum

        result = RAGResponse(
            message=response_text,
            references=references,
            response_type="in_scope",
            tokens_used=tokens_used
        )

        # Store in semantic cache (use raw embedding, not enriched)
        if self.cache:
            self.cache.store_response(
                raw_embedding, result, current_lecture_order, course_title
            )

        return result

    def _detect_struggle(self, history: List[Dict[str, str]], current_question: str) -> bool:
        """Detect if learner has asked about the same topic 3+ times.

        Uses embedding similarity to cluster recent user questions.
        Returns True if the current question is semantically similar to 2+ previous questions.
        """
        if not history or len(history) < 4:  # Need at least 2 prior Q&A pairs
            return False

        user_questions = [m['content'] for m in history if m['role'] == 'user']
        if len(user_questions) < 2:
            return False

        try:
            current_emb = self.embedding_service.encode(current_question)
            similar_count = 0
            # Check last 6 user questions for topic overlap
            for q in user_questions[-6:]:
                q_emb = self.embedding_service.encode(q)
                similarity = float(np.dot(current_emb, q_emb))
                if similarity > 0.7:  # Same topic threshold
                    similar_count += 1

            return similar_count >= 2  # Current + 2 previous = 3 total
        except Exception:
            return False

    async def process_question_stream(
        self,
        question: str,
        course_title: str,
        current_lecture_order: int,
        lecture_id: str,
        api_key: str,
        history: List[Dict[str, str]] = None,
        chapter_title: str = "",
        lecture_title: str = "",
        teaching_mode: str = "fix",
        response_style: str = "casual",
        hint_stage: int = 1,
        image_context: str = ""
    ) -> AsyncGenerator[str, None]:
        """Stream the RAG response as SSE events.

        Yields JSON-formatted SSE events:
        - {"type": "token", "content": "..."} for each token
        - {"type": "done", "references": [...], "responseType": "..."} at end
        """
        # Natural typing delay: pause 2-3s before first token so the bot
        # feels like it's "thinking" rather than replying instantly.
        await asyncio.sleep(2 + (hash(question) % 1000) / 1000)  # 2.0-2.999s

        correlation_id = str(uuid.uuid4())[:8]

        # Step 0: Pre-filter for SQL injection patterns (block before any processing)
        block_message = self._check_dangerous_query(question)
        if block_message:
            yield f"data: {json.dumps({'type': 'token', 'content': block_message})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'blocked'})}\n\n"
            return

        # Step 1: Enrich query with lecture context for better semantic matching
        enriched_query = question
        if chapter_title and lecture_title:
            enriched_query = f"[{chapter_title} - {lecture_title}]: {question}"
        elif lecture_title:
            enriched_query = f"[{lecture_title}]: {question}"

        embedding = None
        if self.cache:
            embedding = self.cache.get_embedding(enriched_query)

        if embedding is None:
            embedding = self.embedding_service.encode(enriched_query)
            if self.cache:
                self.cache.store_embedding(enriched_query, embedding)

        query_vector = embedding.tolist()

        # Check semantic cache using RAW question embedding (not enriched).
        # The enriched prefix dominates the vector, causing false cache hits.
        raw_embedding = self.embedding_service.encode(question)

        # Step 1.5: Redirect persistence — block rephrased off-topic questions
        redirect_msg = self._is_redirect_persistence(raw_embedding, history or [])
        if redirect_msg:
            yield f"data: {json.dumps({'type': 'token', 'content': redirect_msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'off_topic'})}\n\n"
            return

        if self.cache:
            cached = self.cache.get_semantic_match(
                raw_embedding, current_lecture_order, course_title
            )
            if cached:
                # Stream the cached response token by token for consistent UX
                for word in cached.message.split(' '):
                    yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
                refs = [
                    {"lecture_title": r.lecture_title, "chapter_title": r.chapter_title,
                     "timestamp": r.timestamp, "url": r.url}
                    for r in cached.references
                ]
                yield f"data: {json.dumps({'type': 'done', 'references': refs, 'responseType': cached.response_type, 'cacheHit': True})}\n\n"
                return

        # Check rate limiter
        if self.rate_limiter:
            rate_status = await self.rate_limiter.acquire()
            if rate_status.status in ("blocked", "cached_only"):
                yield f"data: {json.dumps({'type': 'token', 'content': rate_status.message})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'rate_limited'})}\n\n"
                return

        # Search Qdrant (Dual-Search Strategy)
        chunks = self._perform_dual_search(
            query_vector, course_title, current_lecture_order, question, lecture_id
        )

        logger.debug(
            "Stream search returned %d chunks: %s",
            len(chunks),
            [(f"{c.score:.3f}", c.metadata.get('lecture_title', ''),
              c.metadata.get('lecture_order')) for c in chunks[:5]]
        )

        # Conversation drift detection — count consecutive redirects for escalation
        redirect_count = self._count_consecutive_redirects(history or [])

        # Classify (pass intent so "previous" queries aren't rejected)
        stream_intent = self._detect_intent(question)
        response_type, chunks_to_use = self._classify_results(
            chunks, query_vector, course_title, intent=stream_intent,
            current_lecture_id=lecture_id
        )

        if response_type == "off_topic":
            msg = self._off_topic_message(course_title, redirect_count)
            yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'off_topic'})}\n\n"
            return

        if response_type == "covered_elsewhere":
            elsewhere_info = ""
            if chunks_to_use:
                ec = chunks_to_use[0]
                elsewhere_info = (
                    f" in **{ec.metadata.get('lecture_title', '')}** "
                    f"(Chapter: {ec.metadata.get('chapter_title', '')})"
                )
            msg = self._covered_elsewhere_message(course_title, elsewhere_info, redirect_count)
            yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'covered_elsewhere'})}\n\n"
            return

        if response_type == "future_topic":
            future_chunks = self.vector_store.search_all_lectures(
                query_vector=query_vector,
                course_title=course_title,
                top_k=1
            )
            future_info = ""
            if future_chunks:
                fc = future_chunks[0]
                future_info = (
                    f" in **{fc.metadata['lecture_title']}** "
                    f"(Chapter: {fc.metadata['chapter_title']})"
                )
            msg = self._future_topic_message(course_title, future_info, redirect_count)
            yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'future_topic'})}\n\n"
            return

        # Extract current lecture info
        current_chapter = ""
        current_lecture = ""
        if chunks_to_use:
            for c in chunks_to_use:
                if c.metadata.get("lecture_id") == lecture_id:
                    current_chapter = c.metadata.get("chapter_title", "")
                    current_lecture = c.metadata.get("lecture_title", "")
                    break
            if not current_lecture and chunks_to_use:
                current_chapter = chunks_to_use[0].metadata.get("chapter_title", "")
                current_lecture = chunks_to_use[0].metadata.get("lecture_title", "")

        # Build context with current lecture awareness
        context_string = self._build_context_string(
            chunks_to_use,
            course_title=course_title,
            chapter_title=current_chapter,
            lecture_title=current_lecture,
            current_lecture_order=current_lecture_order,
            current_lecture_id=lecture_id
        )

        # Prepend screenshot analysis if available
        if image_context:
            context_string = (
                f"[Screenshot Analysis]\n{image_context}\n\n"
                + context_string
            )

        # Detect struggle (topic repetition in history)
        is_struggling = self._detect_struggle(history or [], question)

        # Stream LLM response
        references = self._build_references(chunks_to_use, current_lecture_order, lecture_id)
        full_response = ""

        try:
            async for token in self.llm_service.generate_response_stream(
                api_key=api_key,
                query=question,
                context_string=context_string,
                course_title=course_title,
                chapter_title=current_chapter,
                lecture_title=current_lecture,
                history=history,
                teaching_mode=teaching_mode,
                response_style=response_style,
                hint_stage=hint_stage,
                is_struggling=is_struggling,
                has_screenshot=bool(image_context)
            ):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
                logger.error(f"[{correlation_id}] LLM streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'content': 'An error occurred while generating the response. Please try again.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'error'})}\n\n"
                return

        # Post-filter: append safety disclaimer if LLM output contains dangerous SQL
        safety_addendum = self._post_filter_safety(full_response)
        if safety_addendum:
            full_response += safety_addendum
            yield f"data: {json.dumps({'type': 'token', 'content': safety_addendum})}\n\n"

        # Send done event with references
        refs = [
            {"lecture_title": r.lecture_title, "chapter_title": r.chapter_title,
             "timestamp": r.timestamp, "url": r.url}
            for r in references
        ]
        # Only show reference chips when answer spans multiple lectures
        show_references = len(set(c.metadata.get('lecture_id') for c in chunks_to_use)) > 1
        yield f"data: {json.dumps({'type': 'done', 'references': refs, 'responseType': 'in_scope', 'showReferences': show_references})}\n\n"

        # Store in cache (use raw embedding, not enriched)
        if self.cache and full_response:
            result = RAGResponse(
                message=full_response,
                references=references,
                response_type="in_scope"
            )
            self.cache.store_response(
                raw_embedding, result, current_lecture_order, course_title
            )

    def _classify_results(
        self,
        chunks: List[ScoredChunk],
        query_vector: list,
        course_title: str,
        correlation_id: str = "N/A",
        intent: str = "default",
        current_lecture_id: str = ""
    ) -> tuple:
        """Classify search results into in-scope, covered-elsewhere, future-topic, or off-topic.

        Returns (response_type, chunks_to_use)
        """
        # When intent is "previous", "current", or "specific_lecture" and we got
        # chunks, trust the intent detection even if scores are low.
        # Meta-questions like "what is this lecture about?" or "what was previous
        # lecture?" have inherently low semantic similarity to actual transcript
        # content, but the user's intent is unambiguous — never classify as off-topic.
        if intent in ("previous", "current", "specific_lecture") and chunks:
            return "in_scope", chunks[:5]

        if not chunks or chunks[0].score < RELEVANCE_THRESHOLD:
            # Pass 2: Search without lecture_order filter
            all_chunks = self.vector_store.search_all_lectures(
                query_vector=query_vector,
                course_title=course_title,
                top_k=3
            )

            if all_chunks and all_chunks[0].score >= RELEVANCE_THRESHOLD:
                return "future_topic", []
            else:
                return "off_topic", []

        # In-scope: decide how many chunks to use
        if chunks[0].score >= HIGH_RELEVANCE_THRESHOLD:
            chunks_to_use = chunks[:3]
        else:
            chunks_to_use = chunks[:5]

        # Cross-lecture leak detection (guardrail):
        # If the question matches OTHER lectures but NOT the current lecture,
        # classify as "covered_elsewhere" instead of "in_scope".
        # This prevents the bot from acting as a general tutor using
        # cross-lecture content when the topic isn't in the current lecture.
        if current_lecture_id and intent == "default":
            current_chunks = [
                c for c in chunks_to_use
                if c.metadata.get('lecture_id') == current_lecture_id
            ]
            other_chunks = [
                c for c in chunks_to_use
                if c.metadata.get('lecture_id') != current_lecture_id
            ]
            best_current = max((c.score for c in current_chunks), default=0)

            if best_current < CURRENT_LECTURE_MIN_SCORE and other_chunks:
                logger.info(
                    f"[{correlation_id}] Cross-lecture leak detected: "
                    f"best_current={best_current:.3f} < {CURRENT_LECTURE_MIN_SCORE}, "
                    f"other_chunks={len(other_chunks)} -> covered_elsewhere"
                )
                return "covered_elsewhere", other_chunks[:1]

        return "in_scope", chunks_to_use

    def _build_context_string(
        self,
        chunks: List[ScoredChunk],
        course_title: str = "",
        chapter_title: str = "",
        lecture_title: str = "",
        current_lecture_order: int = None,
        current_lecture_id: str = ""
    ) -> str:
        """Format retrieved chunks as structured context for the LLM.

        Groups current-lecture excerpts first, then previous-lecture excerpts,
        with clear labels and counts so the LLM knows exactly what to prioritize.
        """
        if not chunks:
            return ""

        # Separate chunks into current vs previous
        current_parts = []
        previous_parts = []
        for chunk in chunks:
            meta = chunk.metadata
            chunk_lecture = meta.get('lecture_title', '')
            is_current = bool(current_lecture_id and meta.get('lecture_id') == current_lecture_id)

            label_prefix = "Current Lecture" if is_current else "Previous Lecture"
            label = f"{label_prefix}: {chunk_lecture} (Chapter: {meta.get('chapter_title', '')})"
            part = (
                f"[{label}]\n"
                f"[Timestamp: {meta.get('timestamp_start', '')} - {meta.get('timestamp_end', '')}]\n"
                f"\"{chunk.text}\""
            )
            if is_current:
                current_parts.append(part)
            else:
                previous_parts.append(part)

        header = (
            f"---\n"
            f"CURRENT CONTEXT:\n"
            f"Course: {course_title}\n"
            f"Chapter: {chapter_title}\n"
            f"Lecture: {lecture_title} (the learner is currently watching THIS lecture)\n"
            f"Current lecture excerpts: {len(current_parts)}, Previous lecture excerpts: {len(previous_parts)}\n\n"
            f"RELEVANT TRANSCRIPT EXCERPTS:\n\n"
        )

        # Group current first, then previous with divider
        all_parts = current_parts[:]
        if previous_parts:
            all_parts.append("--- (Previous lectures for additional context) ---")
            all_parts.extend(previous_parts)

        if previous_parts:
            footer = "\n\nNote: Some excerpts are from previous lectures. Prioritize current lecture content. When referencing previous content, mention the lecture name naturally."
        else:
            footer = "\n\nNote: All excerpts are from the current lecture. Focus your answer on this lecture's content only."

        return header + "\n\n".join(all_parts) + footer + "\n---"

    def _build_references(
        self,
        chunks: List[ScoredChunk],
        current_lecture_order: int = None,
        current_lecture_id: str = ""
    ) -> List[Reference]:
        """Build structured references from retrieved chunks.

        Only includes references from OTHER lectures — the learner is already
        watching the current lecture, so linking back to it adds no value.
        """
        seen = set()
        references = []

        for chunk in chunks:
            meta = chunk.metadata

            # Skip references from the current lecture (user is already watching it)
            if current_lecture_id and meta.get('lecture_id') == current_lecture_id:
                continue

            key = (meta.get('lecture_title', ''), meta.get('timestamp_start', ''))
            if key in seen:
                continue
            seen.add(key)

            start_seconds = self._timestamp_to_seconds(meta.get('timestamp_start', '00:00:00'))
            player_url = meta.get('player_embed_url', '')
            url = f"{player_url}#t={start_seconds}s" if player_url else ""

            # Display timestamp without leading "00:" or millisecond decimals
            ts = meta.get('timestamp_start', '00:00:00')
            display_ts = ts[3:] if ts.startswith('00:') else ts
            if '.' in display_ts:
                display_ts = display_ts.split('.')[0]

            references.append(Reference(
                lecture_title=meta.get('lecture_title', ''),
                chapter_title=meta.get('chapter_title', ''),
                timestamp=display_ts,
                url=url
            ))

        return references

    def _post_process_response(
        self,
        llm_text: str,
        chunks: List[ScoredChunk],
        current_lecture_order: int = None,
        current_lecture_id: str = ""
    ) -> str:
        """Post-process LLM output to inject hyperlinks for previous lecture references.

        Only linkifies lecture names from OTHER lectures — linking back to the
        current lecture is unnecessary noise.
        """
        for chunk in chunks:
            meta = chunk.metadata

            # Skip current lecture — don't linkify it
            if current_lecture_id and meta.get('lecture_id') == current_lecture_id:
                continue

            lecture_name = meta.get('lecture_title', '')
            if lecture_name and lecture_name in llm_text:
                start_seconds = self._timestamp_to_seconds(meta.get('timestamp_start', '00:00:00'))
                player_url = meta.get('player_embed_url', '')
                if player_url:
                    url = f"{player_url}#t={start_seconds}s"
                    llm_text = llm_text.replace(
                        lecture_name,
                        f"[{lecture_name}]({url})",
                        1
                    )
        return llm_text

    async def _call_llm(
        self,
        api_key: str,
        query: str,
        context_string: str,
        course_title: str,
        chapter_title: str,
        lecture_title: str,
        history: List[Dict[str, str]] = None
    ) -> tuple:
        """Call LLM with model fallback. Returns (response_text, tokens_used)."""
        models = [
            GroqLLMService.MODEL_HEAVY,     # 70b — best persona adherence
            GroqLLMService.MODEL_PRIMARY,   # 8b — fast fallback
            GroqLLMService.MODEL_FALLBACK   # gemma2 — last resort
        ]

        last_error = None
        for model in models:
            try:
                response_text, tokens_used = self.llm_service.generate_response_v2(
                    api_key=api_key,
                    query=query,
                    context_string=context_string,
                    course_title=course_title,
                    chapter_title=chapter_title,
                    lecture_title=lecture_title,
                    history=history,
                    model=model
                )
                return response_text, tokens_used
            except Exception as e:
                last_error = e
                if "429" in str(e) and model != models[-1]:
                    continue
                raise

        raise last_error

    @staticmethod
    def _timestamp_to_seconds(ts: str) -> int:
        """Convert "00:02:15" or "00:02:15.400" to integer seconds."""
        try:
            parts = ts.split(':')
            if len(parts) == 3:
                h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
                return int(h * 3600 + m * 60 + s)
            elif len(parts) == 2:
                m, s = int(parts[0]), float(parts[1])
                return int(m * 60 + s)
        except (ValueError, IndexError):
            pass
        return 0

    def _off_topic_message(self, course_title: str, redirect_count: int = 0) -> str:
        """Generate a friendly off-topic response with escalating firmness."""
        if redirect_count >= 3:
            return (
                f"I can only help with {course_title} content, specifically the current lecture. "
                f"Every off-topic question uses your limited tokens without adding value. "
                f"What from the current lecture can I help you with?"
            )
        if redirect_count >= 1:
            return (
                f"This one's still outside my scope! I'm here for {course_title} "
                f"and the current lecture only. Let's make your tokens count. "
                f"What from the current lecture can I help with?"
            )
        return (
            f"Hmm, that's actually outside what I can help with. "
            f"I'm here specifically for the {course_title} course. "
            f"But hey, any doubts on the current lecture I can help you nail!"
        )

    def _future_topic_message(self, course_title: str, future_info: str, redirect_count: int = 0) -> str:
        """Generate a friendly future-topic response with escalating firmness."""
        if redirect_count >= 3:
            return (
                f"That topic is coming up later{future_info}. "
                f"Your tokens are limited, let's focus on the current lecture."
            )
        return (
            f"Good question! That topic is actually coming up later in the course"
            f"{future_info}. "
            f"You'll get to it soon! For now, let's focus on what we're learning right now. "
            f"Anything about the current lecture I can help with?"
        )

    def _covered_elsewhere_message(self, course_title: str, elsewhere_info: str, redirect_count: int = 0) -> str:
        """Generate a friendly redirect with escalating firmness."""
        if redirect_count >= 3:
            return (
                f"That's covered{elsewhere_info}, not here. "
                f"Your tokens are limited, let's focus on the current lecture."
            )
        if redirect_count >= 1:
            return (
                f"That topic is still outside the current lecture{elsewhere_info}. "
                f"Let's make your tokens count on what we're learning right now!"
            )
        return (
            f"That's actually covered{elsewhere_info}, not in the current lecture. "
            f"Let's save your tokens for what we're learning right now! "
            f"Any doubts on the current lecture I can help with?"
        )

    # ---- Guardrail Methods ----

    @staticmethod
    def _check_dangerous_query(question: str) -> Optional[str]:
        """Pre-filter for SQL injection patterns. Always blocks.

        Returns a block message if the query contains SQL injection attempts.
        Returns None if the query is safe to proceed.

        Design: Only blocks TRUE injection patterns (chained SQL commands,
        UNION SELECT, tautology attacks). Does NOT block educational questions
        ABOUT destructive SQL (e.g. "what does DROP TABLE do?") — those are
        handled by the system prompt + post-filter instead.
        """
        if _SQL_INJECTION_PATTERNS.search(question):
            return (
                "Whoa, that looks like it could be a SQL injection pattern! "
                "I can't help with queries like that. "
                "If you're curious about SQL security, check out the security-related "
                "lectures in your course. "
                "Anything about the current lecture I can help with?"
            )
        return None

    def _is_redirect_persistence(
        self,
        raw_embedding: np.ndarray,
        history: List[Dict[str, str]]
    ) -> Optional[str]:
        """Detect rephrased off-topic attempts after a redirect.

        If the last assistant message had a redirect responseType AND the
        current question is semantically similar to the last user question,
        the user is likely rephrasing the same off-topic question.

        Returns a redirect message if persistence detected, None otherwise.
        """
        if not history or len(history) < 2:
            return None

        # Find the last assistant and user messages
        last_assistant = None
        last_user_question = None
        for msg in reversed(history):
            if msg["role"] == "assistant" and last_assistant is None:
                last_assistant = msg
            elif msg["role"] == "user" and last_user_question is None:
                last_user_question = msg
            if last_assistant and last_user_question:
                break

        if not last_assistant or not last_user_question:
            return None

        # Check if last response was a redirect
        last_response_type = last_assistant.get("responseType")
        if last_response_type not in REDIRECT_RESPONSE_TYPES:
            return None

        # Compare embeddings (raw_embedding is already computed for current question)
        try:
            prev_embedding = self.embedding_service.encode(last_user_question["content"])
            similarity = float(np.dot(raw_embedding, prev_embedding))

            if similarity > REPHRASE_SIMILARITY_THRESHOLD:
                logger.info(
                    "Redirect persistence detected: similarity=%.3f > %.2f, "
                    "previous responseType=%s",
                    similarity, REPHRASE_SIMILARITY_THRESHOLD, last_response_type
                )
                return (
                    "I hear you, but this one's still outside the current lecture scope. "
                    "I want to make sure your tokens go toward the stuff that'll actually "
                    "help you right now. What part of the current lecture can I help with?"
                )
        except Exception:
            pass

        return None

    @staticmethod
    def _count_consecutive_redirects(history: List[Dict[str, str]]) -> int:
        """Count consecutive redirect responses at the end of conversation history.

        Walks backward through assistant messages, counting how many consecutive
        ones have a redirect responseType. Used to escalate redirect firmness.
        """
        count = 0
        for msg in reversed(history):
            if msg["role"] == "assistant":
                if msg.get("responseType") in REDIRECT_RESPONSE_TYPES:
                    count += 1
                else:
                    break  # Non-redirect assistant message breaks the streak
        return count

    @staticmethod
    def _post_filter_safety(response_text: str) -> Optional[str]:
        """Scan LLM response for dangerous SQL patterns, return safety disclaimer if found.

        This is a LAST-RESORT guardrail. The system prompt should prevent most cases,
        but this catches any that slip through. Skips if the LLM already included
        safety language (avoid double-disclaimers).
        """
        if not _DANGEROUS_OUTPUT_PATTERNS.search(response_text):
            return None

        # Check if the response already contains safety language
        disclaimer_keywords = ["backup", "staging", "never run", "production data", "safety note", "test environment"]
        response_lower = response_text.lower()
        if any(kw in response_lower for kw in disclaimer_keywords):
            return None  # LLM already added a disclaimer

        return _SAFETY_DISCLAIMER

    def _resolve_lecture_order(self, lecture_id: str, frontend_order: int) -> int:
        """Deterministically resolve the Qdrant-side lecture_order for a lecture_id.

        The frontend sends 0-based lecture_order (CSV row index), but Qdrant
        stores 1-based sequential values from the ingestion script. This method
        uses a metadata-only lookup (no semantic query) to get the correct value.
        """
        if lecture_id:
            qdrant_order = self.vector_store.get_lecture_order_by_id(lecture_id)
            if qdrant_order is not None:
                logger.info(
                    "Lecture order resolved: lecture_id=%s -> qdrant_order=%s (frontend sent %s)",
                    lecture_id, qdrant_order, frontend_order
                )
                return qdrant_order

        # Heuristic fallback: assume 0-based → 1-based offset
        fallback = frontend_order + 1
        logger.warning(
            "Lecture order fallback: lecture_id=%s not found in Qdrant, "
            "using heuristic %s+1=%s",
            lecture_id, frontend_order, fallback
        )
        return fallback

    @staticmethod
    def _detect_intent(question: str) -> str:
        """Detect whether the user is asking about current, previous, a specific
        other lecture, or general scope.

        Returns: "current", "previous", "specific_lecture", or "default".

        - "specific_lecture": user references a lecture/chapter by number or ordinal
          (e.g. "first lecture", "2nd lecture of 1st chapter", "lecture 3").
          These should search across all accessible lectures, not just the current one.
        - "default": current-lecture-first (the common case).
        """
        q = question.lower()

        # Check for PREVIOUS intent first (explicit widening)
        previous_keywords = [
            "previous lecture", "last lecture", "prev lecture",
            "previous video", "last video", "earlier lecture",
            "pichle lecture", "pichli lecture", "pehle wala",
            "pehle ki lecture", "pichla video",
            "in the last", "in the previous", "from the previous",
            "you said earlier", "you mentioned earlier",
            "earlier you said", "earlier you mentioned",
        ]
        if any(kw in q for kw in previous_keywords):
            return "previous"

        # Check for explicit CURRENT intent
        current_keywords = [
            "this lecture", "current lecture", "this video", "in this video",
            "covered in this", "what is covered", "what was covered",
            "what did we", "what have we", "lecture summary", "overview of this",
            "explain this lecture", "summarize this", "recap", "what topics",
            "what we learned", "what did we learn", "what are we learning",
            "what was taught", "what did you teach", "what are we covering",
            "what did the instructor", "explain the concept",
            "summary", "summarize",
            # Hindi/Hinglish
            "is yahan", "is lecture", "yeh lecture", "ye lecture",
            "ye video", "yeh video", "is video mein", "ye video mein",
            "abhi", "aaj ka", "aaj ki", "kya padha rahe",
            "kya sikha rahe", "is mein",
        ]
        if any(kw in q for kw in current_keywords):
            return "current"

        # Check for SPECIFIC lecture/chapter reference by number or ordinal
        # e.g. "first lecture", "2nd lecture of 1st chapter", "lecture 3",
        #       "chapter 2", "in lecture 5", "pehle chapter mein"
        specific_lecture_patterns = [
            r'\b(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:lecture|video|chapter)',
            r'\b(?:lecture|video|chapter)\s+(?:number\s+)?\d+',
            r'\b\d+(?:st|nd|rd|th)\s+(?:lecture|video|chapter)',
            r'\b(?:in|from|of)\s+(?:lecture|chapter)\s+\d+',
            r'\b\d+(?:st|nd|rd|th)\s+(?:lecture|video)\s+(?:of|in)\s+\d+(?:st|nd|rd|th)\s+chapter',
            # Hindi/Hinglish
            r'\bpehle?\s+(?:lecture|chapter|video)',
            r'\bdusre?\s+(?:lecture|chapter|video)',
            r'\btisre?\s+(?:lecture|chapter|video)',
        ]
        for pattern in specific_lecture_patterns:
            if re.search(pattern, q):
                return "specific_lecture"

        # DEFAULT: treat as current-lecture-first (not "search everything")
        return "default"

    def _perform_dual_search(
        self,
        query_vector: list,
        course_title: str,
        current_lecture_order: int,
        question: str,
        lecture_id: str = "",
        correlation_id: str = "N/A"
    ) -> List[Any]:
        """Execute a dual-search strategy: Current Lecture Priority + Broader Context.

        Key design principles:
        1. Deterministic lecture_order resolution via metadata lookup (not semantic probe)
        2. Default to current lecture scope — only widen on explicit "previous" intent
        3. Current lecture chunks get a score boost to prevent cross-lecture contamination
        4. Minimum current-lecture representation guaranteed in final results
        """
        # Step 0: Resolve lecture_order deterministically
        resolved_order = self._resolve_lecture_order(lecture_id, current_lecture_order)

        # Step 1: Detect intent
        intent = self._detect_intent(question)
        logger.info(
            f"[{correlation_id}] Intent detected: {intent} | resolved_order={resolved_order} (frontend sent {current_lecture_order})"
        )

        # Step 2: Handle explicit PREVIOUS intent
        if intent == "previous" and resolved_order > 1:
            # Use a RAW embedding (without current-lecture enrichment prefix)
            # so the vector isn't biased toward the current lecture content.
            raw_prev_vector = self.embedding_service.encode(question).tolist()
            prev_chunks = self.vector_store.search_current_lecture(
                query_vector=raw_prev_vector,
                course_title=course_title,
                lecture_order=resolved_order - 1,
                top_k=5
            )
            if prev_chunks:
                # For explicit "previous" intent, ALWAYS return previous lecture chunks
                # regardless of score. Meta-questions like "what was previous lecture?"
                # have low semantic overlap with transcript content, but the user's
                # intent is clear — they want content from the previous lecture.
                logger.info(
                    f"[{correlation_id}] Search path: PREVIOUS lecture (order {resolved_order - 1}) "
                    f"| chunks={len(prev_chunks)} | best_score={prev_chunks[0].score:.3f}"
                )
                return prev_chunks
            # Fall through only if that lecture has NO chunks at all in Qdrant
            logger.warning(
                f"[{correlation_id}] No chunks found for previous lecture (order {resolved_order - 1}), falling through"
            )

        # Step 2b: Handle SPECIFIC LECTURE reference (e.g. "first lecture", "lecture 3")
        # User is asking about a specific lecture by number — search across all accessible lectures
        if intent == "specific_lecture":
            raw_vector = self.embedding_service.encode(question).tolist()
            broad_chunks = self.vector_store.search(
                query_vector=raw_vector,
                course_title=course_title,
                max_lecture_order=resolved_order,
                top_k=5
            )
            if broad_chunks:
                logger.info(
                    f"[{correlation_id}] Search path: SPECIFIC_LECTURE (broad across all accessible) "
                    f"| chunks={len(broad_chunks)} | best_score={broad_chunks[0].score:.3f}"
                )
                return broad_chunks
            logger.warning(
                f"[{correlation_id}] No chunks found for specific lecture reference, falling through"
            )

        # Step 3: Search current lecture (always needed)
        if lecture_id:
            current_chunks = self.vector_store.search_current_lecture(
                query_vector=query_vector,
                course_title=course_title,
                lecture_id=lecture_id,
                top_k=5
            )
        else:
            current_chunks = self.vector_store.search_current_lecture(
                query_vector=query_vector,
                course_title=course_title,
                lecture_order=resolved_order,
                top_k=5
            )

        # Step 4: For explicit "current" intent, return current-only
        if intent == "current":
            if current_chunks:
                logger.info(f"[{correlation_id}] Search path: CURRENT lecture only | chunks={len(current_chunks)} | best_score={current_chunks[0].score:.3f}")
                return current_chunks
            # Fall through if current lecture has no chunks (unlikely)

        # Step 5: Analyze current lecture relevance
        best_current_score = current_chunks[0].score if current_chunks else 0

        # If current lecture has good relevance, use mostly current + minor broader context
        if best_current_score > 0.5:
            logger.info(f"[{correlation_id}] Search path: CURRENT+BROAD (current score {best_current_score:.3f} > 0.5)")
            broad_chunks = self.vector_store.search(
                query_vector=query_vector,
                course_title=course_title,
                max_lecture_order=resolved_order,
                top_k=3
            )
            current_ids = {
                (c.metadata.get('lecture_id', ''), c.metadata.get('chunk_index'))
                for c in current_chunks
            }
            unique_broad = [
                c for c in broad_chunks
                if (c.metadata.get('lecture_id', ''), c.metadata.get('chunk_index')) not in current_ids
            ]
            combined = current_chunks[:4] + unique_broad[:1]
            # Boost current lecture scores by 1.3x before sorting
            for c in combined:
                if c.metadata.get('lecture_id') == lecture_id:
                    c.score = min(c.score * 1.3, 1.0)
            combined.sort(key=lambda x: x.score, reverse=True)
            return combined

        # Step 6: Broader search (current lecture relevance is low)
        logger.info(f"[{correlation_id}] Search path: BROAD (current score {best_current_score:.3f} <= 0.5)")
        broad_chunks = self.vector_store.search(
            query_vector=query_vector,
            course_title=course_title,
            max_lecture_order=resolved_order,
            top_k=5
        )

        # Step 7: Intelligent merge with current-lecture priority
        final_chunks = []
        seen_ids = set()

        # Add current lecture chunks first (lowered threshold from 0.4 to 0.3)
        for chunk in current_chunks:
            if chunk.score > 0.3:
                final_chunks.append(chunk)
                seen_ids.add((chunk.metadata.get('lecture_id', ''), chunk.metadata.get('chunk_index')))

        # Fill remaining slots with broader context
        for chunk in broad_chunks:
            c_key = (chunk.metadata.get('lecture_id', ''), chunk.metadata.get('chunk_index'))
            if c_key not in seen_ids:
                final_chunks.append(chunk)
                seen_ids.add(c_key)

        # Boost current lecture scores before final sort
        for c in final_chunks:
            if c.metadata.get('lecture_id') == lecture_id:
                c.score = min(c.score * 1.3, 1.0)

        final_chunks.sort(key=lambda x: x.score, reverse=True)

        # Guarantee minimum 2 current-lecture chunks if available
        current_in_final = [c for c in final_chunks[:5] if c.metadata.get('lecture_id') == lecture_id]
        if len(current_in_final) < 2 and current_chunks:
            remaining_current = [
                c for c in current_chunks
                if (c.metadata.get('lecture_id', ''), c.metadata.get('chunk_index'))
                not in {(x.metadata.get('lecture_id', ''), x.metadata.get('chunk_index')) for x in current_in_final}
            ]
            if remaining_current:
                # Insert at position 2 to ensure current lecture representation
                non_current = [c for c in final_chunks[:5] if c.metadata.get('lecture_id') != lecture_id]
                result = current_in_final + remaining_current[:2 - len(current_in_final)] + non_current
                logger.info(f"[{correlation_id}] Final composition: {len(current_in_final + remaining_current[:2 - len(current_in_final)])} current + {len(non_current[:5 - (len(current_in_final) + len(remaining_current[:2 - len(current_in_final)]))])} other")
                return result[:5]

        current_count = len(current_in_final)
        other_count = len([c for c in final_chunks[:5] if c.metadata.get('lecture_id') != lecture_id])
        logger.info(f"[{correlation_id}] Final composition: {current_count} current + {other_count} other")
        return final_chunks[:5]
