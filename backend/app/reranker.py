"""Cross-encoder reranker for semantic search results."""

import logging
import os
from typing import List, Optional
import numpy as np

# Model is public - don't use token (clear any invalid cached tokens)
# This prevents 401 errors from invalid tokens
if "HF_TOKEN" in os.environ:
    del os.environ["HF_TOKEN"]
if "HUGGING_FACE_HUB_TOKEN" in os.environ:
    del os.environ["HUGGING_FACE_HUB_TOKEN"]

from sentence_transformers import CrossEncoder
from .models import RetrievedContext

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Reranker using sentence-transformers cross-encoder."""

    def __init__(self, model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"):
        """
        Initialize the cross-encoder reranker.

        Args:
            model_name: Hugging Face model ID for the cross-encoder
        """
        logger.info(f"Loading cross-encoder model: {model_name}")

        try:
            # Load the cross-encoder model (public model, no auth needed)
            # Explicitly disable auth token to avoid using cached invalid token
            self.model = CrossEncoder(model_name)
            self.model_name = model_name
            logger.info(f"Successfully loaded cross-encoder model: {model_name}")

        except Exception as e:
            logger.error(f"Failed to load cross-encoder model: {e}", exc_info=True)
            raise

    def rerank(
        self,
        question: str,
        contexts: List[RetrievedContext],
        top_k: Optional[int] = None,
    ) -> List[RetrievedContext]:
        """
        Rerank contexts using cross-encoder.

        Args:
            question: The question being asked
            contexts: List of retrieved contexts to rerank
            top_k: Optional limit on results returned

        Returns:
            Reranked list of contexts
        """
        if not contexts:
            logger.warning("No contexts to rerank")
            return []

        logger.info(f"Reranking {len(contexts)} contexts for question: {question[:50]}...")

        try:
            # Prepare question-context pairs - include user name to enable user-message semantic mapping
            # Format: "[User Name] message" matches the embedding format for consistency
            # This allows the reranker to understand queries about users and map messages to users
            pairs = [
                (question, f"[{ctx.message.user_name}] {ctx.message.message}") for ctx in contexts
            ]

            # Get scores from cross-encoder
            scores = self.model.predict(pairs, show_progress_bar=True)

            # Normalize scores to 0-1 range using sigmoid function
            # Cross-encoder outputs raw scores (can be negative)
            # Sigmoid normalizes them to (0, 1) range
            scores_array = np.array(scores)
            normalized_scores = 1.0 / (1.0 + np.exp(-scores_array))  # Sigmoid normalization
            
            # Attach normalized scores and sort
            for ctx, score in zip(contexts, normalized_scores):
                ctx.reranker_score = float(score)

            # Sort by reranker score (descending)
            reranked = sorted(contexts, key=lambda x: x.reranker_score, reverse=True)

            # Update ranks
            for i, ctx in enumerate(reranked):
                ctx.rank = i + 1

            # Apply top_k limit if specified
            if top_k:
                reranked = reranked[:top_k]

            logger.info(
                f"Reranking complete. Top result score: {reranked[0].reranker_score:.4f}"
            )

            return reranked

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            raise


# Global reranker instance
_reranker = None


def get_reranker() -> CrossEncoderReranker:
    """Get or create the reranker."""
    global _reranker
    if _reranker is None:
        logger.info("Creating new CrossEncoderReranker instance")
        _reranker = CrossEncoderReranker()
    return _reranker

