"""Evaluation suite using Logfire for answer quality."""

import logging
from datetime import datetime
from typing import List
from .models import (
    EvaluationScore,
    EvaluationResults,
    RetrievedContext,
)
from .llm import get_llm_service

logger = logging.getLogger(__name__)

# Check if logfire is available
logfire_enabled = False
logfire = None
try:
    import logfire as logfire_module
    logfire = logfire_module
    logfire_enabled = True
except ImportError:
    pass

# Wrapper for optional logfire instrumentation
def optional_instrument(name):
    """Decorator that only instruments if logfire is enabled."""
    def decorator(func):
        if logfire_enabled and logfire:
            return logfire.instrument(name)(func)
        return func
    return decorator

# Helper function for optional logfire logging
def logfire_log(message: str, **kwargs):
    """Log to logfire if enabled, otherwise just use logger."""
    if logfire_enabled:
        try:
            logfire.info(message, **kwargs)
        except Exception as e:
            logger.debug(f"Logfire logging failed: {e}")
    else:
        logger.debug(f"Logfire: {message}")


class EvaluationEngine:
    """Engine for evaluating answer quality."""

    def __init__(self):
        """Initialize the evaluation engine."""
        logger.info("Initializing EvaluationEngine")
        self.llm_service = get_llm_service()

    @optional_instrument("evaluate_answer_quality")
    def evaluate(
        self,
        question: str,
        answer: str,
        contexts: List[RetrievedContext],
    ) -> EvaluationResults:
        """
        Run all evaluations on an answer.

        Args:
            question: The question asked
            answer: The generated answer
            contexts: Retrieved contexts used

        Returns:
            EvaluationResults with all scores
        """
        logger.info(f"Running evaluations for answer: {answer[:50]}...")

        evaluations = []

        # Run each evaluation
        logger.debug("Running answer_relevance evaluation")
        relevance = self._evaluate_answer_relevance(question, answer)
        evaluations.append(relevance)
        logfire_log(f"Answer relevance score: {relevance.score}", metadata=relevance.dict())

        logger.debug("Running groundedness evaluation")
        groundedness = self._evaluate_groundedness(question, answer, contexts)
        evaluations.append(groundedness)
        logfire_log(f"Groundedness score: {groundedness.score}", metadata=groundedness.dict())

        logger.debug("Running context_relevance evaluation")
        context_relevance = self._evaluate_context_relevance(question, contexts)
        evaluations.append(context_relevance)
        logfire_log(
            f"Context relevance score: {context_relevance.score}",
            metadata=context_relevance.dict(),
        )

        logger.debug("Running entity_accuracy evaluation")
        entity_accuracy = self._evaluate_entity_accuracy(answer, contexts)
        evaluations.append(entity_accuracy)
        logfire_log(f"Entity accuracy score: {entity_accuracy.score}", metadata=entity_accuracy.dict())

        logger.debug("Running answer_completeness evaluation")
        completeness = self._evaluate_answer_completeness(answer)
        evaluations.append(completeness)
        logfire_log(f"Completeness score: {completeness.score}", metadata=completeness.dict())

        # Calculate aggregate score
        avg_score = sum(e.score for e in evaluations) / len(evaluations)
        all_passed = all(e.passed for e in evaluations)

        logger.info(f"Evaluation complete. Average score: {avg_score:.2f}, All passed: {all_passed}")

        results = EvaluationResults(
            evaluations=evaluations,
            average_score=avg_score,
            all_passed=all_passed,
            timestamp=datetime.now(),
        )

        logfire_log(
            "Evaluation results",
            metadata={
                "average_score": avg_score,
                "all_passed": all_passed,
                "evaluation_count": len(evaluations),
            },
        )

        return results

    def _evaluate_answer_relevance(self, question: str, answer: str) -> EvaluationScore:
        """Evaluate if answer addresses the question."""
        logger.debug("Evaluating answer relevance")

        prompt = f"""Question: {question}
Answer: {answer}

Does the answer directly address the question? Score 0-1 where:
0 = Completely irrelevant or doesn't address question
1 = Directly and completely answers the question

Respond with only: SCORE: <number>, REASONING: <brief reason>"""

        try:
            system_prompt = "You are an evaluation assistant. Provide scores and reasoning based on the given criteria."
            result = self.llm_service.raw_call(system_prompt, prompt, temperature=0.1, max_tokens=200)
            score, reasoning = self._parse_evaluation_response(result)

            passed = score >= 0.7
            logger.debug(f"Answer relevance: score={score}, passed={passed}")

            return EvaluationScore(
                name="answer_relevance",
                score=score,
                reasoning=reasoning,
                passed=passed,
            )
        except Exception as e:
            logger.error(f"Answer relevance evaluation failed: {e}")
            return EvaluationScore(
                name="answer_relevance",
                score=0.0,
                reasoning=f"Evaluation failed: {e}",
                passed=False,
            )

    def _evaluate_groundedness(
        self,
        question: str,
        answer: str,
        contexts: List[RetrievedContext],
    ) -> EvaluationScore:
        """Evaluate if answer is grounded in retrieved context."""
        logger.debug("Evaluating groundedness")

        context_text = "\n".join([f"- {ctx.message.message}" for ctx in contexts])

        prompt = f"""Question: {question}
Answer: {answer}
Retrieved Context:
{context_text}

Is the answer supported by the context? Score 0-1 where:
0 = Answer contradicts context or is not mentioned (hallucination)
1 = Answer is fully supported by context

Respond with only: SCORE: <number>, REASONING: <brief reason>"""

        try:
            system_prompt = "You are an evaluation assistant. Provide scores and reasoning based on the given criteria."
            result = self.llm_service.raw_call(system_prompt, prompt, temperature=0.1, max_tokens=200)
            score, reasoning = self._parse_evaluation_response(result)

            passed = score >= 0.8
            logger.debug(f"Groundedness: score={score}, passed={passed}")

            return EvaluationScore(
                name="groundedness",
                score=score,
                reasoning=reasoning,
                passed=passed,
            )
        except Exception as e:
            logger.error(f"Groundedness evaluation failed: {e}")
            return EvaluationScore(
                name="groundedness",
                score=0.0,
                reasoning=f"Evaluation failed: {e}",
                passed=False,
            )

    def _evaluate_context_relevance(
        self,
        question: str,
        contexts: List[RetrievedContext],
    ) -> EvaluationScore:
        """Evaluate if retrieved contexts are relevant to question."""
        logger.debug("Evaluating context relevance")

        context_text = "\n".join([f"- {ctx.message.message}" for ctx in contexts])

        prompt = f"""Question: {question}
Retrieved Messages:
{context_text}

Are the retrieved messages relevant to answering the question? Score 0-1 where:
0 = Messages are irrelevant
1 = Messages are highly relevant and helpful

Respond with only: SCORE: <number>, REASONING: <brief reason>"""

        try:
            system_prompt = "You are an evaluation assistant. Provide scores and reasoning based on the given criteria."
            result = self.llm_service.raw_call(system_prompt, prompt, temperature=0.1, max_tokens=200)
            score, reasoning = self._parse_evaluation_response(result)

            passed = score >= 0.7
            logger.debug(f"Context relevance: score={score}, passed={passed}")

            return EvaluationScore(
                name="context_relevance",
                score=score,
                reasoning=reasoning,
                passed=passed,
            )
        except Exception as e:
            logger.error(f"Context relevance evaluation failed: {e}")
            return EvaluationScore(
                name="context_relevance",
                score=0.0,
                reasoning=f"Evaluation failed: {e}",
                passed=False,
            )

    def _evaluate_entity_accuracy(
        self,
        answer: str,
        contexts: List[RetrievedContext],
    ) -> EvaluationScore:
        """Evaluate accuracy of entity mentions (names, numbers, dates)."""
        logger.debug("Evaluating entity accuracy")

        context_text = "\n".join([f"- {ctx.message.message}" for ctx in contexts])

        prompt = f"""Answer: {answer}
Context:
{context_text}

Check if named entities (people, numbers, dates, places) in the answer are accurate based on context.
Score 0-1 where:
0 = Contains factually incorrect entities
1 = All entities are accurate

Respond with only: SCORE: <number>, REASONING: <brief reason>"""

        try:
            system_prompt = "You are an evaluation assistant. Provide scores and reasoning based on the given criteria."
            result = self.llm_service.raw_call(system_prompt, prompt, temperature=0.1, max_tokens=200)
            score, reasoning = self._parse_evaluation_response(result)

            passed = score >= 0.9
            logger.debug(f"Entity accuracy: score={score}, passed={passed}")

            return EvaluationScore(
                name="entity_accuracy",
                score=score,
                reasoning=reasoning,
                passed=passed,
            )
        except Exception as e:
            logger.error(f"Entity accuracy evaluation failed: {e}")
            return EvaluationScore(
                name="entity_accuracy",
                score=0.0,
                reasoning=f"Evaluation failed: {e}",
                passed=False,
            )

    def _evaluate_answer_completeness(self, answer: str) -> EvaluationScore:
        """Evaluate if answer is complete and not vague."""
        logger.debug("Evaluating answer completeness")

        # Simple heuristic check
        is_empty = len(answer.strip()) == 0
        is_unknown = "don't know" in answer.lower() or "don't have" in answer.lower()
        is_short = len(answer.split()) < 5

        if is_empty:
            score = 0.0
            reasoning = "Answer is empty"
        elif is_unknown:
            score = 0.3
            reasoning = "Answer indicates information not available"
        elif is_short:
            score = 0.6
            reasoning = "Answer is quite short"
        else:
            score = 0.9
            reasoning = "Answer appears complete"

        passed = score >= 0.7
        logger.debug(f"Completeness: score={score}, passed={passed}")

        return EvaluationScore(
            name="answer_completeness",
            score=score,
            reasoning=reasoning,
            passed=passed,
        )

    @staticmethod
    def _parse_evaluation_response(response: str) -> tuple:
        """Parse LLM evaluation response."""
        try:
            response = response.strip()
            score = 0.5
            reasoning = ""

            # Try to extract score - handle multiple formats
            # Format 1: "SCORE: 1, REASONING: ..."
            # Format 2: "1, REASONING: ..."
            # Format 3: Just a number at the start
            
            import re
            
            # Look for "SCORE: <number>" pattern
            score_match = re.search(r'SCORE:\s*([0-9.]+)', response, re.IGNORECASE)
            if score_match:
                score = float(score_match.group(1))
            else:
                # Look for number at start followed by comma or REASONING
                score_match = re.search(r'^([0-9.]+)[,\s]+(?:REASONING:)?', response, re.IGNORECASE)
                if score_match:
                    score = float(score_match.group(1))
                else:
                    # Try to find any number in the response
                    score_match = re.search(r'\b([0-9.]+)\b', response)
                    if score_match:
                        potential_score = float(score_match.group(1))
                        # Only use if it's between 0 and 1 (or 0-10 scale, divide by 10)
                        if 0 <= potential_score <= 1:
                            score = potential_score
                        elif 0 <= potential_score <= 10:
                            score = potential_score / 10.0

            # Extract reasoning
            reasoning_match = re.search(r'REASONING:\s*(.+?)(?:\n|$)', response, re.IGNORECASE | re.DOTALL)
            if reasoning_match:
                reasoning = reasoning_match.group(1).strip()
            else:
                # If no REASONING found, use everything after the score
                if score_match:
                    reasoning = response[score_match.end():].strip()
                    # Remove leading comma/colon if present
                    reasoning = re.sub(r'^[,:\s]+', '', reasoning)
                else:
                    reasoning = response

            # Clamp score to [0, 1]
            score = min(1.0, max(0.0, score))
            
            return score, reasoning
        except Exception as e:
            logger.error(f"Failed to parse evaluation response: {e}")
            logger.error(f"Response was: {response[:200]}")
            return 0.5, f"Parse error: {e}"


# Global evaluation engine instance
_evaluation_engine = None


def get_evaluation_engine() -> EvaluationEngine:
    """Get or create the evaluation engine."""
    global _evaluation_engine
    if _evaluation_engine is None:
        logger.info("Creating new EvaluationEngine instance")
        _evaluation_engine = EvaluationEngine()
    return _evaluation_engine

