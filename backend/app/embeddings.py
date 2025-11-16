"""Embeddings service using sentence-transformers library."""

import logging
import os
from typing import List

# Models are public - clear any invalid tokens to avoid 401 errors
if "HF_TOKEN" in os.environ:
    del os.environ["HF_TOKEN"]
if "HUGGING_FACE_HUB_TOKEN" in os.environ:
    del os.environ["HUGGING_FACE_HUB_TOKEN"]

from sentence_transformers import SentenceTransformer
from .config import get_settings

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingsClient:
    """Client for sentence-transformers embeddings (local model)."""

    def __init__(self):
        """Initialize the sentence-transformers embeddings client."""
        settings = get_settings()
        self.api_key = settings.huggingface_api_key
        self.model_name = "BAAI/bge-large-en-v1.5"
        self.embedding_dim = 1024

        logger.info(f"Initializing Sentence Transformer Embeddings Client")
        logger.info(f"Model: {self.model_name}")
        logger.info(f"Embedding dimension: {self.embedding_dim}")
        
        try:
            logger.info(f"Loading model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Successfully loaded model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using sentence-transformers.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each 1024-dimensional)

        Raises:
            Exception: If embedding fails
        """
        if not texts:
            logger.warning("Empty text list provided to embed_texts")
            return []

        logger.debug(f"Embedding {len(texts)} texts with sentence-transformers")

        try:
            # Use sentence-transformers to encode (convert to numpy for proper conversion to list)
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            
            # Convert numpy arrays to list of lists
            import numpy as np
            if isinstance(embeddings, np.ndarray):
                if embeddings.ndim == 1:
                    # Single embedding
                    embeddings_list = [embeddings.tolist()]
                else:
                    # Multiple embeddings (2D array)
                    embeddings_list = [emb.tolist() for emb in embeddings]
            elif isinstance(embeddings, list):
                # Already a list - ensure all elements are lists
                embeddings_list = []
                for emb in embeddings:
                    if isinstance(emb, np.ndarray):
                        embeddings_list.append(emb.tolist())
                    elif hasattr(emb, 'tolist'):  # PyTorch tensor or similar
                        embeddings_list.append(emb.tolist())
                    else:
                        embeddings_list.append(list(emb))
            else:
                # Single embedding (tensor or other type)
                if hasattr(embeddings, 'tolist'):
                    embeddings_list = [embeddings.tolist()]
                else:
                    embeddings_list = [list(embeddings)]

            # Verify dimensions
            for i, emb in enumerate(embeddings_list):
                if len(emb) != self.embedding_dim:
                    logger.warning(f"Embedding {i} has dimension {len(emb)}, expected {self.embedding_dim}")

            logger.debug(f"Successfully embedded {len(texts)} texts")
            return embeddings_list

        except Exception as e:
            logger.error(f"Failed to embed texts: {e}", exc_info=True)
            raise Exception(f"Failed to embed texts: {e}") from e

    def embed_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            1024-dimensional embedding vector
        """
        logger.debug(f"Embedding single text: {text[:50]}...")
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []

    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generate embeddings for a large list of texts in batches.

        Args:
            texts: List of text strings to embed
            batch_size: Number of texts per batch (for logging, model handles batching)

        Returns:
            List of embedding vectors
        """
        logger.info(f"Embedding {len(texts)} texts (model will handle batching)")
        
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(texts) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} texts)")

            try:
                batch_embeddings = self.embed_texts(batch)
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Failed to embed batch {batch_num}: {e}")
                raise

        logger.info(f"Successfully embedded all {len(texts)} texts")
        return all_embeddings


# Global client instance
_embeddings_client = None


def get_embeddings_client() -> SentenceTransformerEmbeddingsClient:
    """Get or create the embeddings client."""
    global _embeddings_client
    if _embeddings_client is None:
        logger.info("Creating new SentenceTransformerEmbeddingsClient instance")
        _embeddings_client = SentenceTransformerEmbeddingsClient()
    return _embeddings_client
