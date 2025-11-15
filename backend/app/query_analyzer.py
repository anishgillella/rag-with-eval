"""Query analysis for type detection, confidence scoring, and error messages."""

import logging
from typing import List, Tuple, Dict
from .models import QueryMetadata

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Analyzes queries to determine type, detect mentions, and assess confidence."""

    # Keywords for different query types
    USER_SPECIFIC_KEYWORDS = {
        "summarize", "summarise", "messages", "said", "say", "request", "requests",
        "asked", "ask", "visited", "visit", "places", "travel", "mentioned", "mention",
        "talked about", "discussed", "spoke", "shared", "commented"
    }

    FACTUAL_KEYWORDS = {
        "how many", "how much", "count", "number", "total", "when", "where",
        "what time", "which", "list", "name"
    }

    COMPARISON_KEYWORDS = {
        "compare", "contrast", "difference", "similar", "unlike", "versus", "vs",
        "between", "both", "either", "rather than", "instead of"
    }

    def __init__(self):
        """Initialize the query analyzer."""
        logger.info("QueryAnalyzer initialized")

    def analyze_query(
        self,
        question: str,
        mentioned_users: List[str],
        num_sources: int,
        sources_from_user: bool = False,
    ) -> Tuple[str, QueryMetadata, str]:
        """
        Analyze a query to determine type and generate metadata.

        Args:
            question: The user's question
            mentioned_users: List of detected user names
            num_sources: Number of sources retrieved
            sources_from_user: Whether sources are filtered by specific user

        Returns:
            Tuple of (query_type, query_metadata, tips)
        """
        question_lower = question.lower()

        # Determine query type
        query_type = self._determine_query_type(
            question_lower, mentioned_users, sources_from_user
        )

        # Generate metadata
        query_metadata = QueryMetadata(
            query_type=query_type,
            mentioned_users=mentioned_users,
            confidence_factors={},
        )

        # Generate helpful tips based on query type
        tips = self._generate_tips(query_type, mentioned_users, num_sources)

        logger.debug(f"Query analyzed: type={query_type}, users={mentioned_users}, tips={tips}")

        return query_type, query_metadata, tips

    def _determine_query_type(
        self, question_lower: str, mentioned_users: List[str], sources_from_user: bool
    ) -> str:
        """Determine the type of query."""
        if len(mentioned_users) > 1:
            return "multi_user"
        elif len(mentioned_users) == 1 and sources_from_user:
            return "user_specific"
        elif any(keyword in question_lower for keyword in self.COMPARISON_KEYWORDS):
            return "comparison"
        elif any(keyword in question_lower for keyword in self.FACTUAL_KEYWORDS):
            return "factual"
        elif any(keyword in question_lower for keyword in self.USER_SPECIFIC_KEYWORDS):
            return "user_specific"
        else:
            return "general"

    def _generate_tips(
        self, query_type: str, mentioned_users: List[str], num_sources: int
    ) -> str:
        """Generate helpful tips based on query characteristics."""
        tips = []

        # Confidence-based tips
        if num_sources < 2:
            tips.append(
                "Low confidence: Only 1 source found. Try a broader question or check if data exists."
            )
        elif num_sources < 5:
            tips.append(
                "Moderate confidence: Limited sources. Consider asking about different aspects."
            )
        else:
            tips.append(f"Good confidence: {num_sources} relevant sources found.")

        # Query type-specific tips
        if query_type == "user_specific" and not mentioned_users:
            tips.append("Tip: Mention a specific user name for more accurate results.")
        elif query_type == "factual" and num_sources < 3:
            tips.append("Tip: Try rephrasing as 'What did [user] say about...' for better results.")
        elif query_type == "comparison" and len(mentioned_users) < 2:
            tips.append("Tip: Mention specific users to compare their information.")
        elif query_type == "general" and num_sources < 3:
            tips.append("Tip: Be more specific about what information you're looking for.")

        return " ".join(tips)

    def calculate_confidence_score(
        self,
        num_sources: int,
        avg_reranker_score: float = 0.5,
        query_type: str = "general",
        sources_from_specific_user: bool = False,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate confidence score based on multiple factors.

        Args:
            num_sources: Number of sources used
            avg_reranker_score: Average reranker score (0-1)
            query_type: Type of query
            sources_from_specific_user: Whether sources filtered by user

        Returns:
            Tuple of (confidence_score, factor_weights)
        """
        factors = {}

        # Factor 1: Number of sources (30% weight)
        # More sources = higher confidence
        if num_sources >= 10:
            source_factor = 1.0
        elif num_sources >= 5:
            source_factor = 0.8
        elif num_sources >= 3:
            source_factor = 0.6
        elif num_sources >= 2:
            source_factor = 0.4
        else:
            source_factor = 0.2
        factors["source_count"] = source_factor * 0.3

        # Factor 2: Reranker score quality (30% weight)
        # Higher avg score = better matches
        reranker_factor = min(float(avg_reranker_score), 1.0)  # Normalize to 0-1
        factors["reranker_quality"] = reranker_factor * 0.3

        # Factor 3: Query type specificity (20% weight)
        # User-specific queries have higher confidence when we find user data
        if query_type == "user_specific" and sources_from_specific_user:
            query_factor = 0.95
        elif query_type == "user_specific":
            query_factor = 0.7
        elif query_type == "factual":
            query_factor = 0.75
        elif query_type == "comparison":
            query_factor = 0.8
        else:
            query_factor = 0.6
        factors["query_specificity"] = query_factor * 0.2

        # Factor 4: Source consistency (20% weight)
        # If sources are from expected users/patterns, higher confidence
        consistency_factor = 0.8  # Default to reasonable
        if num_sources < 2:
            consistency_factor = 0.4  # Low sources = potentially inconsistent
        factors["consistency"] = consistency_factor * 0.2

        # Calculate final confidence score (0-1)
        confidence = sum(factors.values())
        confidence = float(min(max(confidence, 0.0), 1.0))  # Clamp to 0-1

        logger.info(f"Confidence calculation: num_sources={num_sources}, avg_reranker={avg_reranker_score:.3f}, query_type={query_type}, factors={factors} → confidence={confidence:.3f}")

        return confidence, factors

    def generate_error_message(self, error_type: str, context: Dict = None) -> str:
        """
        Generate helpful error messages.

        Args:
            error_type: Type of error
            context: Additional context for the error

        Returns:
            User-friendly error message
        """
        context = context or {}

        error_messages = {
            "no_user_found": (
                f"Could not find information about '{context.get('query', 'that user')}'.\n"
                "Try:\n"
                "  * Spelling the name differently\n"
                "  * Asking about a different person\n"
                "  * Using a more general question"
            ),
            "no_relevant_sources": (
                f"No relevant information found for '{context.get('query', 'your query')}'.\n"
                "Try:\n"
                "  * Being more specific\n"
                "  * Mentioning a user name\n"
                "  * Rephrasing your question"
            ),
            "sparse_sources": (
                f"Limited information found (only {context.get('num_sources', 1)} source).\n"
                "This answer has low confidence. Try:\n"
                "  * Asking about a different aspect\n"
                "  * Mentioning specific users\n"
                "  * Using different keywords"
            ),
            "api_error": (
                "System error while processing your question.\n"
                "Our system is experiencing issues. Please try again in a moment."
            ),
            "invalid_question": (
                "Your question is too vague or too long.\n"
                "Try:\n"
                "  * Shortening your question\n"
                "  * Being more specific\n"
                "  * Example: 'What did Sophia say about travel?'"
            ),
        }

        return error_messages.get(error_type, "Unable to answer your question. Please try rephrasing.")


# Global analyzer instance
_query_analyzer = None


def get_query_analyzer() -> QueryAnalyzer:
    """Get or create the query analyzer."""
    global _query_analyzer
    if _query_analyzer is None:
        logger.info("Creating new QueryAnalyzer instance")
        _query_analyzer = QueryAnalyzer()
    return _query_analyzer

