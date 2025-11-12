#!/usr/bin/env python3
"""
Test script to run relevant queries and verify results.

Usage:
    python test_queries.py
"""

import subprocess
import json
import sys

# Test queries - no hardcoded expectations, just test semantic understanding
TEST_QUERIES = [
    "What is Vikram Desai talking about in his messages?",
    "What is Sophia Al-Farsi talking about in her messages?",
    "How was Thiago's trip?",
    "How was Thaigo's trip?",  # Typo test
    "What did Fatima request?",
    "What did Fatimah request?",  # Typo test
    "Summarise Fatima's messages",
    "What are Vikram's travel plans?",
    "Tell me about Layla's requests",
    "What did Sophia ask for?",
]

def run_query(query: str) -> dict:
    """Run a query and return the response."""
    try:
        result = subprocess.run(
            ["python", "query.py", query, "--sources", "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(f"Error running query: {result.stderr}", file=sys.stderr)
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Exception running query: {e}", file=sys.stderr)
        return None

def main():
    """Run test queries and display results."""
    print("=" * 80)
    print("TESTING QUERIES")
    print("=" * 80)
    print()
    
    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"[{i}/{len(TEST_QUERIES)}] Query: {query}")
        
        response = run_query(query)
        
        if not response:
            print(f"  ❌ FAILED: Could not get response")
            print()
            continue
        
        answer = response.get("answer", "")
        sources = response.get("sources", [])
        sources_users = [s.get("user_name") for s in sources]
        
        print(f"  Answer: {answer[:150]}...")
        print(f"  Sources ({len(sources)}): {', '.join(set(sources_users))}")
        print()
    
    print("=" * 80)
    print("Testing complete")
    print("=" * 80)

if __name__ == "__main__":
    main()

