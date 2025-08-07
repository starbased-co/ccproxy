# Anthropic Cache Analyzer for Claude Code

Analyzes Claude Code's API caching patterns to identify optimization opportunities. Works by intercepting Anthropic API requests and analyzing cache behavior.

## Quick Start

### 1. Start the Analyzer

```bash
./start.sh
```

This starts:

- Reverse proxy on port 4000
- Cache analysis dashboard on port 5555

### 2. Run Claude Code

In another terminal:

```bash
./run_claude.sh
```

Or manually:

```bash
export ANTHROPIC_BASE_URL="http://localhost:4000"
claude
```

### 3. View Cache Analysis

Open <http://localhost:5555> to see:

- Real-time cache hit/miss patterns
- Token usage breakdown
- 1-hour cache opportunities
- Optimization recommendations

## How It Works

```
Claude Code → ANTHROPIC_BASE_URL → Cache Analyzer → api.anthropic.com
                                       ├── Analysis Engine
                                       └── Dashboard (5555)
```

## Key Features

- **Reverse Proxy**: Transparent forwarding to Anthropic API
- **Cache Analysis**: Tracks cache_control blocks in tools, system, messages
- **Optimization Detection**: Identifies 1-hour cache opportunities
- **Real-time Dashboard**: Live visualization of cache patterns
- **MCP Compatibility**: Doesn't interfere with MCP servers

## Files

- `cache_analyzer.py` - Unified addon with reverse proxy + cache analysis
- `start.sh` - Start the analyzer (port 4000)
- `run_claude.sh` - Run Claude Code with analyzer
- `setup-certificates.sh` - Install mitmproxy certificates (Arch Linux)
- `README.md` - This file

## Requirements

- Python 3.8+
- mitmproxy (`pip install mitmproxy`)
- flask (`pip install flask flask-cors`)

## Troubleshooting

### Health Check

```bash
curl http://localhost:4000/health
```

Should return: `{"status": "ok", "proxy": "unified-cache-analyzer"}`

### Certificate Issues (Arch Linux)

```bash
./setup-certificates.sh
```

### Port Already in Use

```bash
# Use different port
PROXY_PORT=4001 ./start.sh

# Update Claude to use new port
PROXY_PORT=4001 ./run_claude.sh
```

## Cache Analysis Insights

The analyzer identifies:

1. **Stable Content** - Tools and system prompts that could use 1-hour caching
2. **Cache Thrashing** - Frequent recreation of identical cache blocks
3. **Optimal Breakpoints** - Where to place cache_control for maximum reuse
4. **Token Savings** - Potential cost reduction from better caching

## Development

To modify cache analysis logic, edit the `CacheAnalyzer` class in `cache_analyzer.py`.

The dashboard auto-refreshes every 10 seconds and shows metrics for active conversations.

