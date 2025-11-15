"""Data ingestion and indexing pipeline."""

import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import List
import requests
from .models import Message, PaginatedMessages, IndexingMetadata
from .embeddings import get_embeddings_client
from .vector_store import get_vector_store
from .config import get_settings

logger = logging.getLogger(__name__)

# Global indexing state
indexing_state = {
    "in_progress": False,
    "total_messages": 0,  # Messages indexed
    "indexed_messages": 0,  # Same as total_messages (for backward compatibility)
    "expected_total_messages": None,  # Total according to API
    "fetched_messages": 0,  # Messages successfully fetched from API
    "missed_messages": 0,  # Messages that couldn't be fetched
    "missed_ranges": [],  # List of skip ranges that failed
    "last_indexed": None,
    "next_refresh": None,
    "last_error": None,
}


class DataIngestionPipeline:
    """Pipeline for fetching and indexing messages."""

    def __init__(self):
        """Initialize the ingestion pipeline."""
        settings = get_settings()
        self.api_url = settings.external_api_url
        self.batch_size = settings.message_batch_size
        self.embedding_batch_size = settings.embedding_batch_size

        self.embeddings_client = get_embeddings_client()
        self.vector_store = get_vector_store()

        logger.info("DataIngestionPipeline initialized")

    def fetch_all_messages(self) -> List[Message]:
        """
        Fetch all messages from the external API with improved error handling.

        Returns:
            List of all messages successfully fetched
        """
        logger.info("Starting to fetch all messages from API")

        all_messages = []
        skip = 0
        expected_total = None
        consecutive_errors = 0
        consecutive_skips = 0  # Track consecutive skipped ranges
        max_consecutive_errors = 3
        max_consecutive_skips = 10  # Stop if we skip 10 ranges in a row (likely reached end)
        base_delay = 2.5  # Increased base delay to 2.5 seconds
        retry_attempts = 2  # Number of retries per failed request

        try:
            while True:
                logger.debug(f"Fetching messages: skip={skip}, limit=100")

                try:
                    response = requests.get(
                        f"{self.api_url}/messages/",
                        params={"skip": skip, "limit": 100},
                        timeout=30,
                        headers={"Accept": "application/json"},
                    )
                    response.raise_for_status()

                    data = response.json()
                    paginated = PaginatedMessages(**data)

                    if expected_total is None:
                        expected_total = paginated.total
                        indexing_state["expected_total_messages"] = expected_total
                        logger.info(f"Total messages according to API: {expected_total}")

                    # If we get 0 messages, we've reached the end
                    if len(paginated.items) == 0:
                        logger.info(f"Received 0 messages at skip={skip}. Reached end of available data.")
                        break
                    
                    all_messages.extend(paginated.items)
                    indexing_state["fetched_messages"] = len(all_messages)
                    consecutive_errors = 0  # Reset on success
                    consecutive_skips = 0  # Reset on success

                    # Log progress every 500 messages or near completion
                    if len(all_messages) % 500 == 0 or len(all_messages) >= expected_total - 100:
                        logger.info(f"Progress: Fetched {len(all_messages)}/{expected_total} messages ({len(all_messages)/expected_total*100:.1f}%)")

                    # Stop if we've fetched enough messages (accounting for skipped ranges)
                    if len(all_messages) >= expected_total:
                        logger.info(f"Successfully fetched all {len(all_messages)} messages")
                        break
                    
                    # Stop if skip value exceeds what's needed for expected_total
                    # (e.g., if expected_total=3349, we don't need skip > 3300)
                    if skip >= expected_total:
                        logger.info(f"Skip value ({skip}) exceeds expected total ({expected_total}). Stopping fetch.")
                        break

                    skip += 100
                    
                    # Base delay between requests (increased to reduce rate limiting)
                    time.sleep(base_delay)
                    
                except requests.exceptions.HTTPError as e:
                    status_code = e.response.status_code
                    error_text = e.response.text[:500] if e.response.text else "No error text"
                    logger.error(f"{status_code} error at skip={skip}. Response: {error_text}")
                    
                    # Handle 404 immediately - skip range without retries
                    if status_code == 404:
                        consecutive_skips += 1
                        missed_range = f"{skip}-{skip+99}"
                        if missed_range not in indexing_state["missed_ranges"]:
                            indexing_state["missed_ranges"].append(missed_range)
                        
                        logger.warning(f"404 Not Found at skip={skip}. Skipping this range and continuing... (consecutive skips: {consecutive_skips}/{max_consecutive_skips})")
                        
                        if consecutive_skips >= max_consecutive_skips:
                            logger.warning(f"Reached {max_consecutive_skips} consecutive skipped ranges. Likely reached end of available data.")
                            logger.warning(f"Stopping fetch with {len(all_messages)} messages fetched so far.")
                            break
                        
                        skip += 100
                        time.sleep(base_delay * 2)
                        continue
                    
                    consecutive_errors += 1
                    
                    # Track missed range
                    missed_range = f"{skip}-{skip+99}"
                    if missed_range not in indexing_state["missed_ranges"]:
                        indexing_state["missed_ranges"].append(missed_range)
                    
                    if status_code in [400, 401, 402, 403, 405, 429]:  # Various API errors (402 = Payment Required)
                        # 402 and 403 are often hard limits - try once but don't retry aggressively
                        if status_code in [402, 403]:
                            logger.warning(f"API returned {status_code} ({'Payment Required' if status_code == 402 else 'Forbidden'}) at skip={skip}. This may be a hard limit.")
                            # Try one retry with a short delay, but if it fails, continue with what we have
                            retry_delay = base_delay * 2
                        else:
                            # Exponential backoff: 2^attempt * base_delay
                            retry_delay = base_delay * (2 ** min(consecutive_errors, 4))  # Cap at 16x delay
                        
                        # If too many consecutive errors, wait longer
                        if consecutive_errors >= max_consecutive_errors:
                            backoff_delay = 30  # 30 second backoff after N consecutive errors
                            logger.warning(f"{consecutive_errors} consecutive errors detected. Backing off for {backoff_delay}s...")
                            time.sleep(backoff_delay)
                            consecutive_errors = 0  # Reset after backoff
                        else:
                            logger.warning(f"API error ({status_code}). Retrying with {retry_delay:.1f}s delay (attempt {consecutive_errors}/{retry_attempts})...")
                            time.sleep(retry_delay)
                        
                        # Retry with exponential backoff
                        retry_success = False
                        for retry_num in range(retry_attempts):
                            try:
                                retry_response = requests.get(
                                    f"{self.api_url}/messages/",
                                    params={"skip": skip, "limit": 100},
                                    timeout=30,
                                    headers={"Accept": "application/json"},
                                )
                                retry_response.raise_for_status()
                                
                                retry_data = retry_response.json()
                                retry_paginated = PaginatedMessages(**retry_data)
                                
                                # If retry returns 0 messages, we've reached the end
                                if len(retry_paginated.items) == 0:
                                    logger.info(f"Retry returned 0 messages at skip={skip}. Reached end of available data.")
                                    retry_success = True  # Mark as success to exit retry loop
                                    # Set a flag to stop main loop
                                    skip = expected_total  # This will trigger the skip >= expected_total check
                                    break
                                
                                all_messages.extend(retry_paginated.items)
                                indexing_state["fetched_messages"] = len(all_messages)
                                
                                # Remove from missed ranges if retry succeeds
                                if missed_range in indexing_state["missed_ranges"]:
                                    indexing_state["missed_ranges"].remove(missed_range)
                                
                                logger.info(f"Retry successful! Fetched {len(retry_paginated.items)} messages at skip={skip}")
                                retry_success = True
                                consecutive_errors = 0
                                
                                if len(all_messages) >= expected_total:
                                    break
                                
                                skip += 100
                                time.sleep(base_delay * 1.5)  # Longer delay after successful retry
                                break
                                
                            except requests.exceptions.HTTPError as retry_http_error:
                                retry_status = retry_http_error.response.status_code
                                # If 404 on retry, skip this range immediately
                                if retry_status == 404:
                                    logger.warning(f"Retry got 404 at skip={skip}. Skipping this range.")
                                    break  # Break out of retry loop to skip range
                                retry_delay = base_delay * (2 ** (retry_num + 1))
                                logger.warning(f"Retry {retry_num + 1} failed: {retry_http_error}. Waiting {retry_delay:.1f}s...")
                                if retry_num < retry_attempts - 1:
                                    time.sleep(retry_delay)
                            except Exception as retry_error:
                                retry_delay = base_delay * (2 ** (retry_num + 1))
                                logger.warning(f"Retry {retry_num + 1} failed: {retry_error}. Waiting {retry_delay:.1f}s...")
                                if retry_num < retry_attempts - 1:
                                    time.sleep(retry_delay)
                        
                        # After retry, check if we should stop
                        if retry_success and (len(all_messages) >= expected_total or skip >= expected_total):
                            logger.info(f"Stopping fetch: fetched {len(all_messages)}/{expected_total} messages, skip={skip}")
                            break
                        
                        if not retry_success:
                            # If all retries failed, check if we should continue or stop
                            if status_code == 402:
                                # 402 = Payment Required - hard limit, stop immediately
                                logger.warning(f"402 Payment Required persists after retries. API requires payment for further access.")
                                logger.warning(f"Stopping fetch and continuing with {len(all_messages)} messages fetched so far.")
                                break
                            elif status_code == 403 and consecutive_errors >= max_consecutive_errors:
                                # 403 = Forbidden - likely hard limit after multiple attempts
                                logger.warning(f"403 Forbidden persists after {retry_attempts} retries. API may have blocked access.")
                                logger.warning(f"Continuing with {len(all_messages)} messages fetched so far.")
                                break
                            elif status_code == 404:
                                # 404 = Not Found - skip this range and continue (might be missing page, not end of data)
                                consecutive_skips += 1
                                logger.warning(f"404 Not Found at skip={skip}. Skipping this range and continuing... (consecutive skips: {consecutive_skips}/{max_consecutive_skips})")
                                
                                if consecutive_skips >= max_consecutive_skips:
                                    logger.warning(f"Reached {max_consecutive_skips} consecutive skipped ranges. Likely reached end of available data.")
                                    logger.warning(f"Stopping fetch with {len(all_messages)} messages fetched so far.")
                                    break
                                
                                skip += 100
                                time.sleep(base_delay * 2)  # Longer delay after skipping
                                continue  # Continue to next iteration
                            else:
                                # For other errors, skip this range and continue
                                consecutive_skips += 1
                                logger.warning(f"Skipping range {missed_range} due to persistent errors. Continuing... (consecutive skips: {consecutive_skips}/{max_consecutive_skips})")
                                
                                if consecutive_skips >= max_consecutive_skips:
                                    logger.warning(f"Reached {max_consecutive_skips} consecutive skipped ranges. Likely reached end of available data.")
                                    logger.warning(f"Stopping fetch with {len(all_messages)} messages fetched so far.")
                                    break
                                
                                skip += 100
                                time.sleep(base_delay * 2)  # Longer delay after skipping
                                continue  # Continue to next iteration
                    else:
                        # For unexpected status codes, raise the error
                        raise

                except requests.exceptions.Timeout:
                    consecutive_errors += 1
                    missed_range = f"{skip}-{skip+99}"
                    if missed_range not in indexing_state["missed_ranges"]:
                        indexing_state["missed_ranges"].append(missed_range)
                    
                    logger.error(f"Timeout at skip={skip} (consecutive errors: {consecutive_errors})")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.warning(f"Too many timeouts. Stopping fetch at {len(all_messages)} messages.")
                        break
                    
                    retry_delay = base_delay * (2 ** min(consecutive_errors, 4))
                    logger.warning(f"Retrying after {retry_delay:.1f}s delay...")
                    time.sleep(retry_delay)
                    continue  # Retry the same skip value

            # Calculate missed messages
            if expected_total is not None:
                missed_count = expected_total - len(all_messages)
                indexing_state["missed_messages"] = missed_count
                
                logger.info("=" * 80)
                logger.info(f"FETCH SUMMARY:")
                logger.info(f"  Expected (from API): {expected_total}")
                logger.info(f"  Successfully fetched: {len(all_messages)}")
                logger.info(f"  Missed: {missed_count}")
                if indexing_state["missed_ranges"]:
                    logger.info(f"  Missed ranges: {', '.join(indexing_state['missed_ranges'][:10])}")
                    if len(indexing_state["missed_ranges"]) > 10:
                        logger.info(f"  ... and {len(indexing_state['missed_ranges']) - 10} more ranges")
                logger.info("=" * 80)

            return all_messages

        except Exception as e:
            logger.error(f"Failed to fetch messages: {e}")
            indexing_state["last_error"] = str(e)
            # Calculate missed messages even on error
            if expected_total is not None:
                missed_count = expected_total - len(all_messages)
                indexing_state["missed_messages"] = missed_count
            raise

    def index_messages(self, messages: List[Message]) -> int:
        """
        Index messages by embedding and storing in vector DB.

        Args:
            messages: List of messages to index

        Returns:
            Number of messages indexed
        """
        if not messages:
            logger.warning("No messages to index")
            return 0

        logger.info(f"Starting to index {len(messages)} messages")

        try:
            # Process in batches
            total_indexed = 0

            for i in range(0, len(messages), self.batch_size):
                batch = messages[i : i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (len(messages) + self.batch_size - 1) // self.batch_size

                logger.info(f"Processing batch {batch_num}/{total_batches}")

                # Extract texts for embedding - include user name to enable user-message semantic mapping
                # Format: "[User Name] message content" - this allows queries about users to find their messages
                # and queries with message content to map back to users semantically
                texts = [f"[{msg.user_name}] {msg.message}" for msg in batch]

                # Generate embeddings
                logger.debug(f"Generating embeddings for {len(texts)} messages")
                embeddings = self.embeddings_client.embed_batch(
                    texts, batch_size=self.embedding_batch_size
                )

                # Upsert to vector store
                logger.debug(f"Upserting {len(batch)} vectors to Pinecone")
                upserted = self.vector_store.upsert_embeddings(batch, embeddings)

                total_indexed += upserted

                # Update progress
                progress_percent = (total_indexed / len(messages)) * 100
                indexing_state["indexed_messages"] = total_indexed
                logger.info(f"Progress: {total_indexed}/{len(messages)} ({progress_percent:.1f}%)")

            logger.info(f"Successfully indexed {total_indexed} messages")
            return total_indexed

        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            indexing_state["last_error"] = str(e)
            raise

    async def run_full_indexing(self) -> bool:
        """
        Run full indexing pipeline (fetch all, embed, index).

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 80)
        logger.info("STARTING FULL INDEXING PIPELINE")
        logger.info("=" * 80)

        indexing_state["in_progress"] = True
        indexing_state["last_error"] = None

        start_time = datetime.now()

        try:
            # Reset missed ranges at start
            indexing_state["missed_ranges"] = []
            indexing_state["missed_messages"] = 0
            
            # Fetch all messages (may be partial if API blocks)
            messages = self.fetch_all_messages()
            indexing_state["total_messages"] = len(messages)
            indexing_state["indexed_messages"] = len(messages)  # Will be updated after indexing

            if not messages:
                logger.warning("No messages fetched - cannot proceed with indexing")
                indexing_state["last_error"] = "No messages fetched from API"
                return False

            # Index messages (even if partial)
            indexed_count = self.index_messages(messages)

            # Update state
            indexing_state["indexed_messages"] = indexed_count
            indexing_state["total_messages"] = indexed_count  # Update to actual indexed count
            indexing_state["last_indexed"] = datetime.now()

            elapsed = datetime.now() - start_time
            logger.info("=" * 80)
            logger.info(f"INDEXING COMPLETE: {indexed_count} messages indexed in {elapsed.total_seconds():.1f}s")
            
            # Log summary of fetched vs missed
            expected = indexing_state.get("expected_total_messages", 0)
            fetched = indexing_state.get("fetched_messages", indexed_count)
            missed = indexing_state.get("missed_messages", 0)
            
            if expected > 0 and missed > 0:
                logger.warning(f"Partial indexing: Expected {expected}, Fetched {fetched}, Missed {missed}")
                if indexing_state.get("missed_ranges"):
                    logger.warning(f"Missed ranges: {', '.join(indexing_state['missed_ranges'][:5])}")
            elif expected > 0 and fetched == expected:
                logger.info(f"Successfully fetched and indexed all {expected} messages")
            
            logger.info("=" * 80)

            return True

        except Exception as e:
            logger.error(f"Full indexing failed: {e}")
            indexing_state["last_error"] = str(e)
            # If we have some messages, try to index them anyway
            if 'messages' in locals() and messages:
                logger.info(f"Attempting to index {len(messages)} messages despite error...")
                try:
                    indexed_count = self.index_messages(messages)
                    indexing_state["indexed_messages"] = indexed_count
                    indexing_state["last_indexed"] = datetime.now()
                    logger.info(f"Successfully indexed {indexed_count} messages despite initial error")
                    return True
                except Exception as index_error:
                    logger.error(f"Failed to index partial data: {index_error}")
            return False

        finally:
            indexing_state["in_progress"] = False


# Global pipeline instance
_pipeline = None


def get_ingestion_pipeline() -> DataIngestionPipeline:
    """Get or create the ingestion pipeline."""
    global _pipeline
    if _pipeline is None:
        logger.info("Creating new DataIngestionPipeline instance")
        _pipeline = DataIngestionPipeline()
    return _pipeline


def get_indexing_state() -> dict:
    """Get current indexing state."""
    return indexing_state.copy()


def should_index() -> bool:
    """
    Check if indexing is needed by checking if Pinecone index has data.
    
    Returns:
        True if indexing is needed, False if data already exists
    """
    try:
        from .vector_store import get_vector_store
        vector_store = get_vector_store()
        stats = vector_store.get_index_stats()
        
        total_vectors = stats.get('total_vector_count', 0)
        
        if total_vectors == 0:
            logger.info("Index is empty - indexing is needed")
            return True
        else:
            logger.info(f"Index already contains {total_vectors} vectors - skipping indexing")
            # Update state to reflect existing data
            indexing_state["indexed_messages"] = total_vectors
            indexing_state["total_messages"] = total_vectors
            indexing_state["in_progress"] = False
            indexing_state["last_indexed"] = datetime.now()  # Use current time as placeholder
            return False
            
    except Exception as e:
        logger.warning(f"Could not check index status: {e}. Proceeding with indexing.")
        return True


async def run_background_indexing():
    """Run background indexing (for use in async context)."""
    logger.info("Starting background indexing job")

    # Check if indexing is needed
    if not should_index():
        logger.info("Index already populated - skipping indexing")
        return

    pipeline = get_ingestion_pipeline()

    try:
        success = await pipeline.run_full_indexing()

        if success:
            logger.info("Background indexing completed successfully")
        else:
            logger.error("Background indexing failed")

    except Exception as e:
        logger.error(f"Error in background indexing: {e}")
        indexing_state["last_error"] = str(e)


def fetch_sample_messages(count: int = 10) -> List[Message]:
    """
    Fetch a random sample of messages from the API to show what data is available.
    
    Args:
        count: Number of sample messages to fetch
        
    Returns:
        List of sample messages
    """
    import random
    settings = get_settings()
    api_url = settings.external_api_url
    
    try:
        # First, get total count
        response = requests.get(
            f"{api_url}/messages/",
            params={"skip": 0, "limit": 1},
            timeout=30,  # Increased timeout for slow API
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        paginated = PaginatedMessages(**response.json())
        total = paginated.total
        
        if total == 0:
            logger.warning("No messages found in API")
            return []
        
        # Fetch random samples from different pages
        sample_messages = []
        
        # Generate random page numbers (each page has up to 100 messages)
        num_pages = (total + 99) // 100  # Round up
        if num_pages == 0:
            return []
        
        # Get up to 'count' random pages, but don't exceed available pages
        pages_to_sample = min(count, num_pages)
        random_page_numbers = random.sample(range(num_pages), pages_to_sample)
        
        for page_num in random_page_numbers:
            skip = page_num * 100
            try:
                response = requests.get(
                    f"{api_url}/messages/",
                    params={"skip": skip, "limit": 1},
                    timeout=30,  # Increased timeout for slow API
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                paginated = PaginatedMessages(**response.json())
                if paginated.items:
                    sample_messages.append(paginated.items[0])
            except Exception as e:
                logger.debug(f"Failed to fetch sample at skip={skip}: {e}")
                continue
        
        return sample_messages
        
    except Exception as e:
        logger.warning(f"Failed to fetch sample messages: {e}")
        return []


def print_sample_messages(count: int = 10):
    """
    Fetch and print sample messages to show what data is available.
    Non-blocking - fails gracefully if API is slow/unavailable.
    
    Args:
        count: Number of sample messages to display
    """
    logger.info("=" * 80)
    logger.info("FETCHING SAMPLE MESSAGES FROM API")
    logger.info("=" * 80)
    
    try:
        samples = fetch_sample_messages(count)
        
        if not samples:
            logger.warning("No sample messages could be fetched (API may be slow or unavailable)")
            logger.info("Continuing startup without sample messages...")
            return
        
        logger.info(f"\n📋 Sample Messages ({len(samples)} shown):")
        logger.info("=" * 80)
        
        for i, msg in enumerate(samples, 1):
            logger.info(f"\n[{i}] User: {msg.user_name} (ID: {msg.user_id})")
            logger.info(f"    Timestamp: {msg.timestamp}")
            logger.info(f"    Message: {msg.message[:200]}{'...' if len(msg.message) > 200 else ''}")
        
        logger.info("\n" + "=" * 80)
        logger.info(f"Total messages in API: {indexing_state.get('expected_total_messages', 'Unknown')}")
        logger.info("=" * 80 + "\n")
        
    except Exception as e:
        logger.warning(f"Sample message fetching failed: {e}")
        logger.info("Continuing startup without sample messages...")

