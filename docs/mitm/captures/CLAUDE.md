# Exhaustive HTTP Capture Analysis

## Directory Structure

- **convo-{N}.txt** - Copy of User-side inputs (one line = one submission) of User/Assistant conversation
- **convo-{N}/** - Individual conversation capture directories
  - `{N}_request.txt` - HTTP request N from Claude Code to Claude API
  - `{N}_response.txt` - HTTP response N from Claude API to Claude Code

## Exhaustive Analysis Commands

### Deep Structure Discovery
```bash
# Explore ALL keys in request payloads
find . -name "*_request.txt" -exec sh -c 'echo "=== {} ==="; python scripts/extract_json.py {} | jq -r "keys"' \;

# Discover ALL unique message fields across all requests
find . -name "*_request.txt" -exec python scripts/extract_json.py {} \; | jq -s 'map(.messages[]? | keys) | flatten | unique | sort'

# Extract EVERY field from messages with recursive depth
find . -name "*_request.txt" -exec sh -c 'python scripts/extract_json.py {} | jq -r ".messages[]? | to_entries | .[]"' \;
```

### Cache Control Deep Dive
```bash
# Find ALL cache_control variations and contexts
find . -name "*_request.txt" -exec sh -c 'echo "=== {} ==="; python scripts/extract_json.py {} | jq -r ".. | .cache_control? // empty"' \;

# Extract complete message structure when cache_control exists
find . -name "*_request.txt" -exec sh -c 'python scripts/extract_json.py {} | jq -r ".messages[]? | select(.cache_control != null)"' \;

# Map cache_control usage by position in message array
find . -name "*_request.txt" -exec sh -c 'python scripts/extract_json.py {} | jq -r ".messages | to_entries | map(select(.value.cache_control != null) | {index: .key, cache: .value.cache_control})"' \;
```

### Pattern Mining
```bash
# Extract ALL tool use patterns
find . -name "*_request.txt" -exec sh -c 'python scripts/extract_json.py {} | jq -r ".messages[]? | select(.tool_use != null)"' \;

# Find ALL content variations (text, tool_use, cache_control combinations)
find . -name "*_request.txt" -exec sh -c 'python scripts/extract_json.py {} | jq -r ".messages[]? | {role, has_text: (.content | type == \"string\"), has_tool_use: (.tool_use != null), has_cache: (.cache_control != null)}"' \;

# Discover ALL metadata fields beyond standard message structure
find . -name "*_request.txt" -exec sh -c 'python scripts/extract_json.py {} | jq -r ". | del(.messages) | keys"' \;
```

### Response Analysis
```bash
# Extract ALL fields from responses
find . -name "*_response.txt" -exec sh -c 'echo "=== {} ==="; python scripts/extract_json.py {} | jq -r "keys"' \;

# Find ALL response content types and structures
find . -name "*_response.txt" -exec sh -c 'python scripts/extract_json.py {} | jq -r ".content[]? | {type: .type, has_text: (.text != null), has_tool_use: (.tool_use != null)}"' \;
```

### Cross-Reference Analysis
```bash
# Compare request/response pairs exhaustively
for i in {1..20}; do
  req="convo-1/${i}_request.txt"
  res="convo-1/${i}_response.txt"
  if [[ -f "$req" && -f "$res" ]]; then
    echo "=== Pair $i ==="
    echo "Request fields: $(python scripts/extract_json.py "$req" | jq -r 'keys | join(", ")')"
    echo "Response fields: $(python scripts/extract_json.py "$res" | jq -r 'keys | join(", ")')"
  fi
done
```

## Analysis Directives

- **IMPERATIVE**: Leave no field unexplored - extract and analyze EVERY JSON path
- **CRITICAL**: Discover ALL patterns, not just cache_control - tool use, content types, metadata
- **IMPORTANT**: Cross-reference request/response pairs to understand full conversation flow
- **MANDATORY**: Use recursive jq queries to find nested structures at any depth

