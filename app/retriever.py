"""Orchestration for the Q&A retrieval pipeline."""

import logging
import time
from typing import List
from datetime import datetime
import numpy as np
from .models import (
    QuestionRequest,
    AnswerResponse,
    RetrievedContext,
    MessageSource,
    TokenUsageInfo,
)
from .embeddings import get_embeddings_client
from .vector_store import get_vector_store
from .reranker import get_reranker
from .llm import get_llm_service
from .evaluations import get_evaluation_engine
from .config import get_settings

logger = logging.getLogger(__name__)


class QARetriever:
    """Orchestrates the question-answering retrieval pipeline."""

    def __init__(self):
        """Initialize the retriever."""
        settings = get_settings()

        self.embeddings_client = get_embeddings_client()
        self.vector_store = get_vector_store()
        self.reranker = get_reranker()
        self.llm_service = get_llm_service()
        self.evaluation_engine = get_evaluation_engine()

        self.top_k_initial = settings.top_k_initial_retrieval
        self.top_k_final = settings.top_k_after_reranking

        # Cache for ALL user name embeddings (full names only - no need for separate first names)
        # Initialized lazily on first query to avoid blocking startup
        self._user_name_embeddings_cache = {}  # {user_name: embedding}
        self._all_user_names = set()  # All known user names
        self._cache_initialized = False  # Track if cache has been initialized

        logger.info("QARetriever initialized")

    def _initialize_user_name_cache(self):
        """Initialize cache with ALL user names and their embeddings from the index."""
        if self._cache_initialized:
            return
        
        logger.info("Initializing user name embeddings cache...")
        
        # Get all unique user names by doing a large search with a dummy vector
        # Use a neutral vector (all zeros) to get diverse results
        dummy_vector = [0.0] * 1024
        all_contexts = self.vector_store.search(dummy_vector, top_k=1000)  # Large number to get all users
        
        # Extract all unique user names
        all_user_names = set(ctx.message.user_name for ctx in all_contexts)
        
        if not all_user_names:
            logger.warning("No user names found in index")
            self._cache_initialized = True
            return
        
        self._all_user_names = all_user_names
        logger.info(f"Found {len(all_user_names)} unique user names in index")
        
        # Embed ALL user names (full names only - no need for separate first names)
        # Semantic similarity naturally handles matching "Sophia" (query) to "Sophia Al-Farsi" (full name)
        user_names_list = list(all_user_names)
        logger.info(f"Embedding {len(user_names_list)} full user names...")
        full_name_embeddings = self.embeddings_client.embed_texts(user_names_list)
        
        # Cache full name embeddings
        for user_name, emb in zip(user_names_list, full_name_embeddings):
            self._user_name_embeddings_cache[user_name] = emb
        
        self._cache_initialized = True
        logger.info(f"User name cache initialized: {len(self._user_name_embeddings_cache)} full names cached")

    async def answer_question(self, request: QuestionRequest) -> AnswerResponse:
        """
        Answer a question using the full retrieval pipeline.

        Args:
            request: Question request

        Returns:
            Answer response with optional sources and evaluations
        """
        logger.info("=" * 80)
        logger.info(f"ANSWERING QUESTION: {request.question}")
        logger.info("=" * 80)

        start_time = time.time()

        try:
            # Step 1: Embed question (pure semantic understanding - no regex/pattern matching)
            logger.info("[1/5] Embedding question")
            question_embedding = self.embeddings_client.embed_single(request.question)
            logger.debug(f"Question embedding generated ({len(question_embedding)} dims)")

            # Step 2: Retrieve initial candidates to detect user-specific queries
            logger.info(f"[2/5] Retrieving top-{self.top_k_initial} messages for initial analysis")
            initial_contexts = self.vector_store.search(
                question_embedding, 
                top_k=self.top_k_initial
            )
            logger.info(f"Retrieved {len(initial_contexts)} messages")
            
            # Analyze user distribution to detect user-specific queries
            user_counts = {}
            for ctx in initial_contexts:
                user_name = ctx.message.user_name
                user_counts[user_name] = user_counts.get(user_name, 0) + 1
            logger.info(f"User distribution in top-{self.top_k_initial}: {dict(sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10])}")

            # Initialize user name cache on first query (lazy loading)
            if not self._cache_initialized:
                self._initialize_user_name_cache()
            
            # Detect if this is a user-specific or multi-user query
            # Use SEMANTIC matching with CACHED embeddings (no embedding on each query!)
            query_lower = request.question.lower()
            mentioned_users = []
            
            # Use cached full name embeddings for semantic matching
            # Semantic similarity naturally handles matching "Sophia" (query) to "Sophia Al-Farsi" (full name)
            logger.debug(f"Checking {len(self._user_name_embeddings_cache)} cached full names for semantic match")
            
            query_emb_array = np.array(question_embedding)
            
            # Compare query with ALL cached full name embeddings
            # The embedding model understands that "Sophia" semantically matches "Sophia Al-Farsi"
            user_similarities = []
            for user_name, name_emb in self._user_name_embeddings_cache.items():
                name_emb_array = np.array(name_emb)
                
                # Cosine similarity
                similarity = np.dot(query_emb_array, name_emb_array) / (
                    np.linalg.norm(query_emb_array) * np.linalg.norm(name_emb_array)
                )
                
                user_similarities.append((user_name, similarity))
            
            # Sort by similarity and use a dynamic threshold
            # Take top-N users with highest similarity, but only if similarity is above a minimum threshold
            user_similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Dynamic threshold: Use top similarity as reference, accept users within 0.2 of top score
            # This ensures we only get users that are actually mentioned, not all users
            if user_similarities:
                top_similarity = user_similarities[0][1]
                # Threshold: Must be within 0.2 of top score AND above 0.5 absolute threshold
                min_threshold = max(0.5, top_similarity - 0.2)
                
                for user_name, similarity in user_similarities:
                    if similarity >= min_threshold:
                        if user_name not in mentioned_users:
                            mentioned_users.append(user_name)
                            logger.debug(f"Semantically matched user '{user_name}' (similarity: {similarity:.3f}, threshold: {min_threshold:.3f})")
                    else:
                        # Stop once we're below threshold (sorted by similarity, so rest will be lower)
                        break
            
            logger.info(f"Semantically detected {len(mentioned_users)} users in query: {mentioned_users}")
            
            # Check if query seems user-specific (contains words like "summarize", "messages", "said", etc.)
            user_specific_keywords = ["summarize", "summarise", "messages", "said", "say", "request", "requests", "asked", "ask", "visited", "visit", "places", "travel"]
            is_user_specific_query = any(keyword in query_lower for keyword in user_specific_keywords)
            
            dominant_user = None
            target_users = []
            
            if mentioned_users and is_user_specific_query:
                if len(mentioned_users) == 1:
                    # Single user query - retrieve ALL their messages
                    dominant_user = mentioned_users[0]
                    logger.info(f"Detected single-user query for '{dominant_user}'. Retrieving ALL messages from this user.")
                    initial_contexts = self.vector_store.search(
                        question_embedding,
                        top_k=500,  # Large number to get all messages from user
                        filter_user_name=dominant_user
                    )
                    logger.info(f"Retrieved {len(initial_contexts)} messages from {dominant_user}")
                else:
                    # Multi-user query - retrieve ALL messages from ALL mentioned users
                    target_users = mentioned_users
                    logger.info(f"Detected multi-user query for {len(target_users)} users: {target_users}. Retrieving ALL messages from each user.")
                    
                    # Collect messages from all mentioned users
                    all_user_contexts = []
                    for user_name in target_users:
                        user_contexts = self.vector_store.search(
                            question_embedding,
                            top_k=500,  # Large number to get all messages from user
                            filter_user_name=user_name
                        )
                        all_user_contexts.extend(user_contexts)
                        logger.info(f"Retrieved {len(user_contexts)} messages from {user_name}")
                    
                    initial_contexts = all_user_contexts
                    logger.info(f"Total retrieved: {len(initial_contexts)} messages from {len(target_users)} users")
            elif user_counts and is_user_specific_query:
                # Fallback: if no explicit user names detected, check if one user dominates
                sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
                top_user, top_count = sorted_users[0]
                user_ratio = top_count / len(initial_contexts) if initial_contexts else 0
                
                # If one user dominates (>50% of results), retrieve ALL their messages
                if user_ratio > 0.5:
                    dominant_user = top_user
                    logger.info(f"Detected user-specific query for '{dominant_user}' ({top_count}/{len(initial_contexts)} = {user_ratio:.1%}). Retrieving ALL messages from this user.")
                    initial_contexts = self.vector_store.search(
                        question_embedding,
                        top_k=500,  # Large number to get all messages from user
                        filter_user_name=dominant_user
                    )
                    logger.info(f"Retrieved {len(initial_contexts)} messages from {dominant_user}")

            for ctx in initial_contexts:
                logger.debug(
                    f"  - [{ctx.message.user_name}] {ctx.message.message[:50]}... (score: {ctx.similarity_score:.4f})"
                )

            # Step 3: Rerank using cross-encoder
            # Always rerank, then apply limit to get top-30 most relevant sources
            # Reranking improves quality by better understanding query-context relevance
            
            logger.info(f"[3/5] Reranking {len(initial_contexts)} messages with cross-encoder")
            
            # Rerank all initial contexts (cross-encoder scores all query-message pairs)
            reranked_all = self.reranker.rerank(
                request.question, initial_contexts, top_k=None  # Rerank all, no limit yet
            )
            
            # Apply limit: use max_sources if specified, otherwise default to 30 for all queries
            top_k_after_rerank = request.max_sources if request.max_sources is not None else 30
            reranked_contexts = reranked_all[:top_k_after_rerank]
            logger.info(f"Reranked to top-{top_k_after_rerank} most relevant messages (from {len(reranked_all)} reranked)")

            for ctx in reranked_contexts:
                logger.debug(
                    f"  - [{ctx.message.user_name}] {ctx.message.message[:50]}... (reranker: {ctx.reranker_score:.4f})"
                )

            # Step 4: Generate answer with LLM
            logger.info("[4/5] Generating answer with LLM")
            answer_text, token_usage = self.llm_service.generate_answer(
                request.question, reranked_contexts
            )
            logger.info(f"Answer generated: {answer_text[:100]}...")

            # Step 5: Evaluate answer (optional)
            evaluations = None
            if request.include_evaluations:
                logger.info("[5/5] Running evaluations")
                try:
                    evaluations = self.evaluation_engine.evaluate(
                        request.question, answer_text, reranked_contexts
                    )
                    logger.info(
                        f"Evaluations complete (avg score: {evaluations.average_score:.2f})"
                    )
                except Exception as e:
                    logger.error(f"Evaluation failed: {e}")
                    # Don't fail the whole pipeline, just skip evaluation

            # Build response
            latency_ms = (time.time() - start_time) * 1000

            sources = None
            if request.include_sources:
                sources = [
                    MessageSource(
                        id=ctx.message.id,
                        user_id=ctx.message.user_id,
                        user_name=ctx.message.user_name,
                        timestamp=ctx.message.timestamp,
                        message=ctx.message.message,
                        similarity_score=ctx.similarity_score,
                        reranker_score=ctx.reranker_score,
                    )
                    for ctx in reranked_contexts
                ]

            # Convert TokenUsage to TokenUsageInfo for response
            token_usage_info = None
            if token_usage:
                token_usage_info = TokenUsageInfo(
                    prompt_tokens=token_usage.prompt_tokens,
                    completion_tokens=token_usage.completion_tokens,
                    total_tokens=token_usage.total_tokens,
                    cost_usd=token_usage.cost_usd,
                )

            response = AnswerResponse(
                answer=answer_text,
                sources=sources,
                evaluations=evaluations,
                latency_ms=latency_ms,
                model_used=self.llm_service.model,
                token_usage=token_usage_info,
            )

            logger.info("=" * 80)
            logger.info(f"QUESTION ANSWERED in {latency_ms:.1f}ms")
            logger.info("=" * 80)

            return response

        except Exception as e:
            logger.error(f"Error in question answering: {e}", exc_info=True)
            raise


# Global retriever instance
_retriever = None


def get_retriever() -> QARetriever:
    """Get or create the retriever."""
    global _retriever
    if _retriever is None:
        logger.info("Creating new QARetriever instance")
        _retriever = QARetriever()
    return _retriever

