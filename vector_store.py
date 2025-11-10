"""Pinecone vector store integration."""

import logging
import time
from typing import List, Tuple, Optional
from pinecone import Pinecone
from models import Message, RetrievedContext
from config import get_settings

logger = logging.getLogger(__name__)


class PineconeStore:
    """Vector store using Pinecone."""

    def __init__(self):
        """Initialize Pinecone client and index."""
        settings = get_settings()

        logger.info(f"Initializing Pinecone with index: {settings.pinecone_index_name}")

        try:
            self.client = Pinecone(api_key=settings.pinecone_api_key)
            self.index_name = settings.pinecone_index_name
            self.embedding_dim = 1024  # Jina v3 dimension

            # Try to access the index directly (it should already exist)
            logger.info(f"Accessing index '{self.index_name}'...")
            try:
                self.index = self.client.Index(self.index_name)
                # Test access by getting stats
                stats = self.index.describe_index_stats()
                logger.info(f"Successfully connected to index '{self.index_name}'")
                logger.info(f"Index stats: {stats}")
            except Exception as e:
                error_str = str(e).lower()
                if "not found" in error_str or "404" in error_str:
                    # Index doesn't exist, try to create it
                    logger.info(f"Index '{self.index_name}' not found. Attempting to create...")
                    try:
                        self.client.create_index(
                            name=self.index_name,
                            dimension=self.embedding_dim,
                            metric="cosine",
                        )
                        logger.info(f"Successfully created index '{self.index_name}'")
                        # Wait for index to be ready
                        logger.info("Waiting for index to be ready...")
                        max_wait = 60
                        wait_time = 0
                        while wait_time < max_wait:
                            try:
                                time.sleep(3)
                                wait_time += 3
                                test_index = self.client.Index(self.index_name)
                                test_index.describe_index_stats()
                                logger.info(f"Index is ready after {wait_time} seconds")
                                self.index = test_index
                                break
                            except Exception:
                                if wait_time >= max_wait:
                                    raise
                                continue
                    except Exception as create_error:
                        logger.error(f"Failed to create index: {create_error}")
                        raise
                else:
                    logger.error(f"Failed to access index '{self.index_name}': {e}")
                    logger.error("Please ensure:")
                    logger.error(f"  1. Index '{self.index_name}' exists in Pinecone")
                    logger.error(f"  2. Index has dimension {self.embedding_dim}")
                    logger.error(f"  3. Pinecone API key has correct permissions")
                    raise

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise

    def upsert_embeddings(
        self,
        messages: List[Message],
        embeddings: List[List[float]],
    ) -> int:
        """
        Upsert messages with their embeddings to Pinecone.

        Args:
            messages: List of message objects
            embeddings: List of embedding vectors

        Returns:
            Number of vectors upserted
        """
        if len(messages) != len(embeddings):
            logger.error(f"Mismatch: {len(messages)} messages, {len(embeddings)} embeddings")
            raise ValueError("Messages and embeddings count mismatch")

        logger.info(f"Upserting {len(messages)} vectors to Pinecone")

        try:
            # Prepare vectors for upsert
            vectors_to_upsert = []
            for msg, emb in zip(messages, embeddings):
                vector = (
                    msg.id,
                    emb,
                    {
                        "user_id": msg.user_id,
                        "user_name": msg.user_name,
                        "timestamp": msg.timestamp,
                        "message": msg.message,
                    },
                )
                vectors_to_upsert.append(vector)

            # Upsert to Pinecone
            upsert_response = self.index.upsert(vectors=vectors_to_upsert)
            
            # Extract the count from the response (Pinecone returns a dict-like object)
            if isinstance(upsert_response, dict):
                upserted_count = upsert_response.get('upserted_count', len(messages))
            elif hasattr(upsert_response, 'upserted_count'):
                upserted_count = upsert_response.upserted_count
            else:
                # Fallback: assume all were upserted
                upserted_count = len(messages)
            
            logger.info(f"Successfully upserted {upserted_count} vectors")

            return upserted_count

        except Exception as e:
            logger.error(f"Failed to upsert embeddings: {e}")
            raise

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[RetrievedContext]:
        """
        Search for most similar messages.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of top results to return

        Returns:
            List of retrieved contexts with scores
        """
        logger.debug(f"Searching Pinecone with top_k={top_k}")

        try:
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
            )

            retrieved = []
            for i, match in enumerate(results.get("matches", [])):
                msg_data = match.get("metadata", {})
                message = Message(
                    id=match["id"],
                    user_id=msg_data.get("user_id", ""),
                    user_name=msg_data.get("user_name", ""),
                    timestamp=msg_data.get("timestamp", ""),
                    message=msg_data.get("message", ""),
                )

                context = RetrievedContext(
                    message=message,
                    similarity_score=match.get("score", 0),
                    rank=i + 1,
                )
                retrieved.append(context)

            logger.info(f"Retrieved {len(retrieved)} results from Pinecone")
            return retrieved

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def get_index_stats(self) -> dict:
        """
        Get index statistics.

        Returns:
            Dictionary with index stats
        """
        try:
            stats = self.index.describe_index_stats()
            logger.debug(f"Index stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            raise

    def delete_all(self) -> None:
        """Delete all vectors from index."""
        logger.warning("Deleting all vectors from Pinecone index")
        try:
            # Delete by deleting namespace (or all if no namespace)
            self.index.delete(delete_all=True)
            logger.info("Successfully deleted all vectors")
        except Exception as e:
            logger.error(f"Failed to delete all vectors: {e}")
            raise


# Global store instance
_vector_store = None


def get_vector_store() -> PineconeStore:
    """Get or create the vector store."""
    global _vector_store
    if _vector_store is None:
        logger.info("Creating new PineconeStore instance")
        _vector_store = PineconeStore()
    return _vector_store

