# Public API Issues & Bypass Strategies

## Summary

The public API (`https://november7-730026606190.europe-west1.run.app/messages/`) is **unreliable and rate-limited**, but **NOT hard-limited at 1000 messages**. With proper error handling, we can fetch significantly more messages.

## Issues Encountered

### 1. **400 Bad Request**
- **When**: Random skip values (e.g., skip=700)
- **Cause**: API server-side validation errors or bugs
- **Bypass**: Retry with exponential backoff, skip range if persistent

### 2. **401 Unauthorized**
- **When**: After multiple rapid requests
- **Cause**: Rate limiting or authentication issues
- **Bypass**: Retry with delays, exponential backoff

### 3. **402 Payment Required** ⚠️
- **When**: After fetching ~1000 messages with our original 1s delay pattern
- **Cause**: Rate limiting triggered by cumulative request count/frequency
- **Bypass**: 
  - Increased base delay to 2.5s between requests
  - One retry attempt, then gracefully stop and index what we have
  - **Note**: This is NOT a hard limit - with proper delays, we can fetch more

### 4. **403 Forbidden**
- **When**: After many requests or specific skip values
- **Cause**: Rate limiting or IP-based blocking
- **Bypass**: Exponential backoff, back off after 3 consecutive errors

### 5. **404 Not Found**
- **When**: Random skip values (e.g., skip=400, skip=2300)
- **Cause**: API server bugs or missing data pages
- **Bypass**: Skip the range and continue fetching

### 6. **405 Method Not Allowed**
- **When**: Random occurrences
- **Cause**: API server configuration issues
- **Bypass**: Retry with exponential backoff

### 7. **429 Too Many Requests**
- **When**: Rapid sequential requests
- **Cause**: Rate limiting
- **Bypass**: Exponential backoff, increase delays

### 8. **Timeouts (>30s)**
- **When**: Specific skip values (e.g., skip=2200)
- **Cause**: Slow API responses under load
- **Bypass**: Retry with exponential backoff, skip if persistent

## Our Bypass Strategies

### 1. **Increased Base Delays**
- **Original**: 1.0 second between requests
- **Current**: 2.5 seconds between requests
- **Impact**: Reduces rate limiting significantly

### 2. **Exponential Backoff**
- **Formula**: `base_delay * (2^attempt)` (capped at 16x)
- **Example**: 2.5s → 5s → 10s → 20s
- **Impact**: Gives API time to recover from rate limits

### 3. **Consecutive Error Handling**
- **Threshold**: 3 consecutive errors
- **Action**: 30-second backoff, then reset counter
- **Impact**: Prevents hammering API during outages

### 4. **Graceful Degradation**
- **Strategy**: Continue with partial data if API blocks
- **Tracking**: 
  - `expected_total_messages`: Total according to API (3349)
  - `fetched_messages`: Successfully retrieved
  - `missed_messages`: Couldn't be fetched
  - `missed_ranges`: List of failed skip ranges
- **Impact**: System remains functional even with partial data

### 5. **Smart Retry Logic**
- **402/403**: One retry, then stop (hard limits)
- **Other errors**: Up to 2 retries with exponential backoff
- **404**: Skip range and continue
- **Impact**: Balances data completeness with API stability

### 6. **Range Skipping**
- **Strategy**: Skip failed ranges and continue fetching
- **Tracking**: Log all missed ranges for analysis
- **Impact**: Maximizes data retrieval despite intermittent failures

## Current Status

### What We Can Access
- **With 2.5s delays**: Successfully fetched 1400+ messages in testing
- **With proper error handling**: Can fetch most of the 3349 messages
- **No hard limit**: The API doesn't block at exactly 1000 messages

### What Happens in Practice
- **Typical fetch**: 1000-2000+ messages depending on API conditions
- **Missed messages**: Usually 1000-2000 due to rate limiting
- **System behavior**: Indexes whatever is successfully fetched

## Recommendations

1. **Monitor API patterns**: Track which skip values consistently fail
2. **Adjust delays**: If 402 occurs frequently, increase base delay to 3-4s
3. **Batch retries**: Consider retrying failed ranges later in a separate pass
4. **Cache results**: Store successfully fetched messages to avoid re-fetching

## Error Handling Flow

```
Request → Success? 
  ├─ Yes → Continue fetching
  └─ No → Check error code
      ├─ 402/403 → Retry once → Still fail? → Stop gracefully
      ├─ 404 → Skip range → Continue
      ├─ 400/401/405/429 → Retry with exponential backoff
      └─ Timeout → Retry with exponential backoff
```

## Conclusion

The API is **unreliable but not hard-limited**. With proper error handling, exponential backoff, and graceful degradation, we can fetch a significant portion of the available messages (typically 1000-2000+ out of 3349). The system is designed to work with partial data, ensuring it remains functional even when the API is problematic.

