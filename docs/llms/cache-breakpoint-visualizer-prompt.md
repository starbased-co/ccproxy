# Agent Prompt: Claude Code API Cache Breakpoint Visualizer

## Task
Create a visual representation showing where `{"cache_control": {"type": "ephemeral"}}` cache breakpoints are placed in Claude Code API request/response flows, with special emphasis on timeline-based visualization of conversation flow.

## Context
Cache breakpoints are used in Claude Code API requests to optimize context caching. These ephemeral cache control markers appear at strategic positions in the request structure to enable efficient context reuse across conversations.

## Input Data
You will receive JSON files containing captured Claude Code API request/response flows. Each file contains:
- A `request` object with headers and body
- A `response` object with status, headers, and body (streaming responses)

## Key Patterns to Identify

1. **System Message Cache Breakpoints**
   - Located in `request.body.system[]` array
   - Each system message object can have a `cache_control` field
   - Example: System identity message ("You are Claude Code...") with ephemeral cache

2. **User Message Cache Breakpoints**
   - Located in `request.body.messages[].content[]` array
   - Applied to specific content blocks within user messages
   - Common on system reminders and context injections

3. **Tool Result Cache Breakpoints**
   - Applied to tool use results in conversation history
   - Helps cache expensive tool outputs for reuse

## Visualization Requirements

### 1. Tree Structure View
- Show the JSON hierarchy with clear indentation
- Highlight nodes containing `cache_control` with a special marker (e.g., 🔄 or [CACHE])
- Use different colors/styles for different cache breakpoint locations

### 2. Timeline-Based Conversation Flow Visualization

Create a chronological view of the conversation showing:

```
Timeline: Claude Code API Conversation Flow
==========================================

[START] ──────────────────────────────────────────────────────────────> [TIME]

│ SYSTEM SETUP
├─🔄 [0ms] System: "You are Claude Code..." (CACHED)
├─🔄 [1ms] System: "Tool instructions..." (CACHED)
│
│ USER TURN #1
├─── [10ms] User: "When using neovim, how do I..."
├─🔄 [11ms] System Reminder: "Todo list empty..." (CACHED)
│
│ ASSISTANT TURN #1
├─── [100ms] Assistant: Thinking...
├─── [150ms] Tool Use: SearchCode {query: "terminal buffers"}
├─🔄 [200ms] Tool Result: "Found 15 matches..." (CACHED)
│
│ ASSISTANT TURN #1 (cont.)
├─── [250ms] Assistant: "To detect Claude Code terminals..."
│
│ USER TURN #2
├─── [500ms] User: "Can you show me an example?"
├─🔄 [501ms] Context: Previous tool results (CACHE HIT)
│
│ ASSISTANT TURN #2
├─── [550ms] Assistant: "Here's an example..."
└─── [END]

Cache Statistics:
- Total Breakpoints: 5
- Cache Hits: 1
- Estimated Token Savings: ~2,500 tokens
- Cache Efficiency: 83%
```

### 3. Cache Breakpoint Flow Diagram

Show how cache breakpoints segment the conversation:

```
┌─────────────────────────────────────────────────────────────┐
│                    CACHEABLE SEGMENTS                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🔄 SEGMENT 1: System Instructions                          │
│  ┌─────────────────────────────────────┐                   │
│  │ • Claude Code identity              │ <── Reused across │
│  │ • Tool usage instructions           │     conversations │
│  │ • Operating principles              │                   │
│  └─────────────────────────────────────┘                   │
│                      ↓                                      │
│  📝 SEGMENT 2: User Context                                 │
│  ┌─────────────────────────────────────┐                   │
│  │ • User query                        │ <── Unique per   │
│  │ • Current working directory         │     request      │
│  │ • Environment details               │                   │
│  └─────────────────────────────────────┘                   │
│                      ↓                                      │
│  🔄 SEGMENT 3: System Reminders                             │
│  ┌─────────────────────────────────────┐                   │
│  │ • Todo list status                  │ <── Cached but   │
│  │ • Context warnings                  │     may vary     │
│  └─────────────────────────────────────┘                   │
│                      ↓                                      │
│  🛠️ SEGMENT 4: Tool Results                                 │
│  ┌─────────────────────────────────────┐                   │
│  │ • File contents                     │ <── Selectively  │
│  │ • Search results                    │     cached       │
│  │ • Command outputs                   │                   │
│  └─────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### 4. Cache Hit/Miss Visualization

For conversations with multiple turns, show cache effectiveness:

```
Turn 1: [🔄🔄🔄❌❌❌❌] (3 hits, 4 misses)
Turn 2: [🔄🔄🔄🔄🔄❌❌] (5 hits, 2 misses)
Turn 3: [🔄🔄🔄🔄🔄🔄❌] (6 hits, 1 miss)

Cumulative Cache Performance:
████████████████████░░░░░ 71% Cache Hit Rate
```

### 5. Summary Statistics
- Count total cache breakpoints per request
- Show distribution by type (system vs user messages vs tool results)
- Calculate percentage of content that is cacheable
- Show token savings from cache hits
- Display cache efficiency over conversation turns

### 6. Pattern Analysis
- Identify common placement patterns
- Highlight strategic positioning (e.g., after expensive operations, before context switches)
- Show cache efficiency metrics
- Recommend optimization opportunities

## Output Format

Generate a comprehensive visualization that includes:
1. Timeline-based conversation flow with cache markers
2. Tree structure showing request/response hierarchy
3. Cache segmentation diagram
4. Performance metrics and statistics
5. Optimization recommendations

## Example Combined Visualization

```
═══════════════════════════════════════════════════════════════
           CLAUDE CODE API CACHE BREAKPOINT ANALYSIS           
═══════════════════════════════════════════════════════════════

📊 CONVERSATION METRICS
├─ Total Turns: 3
├─ Cache Breakpoints: 7
├─ Cache Hit Rate: 71%
└─ Token Savings: ~5,200

📈 TIMELINE VIEW (0-800ms)
│
├─[🔄 CACHED]──[📝 NEW]──[🔄 CACHED]──[🛠️ TOOL]──[💬 RESPONSE]
│      ↑           ↑          ↑           ↑            ↑
│   System      User Q    Reminder    Search      Assistant
│   (0ms)      (10ms)     (11ms)     (150ms)      (250ms)
│
└─[🔄 HIT]──[📝 NEW]──[🔄 HIT]──[💬 RESPONSE]
       ↑         ↑         ↑           ↑
    Cached    User Q    Cached    Assistant
    (500ms)  (501ms)   (502ms)    (550ms)

🎯 OPTIMIZATION INSIGHTS
1. System instructions fully cached (100% reuse)
2. Tool results selectively cached based on size
3. Consider caching frequent tool patterns
4. User reminders show high cache efficiency
```

## Analysis Goals

1. Understand optimal cache breakpoint placement strategies
2. Identify patterns that maximize context reuse
3. Visualize the relationship between content types and caching decisions
4. Track cache performance across conversation turns
5. Provide actionable insights for optimizing API request structure
6. Show the temporal flow of cached vs. non-cached content
7. Highlight opportunities for improved cache placement