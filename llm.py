"""LLM service using OpenRouter and GPT-4o mini."""

import logging
from typing import List, Optional, Tuple
import openai
from models import RetrievedContext
from config import get_settings
from token_utils import TokenUtils, TokenUsage

logger = logging.getLogger(__name__)


class LLMService:
    """Service for generating answers using GPT-4o mini via OpenRouter."""

    def __init__(self):
        """Initialize the LLM service."""
        settings = get_settings()

        logger.info("Initializing LLMService with OpenRouter")

        # Configure OpenAI client to use OpenRouter
        self.client = openai.OpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        self.model = settings.openrouter_model
        logger.info(f"LLMService initialized with model: {self.model}")

    def generate_answer(
        self,
        question: str,
        contexts: List[RetrievedContext],
    ) -> Tuple[str, TokenUsage]:
        """
        Generate an answer to a question using retrieved contexts.

        Args:
            question: The question being asked
            contexts: List of retrieved and reranked contexts

        Returns:
            Tuple of (answer string, TokenUsage object)
        """
        logger.info(f"Generating answer for question: {question[:50]}...")
        logger.debug(f"Using {len(contexts)} contexts")

        # Format contexts
        context_text = self._format_contexts(contexts)

        # Build prompt
        system_prompt = """You are a helpful assistant that answers questions about member data 
from message conversations. Use ONLY the provided context to answer questions accurately and concisely.
If the answer cannot be found in the context, clearly state that you don't have that information.
Do not make assumptions or provide information not in the context."""

        user_prompt = f"""Context from member messages:
{context_text}

Question: {question}

Answer: Based on the context above, provide a clear and concise answer. If information is not available, say so."""

        try:
            logger.debug(f"Calling OpenRouter API with model: {self.model}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,  # Low temperature for factual answers
                max_tokens=500,
            )

            answer = response.choices[0].message.content.strip()

            # Extract token usage
            token_usage = TokenUtils.extract_usage_from_response(response)
            if token_usage:
                # Calculate cost
                token_usage.cost_usd = TokenUtils.calculate_cost(
                    token_usage.prompt_tokens,
                    token_usage.completion_tokens,
                    self.model
                )
                logger.info(
                    f"Token usage: {token_usage.total_tokens} tokens "
                    f"({token_usage.prompt_tokens} prompt + {token_usage.completion_tokens} completion) "
                    f"Cost: {TokenUtils.format_cost(token_usage.cost_usd)}"
                )
            else:
                # Fallback: estimate tokens if API doesn't provide usage
                prompt_tokens = TokenUtils.estimate_tokens(system_prompt + user_prompt)
                completion_tokens = TokenUtils.estimate_tokens(answer)
                token_usage = TokenUtils.create_usage(prompt_tokens, completion_tokens, self.model)
                logger.warning(f"Token usage not available from API, estimated: {token_usage.total_tokens} tokens")

            logger.info(f"Answer generated successfully ({len(answer)} chars)")
            logger.debug(f"Generated answer: {answer[:100]}...")

            return answer, token_usage

        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            raise

    def raw_call(self, system_prompt: str, user_prompt: str, temperature: float = 0.1, max_tokens: int = 200) -> str:
        """
        Make a raw LLM call (for evaluations).

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            temperature: Temperature for generation
            max_tokens: Max tokens to generate

        Returns:
            Generated text
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            # Log token usage for evaluations (but don't return it)
            token_usage = TokenUtils.extract_usage_from_response(response)
            if token_usage:
                token_usage.cost_usd = TokenUtils.calculate_cost(
                    token_usage.prompt_tokens,
                    token_usage.completion_tokens,
                    self.model
                )
                logger.debug(
                    f"Evaluation call tokens: {token_usage.total_tokens} "
                    f"Cost: {TokenUtils.format_cost(token_usage.cost_usd)}"
                )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Raw LLM call failed: {e}")
            raise

    def _format_contexts(self, contexts: List[RetrievedContext]) -> str:
        """
        Format retrieved contexts for the LLM prompt.

        Args:
            contexts: List of contexts

        Returns:
            Formatted context string
        """
        formatted = []

        for ctx in contexts:
            msg = ctx.message
            formatted_item = f"- [{msg.user_name}] {msg.message}"

            if ctx.reranker_score is not None:
                formatted_item += f" (relevance: {ctx.reranker_score:.2f})"

            formatted.append(formatted_item)

        return "\n".join(formatted)


# Global LLM service instance
_llm_service = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service."""
    global _llm_service
    if _llm_service is None:
        logger.info("Creating new LLMService instance")
        _llm_service = LLMService()
    return _llm_service

