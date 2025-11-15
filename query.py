#!/usr/bin/env python3
"""
Simple CLI script to query the Aurora QA System.

Usage:
    python query.py "Your question here"
    python query.py "Summarise Fatima's messages?" --sources --evaluations
"""

import sys
import json
import argparse
import requests
from typing import Optional


def query_aurora(
    question: str,
    base_url: str = "http://localhost:8000",
    include_sources: bool = False,
    include_evaluations: bool = False,
    max_sources: Optional[int] = None,
) -> dict:
    """
    Query the Aurora QA System.
    
    Args:
        question: The question to ask
        base_url: Base URL of the Aurora API
        include_sources: Whether to include source messages
        include_evaluations: Whether to include evaluation metrics
        max_sources: Maximum number of sources to use (default: 10, max: 50)
        
    Returns:
        Response dictionary from the API
    """
    url = f"{base_url}/ask"
    payload = {
        "question": question,
        "include_sources": include_sources,
        "include_evaluations": include_evaluations,
    }
    if max_sources is not None:
        payload["max_sources"] = max_sources
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error querying API: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def format_response(response: dict, verbose: bool = False) -> str:
    """
    Format the API response for display.
    
    Args:
        response: API response dictionary
        verbose: Whether to show detailed information
        
    Returns:
        Formatted string
    """
    output = []
    
    # Answer
    output.append("=" * 80)
    output.append("ANSWER")
    output.append("=" * 80)
    output.append(response.get("answer", "No answer provided"))
    output.append("")
    
    # Confidence and Query Type
    output.append("=" * 80)
    output.append("RELIABILITY METRICS")
    output.append("=" * 80)
    
    confidence = response.get("confidence", 0)
    confidence_percent = confidence * 100
    
    # Visual confidence indicator
    if confidence >= 0.8:
        confidence_indicator = "HIGH"
    elif confidence >= 0.6:
        confidence_indicator = "MODERATE"
    else:
        confidence_indicator = "LOW"
    
    output.append(f"Confidence: {confidence_indicator} ({confidence_percent:.0f}%)")
    
    # Query metadata
    if "query_metadata" in response and response["query_metadata"]:
        metadata = response["query_metadata"]
        output.append(f"Query Type: {metadata.get('query_type', 'unknown')}")
        if metadata.get("mentioned_users"):
            output.append(f"Users: {', '.join(metadata['mentioned_users'])}")
    
    # Tips
    if "tips" in response and response["tips"]:
        output.append(f"\n💡 {response['tips']}")
    
    output.append("")
    
    # Token usage
    if "token_usage" in response and response["token_usage"]:
        usage = response["token_usage"]
        output.append(f"Tokens: {usage.get('total_tokens', 0)} "
                     f"({usage.get('prompt_tokens', 0)} prompt + "
                     f"{usage.get('completion_tokens', 0)} completion)")
        output.append(f"Cost: ${usage.get('cost_usd', 0):.6f}")
        output.append("")
    
    # Latency
    output.append(f"Latency: {response.get('latency_ms', 0):.1f}ms")
    output.append("")
    
    # Sources
    if "sources" in response and response["sources"]:
        output.append("=" * 80)
        output.append(f"SOURCES ({len(response['sources'])} messages)")
        output.append("=" * 80)
        for i, source in enumerate(response["sources"], 1):
            output.append(f"\n[{i}] {source.get('user_name', 'Unknown')}")
            output.append(f"    {source.get('message', '')[:200]}")
            if verbose:
                output.append(f"    Score: {source.get('similarity_score', 0):.4f}")
                if 'reranker_score' in source:
                    output.append(f"    Reranker: {source.get('reranker_score', 0):.4f}")
        output.append("")
    
    # Evaluations
    if "evaluations" in response and response["evaluations"]:
        evals = response["evaluations"]
        output.append("=" * 80)
        output.append("EVALUATIONS")
        output.append("=" * 80)
        if "evaluations" in evals:
            for eval_item in evals["evaluations"]:
                status = "PASS" if eval_item.get("passed", False) else "FAIL"
                output.append(f"{status} {eval_item.get('name', 'unknown')}: "
                            f"{eval_item.get('score', 0):.2f}")
                if verbose:
                    output.append(f"   {eval_item.get('reasoning', '')}")
        if "average_score" in evals:
            output.append(f"\nAverage Score: {evals['average_score']:.2f}")
        output.append("")
    
    return "\n".join(output)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Query the Aurora QA System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python query.py "What are Fatima's favorite restaurants?"
  python query.py "Summarise Fatima's messages?" --sources --evaluations
  python query.py "How many cars does Vikram have?" --verbose
        """
    )
    
    parser.add_argument(
        "question",
        nargs="?",
        help="The question to ask (or read from stdin if not provided)"
    )
    parser.add_argument(
        "--sources",
        action="store_true",
        help="Include source messages in response"
    )
    parser.add_argument(
        "--evaluations",
        action="store_true",
        help="Include evaluation metrics in response"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information (scores, reasoning)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the Aurora API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text"
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=None,
        metavar="N",
        help="Maximum number of sources to use (default: 10 for general queries, ALL for user-specific queries like 'Summarise X's messages'). Set to None to use all messages."
    )
    
    args = parser.parse_args()
    
    # Get question from argument or stdin
    if args.question:
        question = args.question
    elif not sys.stdin.isatty():
        question = sys.stdin.read().strip()
    else:
        parser.print_help()
        sys.exit(1)
    
    if not question:
        print("Error: Question cannot be empty", file=sys.stderr)
        sys.exit(1)
    
    # Query the API
    response = query_aurora(
        question=question,
        base_url=args.url,
        include_sources=args.sources,
        include_evaluations=args.evaluations,
        max_sources=args.max_sources,
    )
    
    # Output results
    if args.json:
        print(json.dumps(response, indent=2))
    else:
        print(format_response(response, verbose=args.verbose))


if __name__ == "__main__":
    main()

