"""Embeddings service using Hugging Face Inference API."""

import logging
import requests
from typing import List
from .config import get_settings

logger = logging.getLogger(__name__)


class HFInferenceEmbeddingsClient:
    """Client for Hugging Face Inference API embeddings."""

    def __init__(self):
        """Initialize the Hugging Face embeddings client."""
        settings = get_settings()
        self.api_key = settings.huggingface_api_key
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self.embedding_dim = 384
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_name}"

        logger.info(f"Initializing HF Inference Embeddings Client")
        logger.info(f"Model: {self.model_name}")
        logger.info(f"Embedding dimension: {self.embedding_dim}")
        logger.info(f"API URL: {self.api_url}")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using HF Inference API.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each 384-dimensional)

        Raises:
            Exception: If embedding fails
        """
        if not texts:
            logger.warning("Empty text list provided to embed_texts")
            return []

        logger.debug(f"Embedding {len(texts)} texts via HF API")

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # HF Inference API expects inputs as list of strings
            payload = {"inputs": texts}

            logger.debug(f"Calling HF API with {len(texts)} texts")
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            # Check for errors
            if response.status_code != 200:
                error_msg = response.text
                logger.error(f"HF API error ({response.status_code}): {error_msg}")
                raise Exception(f"HF API returned {response.status_code}: {error_msg}")

            # Parse response
            embeddings_list = response.json()

            # HF returns list of lists directly
            if not isinstance(embeddings_list, list):
                logger.error(f"Unexpected response format: {type(embeddings_list)}")
                raise Exception(f"Unexpected HF API response format")

            # Verify we got embeddings for all texts
            if len(embeddings_list) != len(texts):
                logger.warning(f"Expected {len(texts)} embeddings, got {len(embeddings_list)}")

            # Verify dimensions
            for i, emb in enumerate(embeddings_list):
                if not isinstance(emb, list):
                    logger.error(f"Embedding {i} is not a list: {type(emb)}")
                    embeddings_list[i] = list(emb)
                
                if len(emb) != self.embedding_dim:
                    logger.warning(f"Embedding {i} has dimension {len(emb)}, expected {self.embedding_dim}")

            logger.debug(f"Successfully embedded {len(texts)} texts via HF API")
            return embeddings_list

        except requests.exceptions.Timeout:
            logger.error("HF API request timed out")
            raise Exception("HF API request timed out after 30 seconds")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to HF API: {e}")
            raise Exception(f"Failed to connect to HF API: {e}")
        except Exception as e:
            logger.error(f"Failed to embed texts: {e}", exc_info=True)
            raise Exception(f"Failed to embed texts: {e}") from e

    def embed_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            384-dimensional embedding vector
        """
        logger.debug(f"Embedding single text: {text[:50]}...")
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []

    def embed_batch(self, texts: List[str], batch_size: int = 50) -> List[List[float]]:
        """
        Generate embeddings for a large list of texts in batches.

        HF Inference API has limits on payload size, so we batch requests.

        Args:
            texts: List of text strings to embed
            batch_size: Number of texts per API call (50 is safe default)

        Returns:
            List of embedding vectors
        """
        logger.info(f"Embedding {len(texts)} texts in batches of {batch_size}")
        
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


def get_embeddings_client() -> HFInferenceEmbeddingsClient:
    """Get or create the embeddings client."""
    global _embeddings_client
    if _embeddings_client is None:
        logger.info("Creating new HFInferenceEmbeddingsClient instance")
        _embeddings_client = HFInferenceEmbeddingsClient()
    return _embeddings_client
