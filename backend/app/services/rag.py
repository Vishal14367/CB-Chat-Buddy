"""
RAG Pipeline Orchestrator.
Coordinates embedding, vector search, context classification,
LLM generation, and response post-processing.
"""

import json
import logging
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
    response_type: str = "in_scope"  # "in_scope", "future_topic", "off_topic"
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
            f"[{correlation_id}] RAG request: question={question[:60]}... | lecture_id={lecture_id} | course={course_title}"
        )
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

        # Step 4: Classify the response type (pass intent so "previous" queries aren't rejected)
        detected_intent = self._detect_intent(question)
        response_type, chunks_to_use = self._classify_results(
            chunks, query_vector, course_title, intent=detected_intent
        )

        if response_type == "off_topic":
            return RAGResponse(
                message=self._off_topic_message(course_title),
                response_type="off_topic"
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
                message=self._future_topic_message(course_title, future_info),
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

        # Classify (pass intent so "previous" queries aren't rejected)
        stream_intent = self._detect_intent(question)
        response_type, chunks_to_use = self._classify_results(
            chunks, query_vector, course_title, intent=stream_intent
        )

        if response_type == "off_topic":
            msg = self._off_topic_message(course_title)
            yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'off_topic'})}\n\n"
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
            msg = self._future_topic_message(course_title, future_info)
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
                error_msg = str(e)
                yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'references': [], 'responseType': 'error'})}\n\n"
                return

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
        intent: str = "default"
    ) -> tuple:
        """Classify search results into in-scope, future-topic, or off-topic.

        Returns (response_type, chunks_to_use)
        """
        # When intent is "previous" and we got chunks, trust the intent detection
        # even if scores are low (meta-questions like "what was previous lecture?"
        # have inherently low semantic similarity to actual transcript content).
        if intent == "previous" and chunks:
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
            # Very relevant top result — use fewer chunks to save tokens
            return "in_scope", chunks[:3]
        else:
            return "in_scope", chunks[:5]

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

            # Display timestamp without leading "00:"
            ts = meta.get('timestamp_start', '00:00:00')
            display_ts = ts[3:] if ts.startswith('00:') else ts

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

    def _off_topic_message(self, course_title: str) -> str:
        """Generate a friendly off-topic response."""
        return (
            f"Hmm, that's actually outside what I can help with. "
            f"I'm here specifically for the {course_title} course. "
            f"But hey, any doubts on the current lecture I can help you nail!"
        )

    def _future_topic_message(self, course_title: str, future_info: str) -> str:
        """Generate a friendly future-topic response."""
        return (
            f"Good question! That topic is actually coming up later in the course"
            f"{future_info}. "
            f"You'll get to it soon! For now, let's focus on what we're learning right now. "
            f"Anything about the current lecture I can help with?"
        )

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
        """Detect whether the user is asking about current, previous, or general scope.

        Returns: "current", "previous", or "default" (which maps to current-first).

        Design principle: Default to current lecture. The vast majority of questions
        a learner asks while watching a lecture are about THAT lecture. Only widen
        scope when explicit "previous"/"last"/"earlier" markers are present.
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
