#!/usr/bin/env python3
"""
Comprehensive anomaly detection for member data.

Detects and reports:
1. Inconsistent Message IDs (same ID with different content/user/timestamp)
2. Temporal Anomalies (multiple messages with same timestamp)
3. Duplicate Message Content (identical messages repeated)
4. User ID Inconsistencies (one user_id mapped to multiple users or vice versa)
5. Malformed Data (empty fields, invalid formats, suspicious patterns)
6. Message Content Anomalies (extremely short/long, special characters, patterns)
7. Timestamp Order Violations (timestamps not in order for same user)
8. User Name Formatting Issues (whitespace, case sensitivity)

Note: Duplicate IDs with identical content are expected API pagination behavior, not anomalies.

Usage:
    python anomaly_detection.py
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set
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
                break
            
            all_messages.extend(paginated.items)
            consecutive_errors = 0
            consecutive_skips = 0
            
            if len(all_messages) % 500 == 0:
                print(f"Progress: {len(all_messages)}/{expected_total} ({len(all_messages)/expected_total*100:.1f}%)")
            
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
                    break
                skip += 100
                import time
                time.sleep(base_delay * 2)
                continue
            
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                break
            
            retry_success = False
            for retry_num in range(retry_attempts):
                import time
                retry_delay = base_delay * (2 ** (retry_num + 1))
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
    
    print(f"Fetched {len(all_messages)} messages total\n")
    return all_messages


def detect_anomalies(messages: List[Message]) -> Dict:
    """Detect all anomalies in the dataset."""
    
    print("=" * 80)
    print("ANOMALY DETECTION")
    print("=" * 80)
    
    results = {
        "total_messages": len(messages),
        "anomalies": [],
        "summary": {}
    }
    
    # Group by user
    messages_by_user = defaultdict(list)
    for msg in messages:
        messages_by_user[msg.user_name].append(msg)
    
    # =========================================================================
    # ANOMALY 1: Inconsistent Message IDs (Same ID with different content)
    # =========================================================================
    print("\n[1] Detecting Inconsistent Message IDs...")
    
    # Group by message ID
    id_groups = defaultdict(list)
    for msg in messages:
        id_groups[msg.id].append(msg)
    
    # Find IDs that have different content/user/timestamp (real inconsistency)
    inconsistent_ids = []
    for msg_id, msg_group in id_groups.items():
        if len(msg_group) > 1:
            # Check if all messages with this ID are identical
            first_msg = msg_group[0]
            for other_msg in msg_group[1:]:
                # Same ID but different content, user, or timestamp = anomaly
                if (other_msg.message != first_msg.message or 
                    other_msg.user_name != first_msg.user_name or
                    other_msg.user_id != first_msg.user_id or
                    other_msg.timestamp != first_msg.timestamp):
                    inconsistent_ids.append({
                        "id": msg_id,
                        "group": msg_group
                    })
                    break
    
    if inconsistent_ids:
        print(f"⚠️  Found {len(inconsistent_ids)} message IDs with inconsistent data")
        print(f"\nExamples of inconsistencies:")
        for i, item in enumerate(inconsistent_ids[:3], 1):
            print(f"\n   Example {i}:")
            print(f"   Message ID: {item['id']}")
            print(f"   Same ID, different content/user/timestamp:")
            for j, msg in enumerate(item['group'][:2], 1):
                print(f"     {j}. User: {msg.user_name}")
                print(f"        Message: '{msg.message[:60]}...'")
                print(f"        Timestamp: {msg.timestamp}")
        
        results["anomalies"].append({
            "type": "inconsistent_message_ids",
            "count": len(inconsistent_ids),
            "details": f"{len(inconsistent_ids)} message IDs with inconsistent data"
        })
    else:
        print("✓ No inconsistent message IDs found (duplicate IDs with identical content are expected API pagination)")
    
    # =========================================================================
    # ANOMALY 2: Temporal Anomalies (Multiple messages with same timestamp)
    # =========================================================================
    print("\n[2] Detecting Temporal Anomalies...")
    temporal_issues = []
    
    for user_name, user_messages in messages_by_user.items():
        timestamp_counts = defaultdict(list)
        for msg in user_messages:
            timestamp_counts[msg.timestamp].append(msg)
        
        same_timestamp = {ts: msgs for ts, msgs in timestamp_counts.items() if len(msgs) > 1}
        if same_timestamp:
            total_affected = sum(len(msgs) for msgs in same_timestamp.values())
            temporal_issues.append({
                "user": user_name,
                "affected_messages": total_affected,
                "duplicate_timestamps": len(same_timestamp),
                "examples": same_timestamp
            })
    
    if temporal_issues:
        total_temporal = sum(issue["affected_messages"] for issue in temporal_issues)
        print(f"⚠️  Found {total_temporal} messages with temporal anomalies across {len(temporal_issues)} users")
        print(f"\nExamples of temporal anomalies:")
        for i, issue in enumerate(temporal_issues[:2], 1):
            print(f"\n   Example {i}: {issue['user']}")
            print(f"   Affected messages: {issue['affected_messages']}")
            print(f"   Duplicate timestamps: {issue['duplicate_timestamps']}")
            
            # Show one example timestamp group
            example_ts, example_msgs = next(iter(issue['examples'].items()))
            print(f"   Timestamp: {example_ts}")
            for j, msg in enumerate(example_msgs[:2], 1):
                print(f"     Message {j}: '{msg.message[:60]}...'")
        
        results["anomalies"].append({
            "type": "temporal_anomalies",
            "total_affected": total_temporal,
            "users_affected": len(temporal_issues),
            "percentage": round(total_temporal / len(messages) * 100, 2),
            "details": f"{total_temporal} messages ({total_temporal / len(messages) * 100:.2f}%) with identical timestamps"
        })
    else:
        print("✓ No temporal anomalies found")
    
    # =========================================================================
    # ANOMALY 3: Duplicate Message Content
    # =========================================================================
    print("\n[3] Detecting Duplicate Message Content...")
    
    message_content_counts = defaultdict(list)
    for msg in messages:
        message_content_counts[msg.message].append(msg)
    
    duplicate_content = {content: msgs for content, msgs in message_content_counts.items() if len(msgs) > 1}
    
    if duplicate_content:
        total_duplicate_content = sum(len(msgs) - 1 for msgs in duplicate_content.values())
        print(f"⚠️  Found {len(duplicate_content)} unique messages repeated")
        print(f"   Total duplicate instances: {total_duplicate_content}")
        print(f"\nExamples of duplicate content:")
        
        sorted_duplicates = sorted(duplicate_content.items(), key=lambda x: len(x[1]), reverse=True)
        for i, (content, duplicate_msgs) in enumerate(sorted_duplicates[:3], 1):
            users = set(m.user_name for m in duplicate_msgs)
            print(f"\n   Example {i}:")
            print(f"   Message: '{content[:70]}...'")
            print(f"   Repeated {len(duplicate_msgs)} times by {len(users)} users:")
            for user in list(users)[:3]:
                print(f"     - {user}")
        
        results["anomalies"].append({
            "type": "duplicate_message_content",
            "unique_duplicates": len(duplicate_content),
            "total_duplicate_instances": total_duplicate_content,
            "percentage": round(total_duplicate_content / len(messages) * 100, 2),
            "details": f"{len(duplicate_content)} unique messages repeated {total_duplicate_content} times"
        })
    else:
        print("✓ No duplicate message content found")
    
    # =========================================================================
    # ANOMALY 4: User ID Inconsistencies
    # =========================================================================
    print("\n[4] Detecting User ID Inconsistencies...")
    
    user_id_to_names = defaultdict(set)
    user_name_to_ids = defaultdict(set)
    
    for msg in messages:
        user_id_to_names[msg.user_id].add(msg.user_name)
        user_name_to_ids[msg.user_name].add(msg.user_id)
    
    # Find inconsistencies
    id_to_multiple_names = {uid: names for uid, names in user_id_to_names.items() if len(names) > 1}
    name_to_multiple_ids = {name: ids for name, ids in user_name_to_ids.items() if len(ids) > 1}
    
    if id_to_multiple_names or name_to_multiple_ids:
        print(f"⚠️  Found user ID inconsistencies:")
        
        if id_to_multiple_names:
            print(f"   One user_id mapped to multiple user names: {len(id_to_multiple_names)}")
            for i, (uid, names) in enumerate(list(id_to_multiple_names.items())[:2], 1):
                print(f"   Example {i}: ID {uid[:20]}... → {list(names)}")
            
            results["anomalies"].append({
                "type": "user_id_to_multiple_names",
                "count": len(id_to_multiple_names),
                "details": f"{len(id_to_multiple_names)} user IDs mapped to multiple names"
            })
        
        if name_to_multiple_ids:
            print(f"   One user name mapped to multiple IDs: {len(name_to_multiple_ids)}")
            for i, (name, ids) in enumerate(list(name_to_multiple_ids.items())[:2], 1):
                print(f"   Example {i}: '{name}' → {[uid[:20] + '...' for uid in ids]}")
            
            results["anomalies"].append({
                "type": "user_name_to_multiple_ids",
                "count": len(name_to_multiple_ids),
                "details": f"{len(name_to_multiple_ids)} user names mapped to multiple IDs"
            })
    else:
        print("✓ No user ID inconsistencies found")
    
    # =========================================================================
    # ANOMALY 5: Malformed Data
    # =========================================================================
    print("\n[5] Detecting Malformed Data...")
    
    malformed_issues = []
    
    # Check for empty/null fields
    for msg in messages:
        if not msg.id or len(msg.id.strip()) == 0:
            malformed_issues.append({"type": "empty_id", "msg": msg})
        if not msg.user_id or len(msg.user_id.strip()) == 0:
            malformed_issues.append({"type": "empty_user_id", "msg": msg})
        if not msg.user_name or len(msg.user_name.strip()) == 0:
            malformed_issues.append({"type": "empty_user_name", "msg": msg})
        if not msg.message or len(msg.message.strip()) == 0:
            malformed_issues.append({"type": "empty_message", "msg": msg})
        if not msg.timestamp or len(msg.timestamp.strip()) == 0:
            malformed_issues.append({"type": "empty_timestamp", "msg": msg})
    
    if malformed_issues:
        print(f"⚠️  Found {len(malformed_issues)} malformed messages:")
        for issue in malformed_issues[:3]:
            print(f"   • {issue['type']}: User {issue['msg'].user_name}")
        
        results["anomalies"].append({
            "type": "malformed_data",
            "count": len(malformed_issues),
            "details": f"{len(malformed_issues)} messages with empty/null fields"
        })
    else:
        print("✓ No malformed data found")
    
    # =========================================================================
    # ANOMALY 6: Message Content Anomalies
    # =========================================================================
    print("\n[6] Detecting Message Content Anomalies...")
    
    content_anomalies = []
    message_lengths = [len(msg.message) for msg in messages]
    
    # Very short messages (< 5 chars)
    very_short = [msg for msg in messages if len(msg.message) < 5]
    if very_short:
        content_anomalies.append({
            "type": "very_short_messages",
            "count": len(very_short),
            "examples": very_short[:2]
        })
        print(f"⚠️  Found {len(very_short)} very short messages (< 5 chars):")
        for msg in very_short[:2]:
            print(f"   • '{msg.message}' (User: {msg.user_name})")
    
    # Very long messages (> 500 chars)
    very_long = [msg for msg in messages if len(msg.message) > 500]
    if very_long:
        content_anomalies.append({
            "type": "very_long_messages",
            "count": len(very_long),
            "examples": very_long[:2]
        })
        print(f"⚠️  Found {len(very_long)} very long messages (> 500 chars):")
        for msg in very_long[:2]:
            print(f"   • {len(msg.message)} chars (User: {msg.user_name})")
    
    # Messages with unusual characters (many special chars)
    unusual_char_msgs = [msg for msg in messages if sum(1 for c in msg.message if not c.isalnum() and c not in ' .,!?-\'":;()') > len(msg.message) * 0.5]
    if unusual_char_msgs:
        content_anomalies.append({
            "type": "messages_with_unusual_characters",
            "count": len(unusual_char_msgs),
            "examples": unusual_char_msgs[:2]
        })
        print(f"⚠️  Found {len(unusual_char_msgs)} messages with unusual character patterns:")
        for msg in unusual_char_msgs[:2]:
            print(f"   • '{msg.message[:60]}...' (User: {msg.user_name})")
    
    if content_anomalies:
        for anom in content_anomalies:
            results["anomalies"].append(anom)
    else:
        print("✓ No message content anomalies found")
    
    # =========================================================================
    # ANOMALY 7: Timestamp Order Violations
    # =========================================================================
    print("\n[7] Detecting Timestamp Order Violations...")
    
    order_violations = []
    
    for user_name, user_messages in messages_by_user.items():
        # Sort by timestamp and check if order differs from original
        sorted_msgs = sorted(user_messages, key=lambda x: x.timestamp)
        
        # Count how many are out of order
        out_of_order_count = 0
        for i in range(len(sorted_msgs) - 1):
            # Check if next message in chronological order is NOT next in original order
            if sorted_msgs[i] != user_messages[user_messages.index(sorted_msgs[i]) if sorted_msgs[i] in user_messages else -1]:
                out_of_order_count += 1
        
        # If more than 50% are out of order, flag it
        if out_of_order_count > len(user_messages) * 0.5:
            order_violations.append({
                "user": user_name,
                "out_of_order_percentage": round(out_of_order_count / len(user_messages) * 100, 1),
                "total_messages": len(user_messages)
            })
    
    if order_violations:
        print(f"⚠️  Found {len(order_violations)} users with significant timestamp ordering issues:")
        for issue in order_violations[:3]:
            print(f"   • {issue['user']}: {issue['out_of_order_percentage']}% out of order")
        
        results["anomalies"].append({
            "type": "timestamp_order_violations",
            "count": len(order_violations),
            "details": "Note: This is expected API behavior (pagination returns messages in any order)"
        })
    else:
        print("✓ No critical timestamp order violations found")
    
    # =========================================================================
    # ANOMALY 8: User Name Formatting Issues
    # =========================================================================
    print("\n[8] Detecting User Name Formatting Issues...")
    
    formatting_issues = []
    
    # Check for leading/trailing whitespace
    whitespace_issues = [name for name in user_name_to_ids.keys() if name != name.strip() or '  ' in name]
    if whitespace_issues:
        formatting_issues.append({
            "type": "whitespace_issues",
            "count": len(whitespace_issues),
            "examples": whitespace_issues[:2]
        })
        print(f"⚠️  Found {len(whitespace_issues)} user names with whitespace issues:")
        for name in whitespace_issues[:2]:
            print(f"   • '{name}' (has leading/trailing spaces or double spaces)")
    
    # Check for case sensitivity issues
    case_issues = defaultdict(set)
    for name in user_name_to_ids.keys():
        case_issues[name.lower()].add(name)
    
    case_duplicates = {lower: names for lower, names in case_issues.items() if len(names) > 1}
    if case_duplicates:
        formatting_issues.append({
            "type": "case_sensitivity_issues",
            "count": len(case_duplicates),
            "examples": case_duplicates
        })
        print(f"⚠️  Found {len(case_duplicates)} potential case sensitivity issues:")
        for lower, names in list(case_duplicates.items())[:2]:
            print(f"   • {list(names)} (different cases)")
    
    if formatting_issues:
        for issue in formatting_issues:
            results["anomalies"].append(issue)
    else:
        print("✓ No user name formatting issues found")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    total_anomaly_count = len(results["anomalies"])
    print(f"Total messages analyzed: {len(messages)}")
    print(f"Anomalies detected: {total_anomaly_count}")
    
    if results["anomalies"]:
        print("\nAnomalies found:")
        for anom in results["anomalies"]:
            print(f"  • {anom['type']}: {anom['details']}")
    else:
        print("\n✓ No anomalies detected!")
    
    results["summary"] = {
        "total_messages": len(messages),
        "anomaly_count": total_anomaly_count,
        "status": "clean" if total_anomaly_count == 0 else "issues_found"
    }
    
    return results


def main():
    """Main entry point."""
    try:
        # Fetch all messages
        messages = fetch_all_messages()
        
        if not messages:
            print("No messages fetched. Exiting.")
            sys.exit(1)
        
        # Detect anomalies
        results = detect_anomalies(messages)
        
        # Save results
        output_file = "anomalies_report.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Analysis complete! Report saved to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

