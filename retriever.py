"""Orchestration for the Q&A retrieval pipeline."""

import logging
import time
from typing import List
from datetime import datetime
from models import (
    QuestionRequest,
    AnswerResponse,
    RetrievedContext,
    MessageSource,
    TokenUsageInfo,
)
from embeddings import get_embeddings_client
from vector_store import get_vector_store
from reranker import get_reranker
from llm import get_llm_service
from evaluations import get_evaluation_engine
from config import get_settings

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

        logger.info("QARetriever initialized")

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
            # Step 1: Embed question
            logger.info("[1/5] Embedding question")
            question_embedding = self.embeddings_client.embed_single(request.question)
            logger.debug(f"Question embedding generated ({len(question_embedding)} dims)")

            # Step 2: Retrieve initial candidates
            logger.info(f"[2/5] Retrieving top-{self.top_k_initial} messages")
            initial_contexts = self.vector_store.search(
                question_embedding, top_k=self.top_k_initial
            )
            logger.info(f"Retrieved {len(initial_contexts)} messages")

            for ctx in initial_contexts:
                logger.debug(
                    f"  - [{ctx.message.user_name}] {ctx.message.message[:50]}... (score: {ctx.similarity_score:.4f})"
                )

            # Step 3: Rerank using cross-encoder
            logger.info(f"[3/5] Reranking with cross-encoder to top-{self.top_k_final}")
            reranked_contexts = self.reranker.rerank(
                request.question, initial_contexts, top_k=self.top_k_final
            )
            logger.info(f"Reranked to {len(reranked_contexts)} messages")

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

