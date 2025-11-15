#!/usr/bin/env python3
"""
Extract all messages from the API and group them by user.

Usage:
    python extract_messages.py [--format json|markdown] [--output filename]
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import requests

from app.config import get_settings
from app.models import Message, PaginatedMessages


def fetch_all_messages() -> List[Message]:
    """Fetch all messages from the API."""
    settings = get_settings()
    api_url = settings.external_api_url
    
    all_messages = []
    skip = 0
    expected_total = None
    base_delay = 2.5
    retry_attempts = 2
    max_consecutive_errors = 3
    max_consecutive_skips = 10
    consecutive_errors = 0
    consecutive_skips = 0
    
    print(f"Fetching messages from {api_url}...")
    print("=" * 80)
    
    while True:
        try:
            response = requests.get(
                f"{api_url}/messages/",
                params={"skip": skip, "limit": 100},
                timeout=30,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            
            data = response.json()
            paginated = PaginatedMessages(**data)
            
            if expected_total is None:
                expected_total = paginated.total
                print(f"Total messages in API: {expected_total}")
            
            if len(paginated.items) == 0:
                print(f"\nReached end at skip={skip}")
                break
            
            all_messages.extend(paginated.items)
            consecutive_errors = 0
            consecutive_skips = 0
            
            if len(all_messages) % 500 == 0:
                print(f"Progress: {len(all_messages)}/{expected_total} messages ({len(all_messages)/expected_total*100:.1f}%)")
            
            if len(all_messages) >= expected_total or skip >= expected_total:
                break
            
            skip += 100
            import time
            time.sleep(base_delay)
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            
            if status_code == 404:
                consecutive_skips += 1
                if consecutive_skips >= max_consecutive_skips:
                    print(f"\nReached {max_consecutive_skips} consecutive skips. Stopping.")
                    break
                skip += 100
                import time
                time.sleep(base_delay * 2)
                continue
            
            consecutive_errors += 1
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"\nToo many consecutive errors ({consecutive_errors}). Stopping.")
                break
            
            # Retry logic
            retry_success = False
            for retry_num in range(retry_attempts):
                import time
                retry_delay = base_delay * (2 ** (retry_num + 1))
                print(f"  Retrying after {retry_delay:.1f}s... (attempt {retry_num + 1}/{retry_attempts})")
                time.sleep(retry_delay)
                
                try:
                    retry_response = requests.get(
                        f"{api_url}/messages/",
                        params={"skip": skip, "limit": 100},
                        timeout=30,
                        headers={"Accept": "application/json"},
                    )
                    retry_response.raise_for_status()
                    retry_data = retry_response.json()
                    retry_paginated = PaginatedMessages(**retry_data)
                    all_messages.extend(retry_paginated.items)
                    retry_success = True
                    break
                except Exception:
                    continue
            
            if not retry_success:
                skip += 100
                import time
                time.sleep(base_delay * 2)
                
        except Exception as e:
            print(f"Error at skip={skip}: {e}")
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                break
            skip += 100
            import time
            time.sleep(base_delay * 2)
    
    print(f"\nFetched {len(all_messages)} messages total")
    return all_messages


def group_by_user(messages: List[Message]) -> Dict[str, List[Message]]:
    """Group messages by user name."""
    grouped = defaultdict(list)
    for msg in messages:
        grouped[msg.user_name].append(msg)
    
    # Sort messages by timestamp within each user
    for user_name in grouped:
        grouped[user_name].sort(key=lambda x: x.timestamp)
    
    return dict(grouped)


def save_json(grouped_messages: Dict[str, List[Message]], output_file: str):
    """Save grouped messages as JSON."""
    output_data = {}
    for user_name, messages in grouped_messages.items():
        output_data[user_name] = [
            {
                "id": msg.id,
                "user_id": msg.user_id,
                "timestamp": msg.timestamp,
                "message": msg.message,
            }
            for msg in messages
        ]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {output_file} (JSON format)")


def save_markdown(grouped_messages: Dict[str, List[Message]], output_file: str):
    """Save grouped messages as Markdown."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Messages by User\n\n")
        f.write(f"Extracted on: {datetime.now().isoformat()}\n\n")
        f.write(f"Total users: {len(grouped_messages)}\n")
        f.write(f"Total messages: {sum(len(msgs) for msgs in grouped_messages.values())}\n\n")
        f.write("=" * 80 + "\n\n")
        
        # Sort users by number of messages (descending)
        sorted_users = sorted(grouped_messages.items(), key=lambda x: len(x[1]), reverse=True)
        
        for user_name, messages in sorted_users:
            f.write(f"## {user_name}\n\n")
            f.write(f"**User ID:** `{messages[0].user_id}`  \n")
            f.write(f"**Total Messages:** {len(messages)}\n\n")
            
            for i, msg in enumerate(messages, 1):
                f.write(f"### Message {i}\n\n")
                f.write(f"**Timestamp:** {msg.timestamp}  \n")
                f.write(f"**ID:** `{msg.id}`  \n\n")
                f.write(f"{msg.message}\n\n")
            
            f.write("---\n\n")
    
    print(f"Saved to {output_file} (Markdown format)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract all messages from API and group by user",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output filename (default: messages_by_user.{format})"
    )
    
    args = parser.parse_args()
    
    # Fetch all messages
    messages = fetch_all_messages()
    
    if not messages:
        print("No messages fetched. Exiting.")
        sys.exit(1)
    
    # Group by user
    print("\nGrouping messages by user...")
    grouped = group_by_user(messages)
    
    print(f"\nFound {len(grouped)} unique users:")
    for user_name, user_messages in sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  - {user_name}: {len(user_messages)} messages")
    
    # Determine output filename
    if args.output:
        output_file = args.output
    else:
        extension = "md" if args.format == "markdown" else "json"
        output_file = f"messages_by_user.{extension}"
    
    # Save
    if args.format == "json":
        save_json(grouped, output_file)
    else:
        save_markdown(grouped, output_file)
    
    print(f"\nExtraction complete! Output: {output_file}")


if __name__ == "__main__":
    main()



