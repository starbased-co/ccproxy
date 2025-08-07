#!/usr/bin/env python3
"""
Unified Anthropic Cache Analyzer with Reverse Proxy
Combines reverse proxy functionality with cache analysis for Claude Code
"""

import hashlib
import json
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field

from flask import Flask, jsonify, redirect, render_template_string, url_for
from flask_cors import CORS
from mitmproxy import ctx, http


@dataclass
class CacheControl:
    """Represents a cache control block"""

    type: str  # 'ephemeral'
    ttl: str | None = None  # '5m' or '1h'
    location: str = ""  # 'tools', 'system', 'messages'
    block_index: int = 0
    content_preview: str = ""


@dataclass
class UsageMetrics:
    """Token usage metrics from response"""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    total_tokens: int = 0
    cache_efficiency: float = 0.0  # Percentage of tokens from cache

    def calculate_efficiency(self):
        total_input = self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens
        if total_input > 0:
            self.cache_efficiency = (self.cache_read_input_tokens / total_input) * 100


@dataclass
class ConversationTurn:
    """Represents a single API call in a conversation"""

    request_id: str
    timestamp: float
    model: str
    method: str  # 'messages' or 'completions'

    # Cache control locations
    cache_controls: dict[str, list[CacheControl]] = field(default_factory=dict)

    # Token usage
    usage: UsageMetrics = field(default_factory=UsageMetrics)

    # Timing
    time_since_last: float | None = None
    potential_1h_benefit: bool = False

    # Request details
    has_tools: bool = False
    has_thinking: bool = False
    has_images: bool = False
    message_count: int = 0
    system_prompt_hash: str | None = None

    # Response details
    response_time: float = 0.0
    was_successful: bool = True
    error_message: str | None = None


@dataclass
class Conversation:
    """Tracks a full conversation session"""

    conversation_id: str
    start_time: float
    turns: list[ConversationTurn] = field(default_factory=list)

    # Aggregate metrics
    total_cache_hits: int = 0
    total_cache_misses: int = 0
    total_tokens_saved: int = 0
    gaps_over_5min: int = 0
    gaps_5min_to_1hr: int = 0

    def add_turn(self, turn: ConversationTurn):
        """Add a turn and update metrics"""
        if self.turns:
            last_turn = self.turns[-1]
            turn.time_since_last = turn.timestamp - last_turn.timestamp

            # Check for cache gap opportunities
            if turn.time_since_last > 300:  # 5 minutes
                self.gaps_over_5min += 1
                if turn.time_since_last > 300 and turn.time_since_last <= 3600:  # 5min-1hr
                    self.gaps_5min_to_1hr += 1
                    turn.potential_1h_benefit = True

        # Update cache metrics
        if turn.usage.cache_read_input_tokens > 0:
            self.total_cache_hits += 1
            self.total_tokens_saved += turn.usage.cache_read_input_tokens
        elif turn.usage.cache_creation_input_tokens > 0:
            self.total_cache_misses += 1

        self.turns.append(turn)


class CacheAnalyzer:
    """Core cache analysis engine"""

    def __init__(self):
        self.conversations: dict[str, Conversation] = {}
        self.current_requests: dict[str, dict] = {}
        self.request_counts = defaultdict(int)

    def analyze_request(self, flow: http.HTTPFlow) -> str | None:
        """Analyze an outgoing Anthropic API request"""
        try:
            request_data = json.loads(flow.request.content)
            request_id = request_data.get("id", f"{int(time.time() * 1000)}")

            # Check if this is a streaming request
            is_streaming = request_data.get("stream", False)

            # Create conversation turn
            turn = ConversationTurn(
                request_id=request_id,
                timestamp=time.time(),
                model=request_data.get("model", "unknown"),
                method="messages",  # Assume messages for now
                cache_controls={"tools": [], "system": [], "messages": []},
            )

            # Extract cache controls
            cache_controls = self._extract_cache_controls(request_data)
            for control in cache_controls:
                if control.location.startswith("tools"):
                    turn.cache_controls["tools"].append(control)
                elif control.location.startswith("system"):
                    turn.cache_controls["system"].append(control)
                elif control.location.startswith("messages"):
                    turn.cache_controls["messages"].append(control)

            # Analyze request features
            turn.has_tools = "tools" in request_data and len(request_data["tools"]) > 0
            turn.has_images = self._check_for_images(request_data)
            turn.has_thinking = self._check_for_thinking(request_data)
            turn.message_count = len(request_data.get("messages", []))

            # Hash system prompt for change detection
            if "system" in request_data:
                system_str = json.dumps(request_data["system"], sort_keys=True)
                turn.system_prompt_hash = hashlib.md5(system_str.encode()).hexdigest()

            # Store request for correlation with response
            self.current_requests[request_id] = {
                "turn": turn, 
                "flow_id": flow.id, 
                "start_time": time.time(),
                "is_streaming": is_streaming
            }

            return request_id

        except Exception as e:
            ctx.log.error(f"Error analyzing request: {e}")
            return None

    def analyze_response(self, flow: http.HTTPFlow, request_id: str):
        """Analyze response and complete the turn analysis"""
        if request_id not in self.current_requests:
            return

        try:
            request_info = self.current_requests[request_id]
            
            # Check if response exists
            if not flow.response:
                ctx.log.warn(f"No response object for request {request_id}")
                del self.current_requests[request_id]
                return

            # Check response status
            if flow.response.status_code >= 400:
                ctx.log.warn(f"Error response {flow.response.status_code} for request {request_id}")
                ctx.log.debug(f"Error content: {flow.response.text[:500] if flow.response.text else 'None'}")
                del self.current_requests[request_id]
                return

            # Get response content - try multiple methods
            content = None
            
            # First try the text property (handles decompression)
            try:
                content = flow.response.text
            except Exception as e:
                ctx.log.debug(f"Failed to get response.text: {e}")
                
            # If text failed or is empty, try get_text()
            if not content:
                try:
                    content = flow.response.get_text()
                except Exception as e:
                    ctx.log.debug(f"Failed to get_text(): {e}")
            
            # If still no content, try raw content with decoding
            if not content:
                try:
                    raw_content = flow.response.content
                    if raw_content:
                        content = raw_content.decode('utf-8', errors='ignore')
                        ctx.log.debug(f"Using raw content decoding for {request_id}")
                except Exception as e:
                    ctx.log.debug(f"Failed to decode raw content: {e}")
            
            # Log content details for debugging
            if not content:
                ctx.log.warn(f"Empty response content for request {request_id}")
                ctx.log.debug(f"Response headers: {dict(flow.response.headers)}")
                ctx.log.debug(f"Response content length: {len(flow.response.content) if flow.response.content else 0}")
                del self.current_requests[request_id]
                return
            
            # Log content type and first characters for debugging
            ctx.log.debug(f"Response for {request_id}: content_type={flow.response.headers.get('content-type', 'unknown')}, len={len(content)}, preview={repr(content[:100])}")

            # Handle streaming responses (Server-Sent Events format)
            # Check if this looks like SSE format (can start with "event:" or "data:")
            is_streaming = request_info.get("is_streaming", False)
            if is_streaming or content.startswith(("data:", "event:")):
                ctx.log.info(f"Processing SSE/streaming response for {request_id}")
                # Extract JSON from SSE stream
                lines = content.strip().split('\n')
                response_data = None
                
                # Debug: show what we're dealing with
                ctx.log.debug(f"SSE response has {len(lines)} lines")
                if lines:
                    ctx.log.debug(f"First line: {repr(lines[0][:100])}")
                    ctx.log.debug(f"Last line: {repr(lines[-1][:100])}")
                
                # Look for JSON data in various SSE formats
                for line in reversed(lines):
                    # Handle "data: {...}" format
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])  # Skip "data: " prefix
                            # Look for usage in the streaming events
                            if "usage" in data:
                                response_data = data
                                break
                            elif data.get("type") == "message_stop":
                                # message_stop event might contain usage
                                response_data = data
                                break
                        except json.JSONDecodeError:
                            continue
                    
                    # Handle lines that might just be JSON without "data:" prefix
                    elif line.strip().startswith('{'):
                        try:
                            data = json.loads(line.strip())
                            if "usage" in data or data.get("type") == "message_stop":
                                response_data = data
                                break
                        except json.JSONDecodeError:
                            continue
                
                if not response_data:
                    ctx.log.info(f"No usage metrics in streaming response for {request_id} - this is normal for streaming")
                    del self.current_requests[request_id]
                    return
            else:
                # Try to parse as regular JSON
                try:
                    # First check if content looks like JSON
                    content_stripped = content.strip()
                    if not content_stripped:
                        ctx.log.error(f"Response content is empty after stripping for {request_id}")
                        del self.current_requests[request_id]
                        return
                    
                    # Check if it starts with expected JSON characters
                    if not content_stripped[0] in '{[':
                        # Maybe it's SSE that we didn't catch earlier
                        if content_stripped.startswith(("event:", "data:", "id:")):
                            ctx.log.info(f"Detected SSE format for non-streaming request {request_id}, processing as SSE")
                            # Process as SSE
                            lines = content_stripped.split('\n')
                            response_data = None
                            for line in lines:
                                if line.startswith("data: ") and line != "data: [DONE]":
                                    try:
                                        response_data = json.loads(line[6:])
                                        if "usage" in response_data:
                                            break
                                    except json.JSONDecodeError:
                                        continue
                            
                            if not response_data:
                                ctx.log.warn(f"Could not extract data from SSE response for {request_id}")
                                del self.current_requests[request_id]
                                return
                        else:
                            ctx.log.error(f"Response doesn't look like JSON for {request_id}. First char: {repr(content_stripped[0])}")
                            ctx.log.debug(f"Full content preview: {repr(content_stripped[:200])}")
                            del self.current_requests[request_id]
                            return
                    
                    response_data = json.loads(content_stripped)
                except json.JSONDecodeError as e:
                    ctx.log.error(f"Failed to parse JSON response for {request_id}: {e}")
                    ctx.log.debug(f"Response content preview: {repr(content[:200])}")
                    ctx.log.debug(f"Content-Type: {flow.response.headers.get('content-type', 'unknown')}")
                    ctx.log.debug(f"Content-Encoding: {flow.response.headers.get('content-encoding', 'none')}")
                    del self.current_requests[request_id]
                    return

            turn = request_info["turn"]

            # Update response timing
            turn.response_time = time.time() - request_info["start_time"]

            # Extract usage metrics
            if "usage" in response_data:
                usage = response_data["usage"]
                turn.usage = UsageMetrics(
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
                    cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                )
                turn.usage.calculate_efficiency()

            # Determine conversation ID
            conversation_id = self._get_conversation_id(flow)

            # Add to conversation
            if conversation_id not in self.conversations:
                self.conversations[conversation_id] = Conversation(
                    conversation_id=conversation_id, start_time=turn.timestamp
                )

            self.conversations[conversation_id].add_turn(turn)

            # Clean up
            del self.current_requests[request_id]

        except Exception as e:
            ctx.log.error(f"Error analyzing response: {e}")

    def _extract_cache_controls(self, data: dict) -> list[CacheControl]:
        """Extract cache control blocks from request"""
        controls = []

        def extract_from_content(content, location_prefix=""):
            if isinstance(content, list):
                for i, block in enumerate(content):
                    if isinstance(block, dict):
                        cache_control = block.get("cache_control")
                        if cache_control:
                            controls.append(
                                CacheControl(
                                    type=cache_control.get("type", "ephemeral"),
                                    ttl=cache_control.get("ttl"),
                                    location=f"{location_prefix}[{i}]",
                                    block_index=i,
                                    content_preview=str(block.get("text", block.get("content", "")))[:100],
                                )
                            )
                        # Recursively check nested content
                        if "content" in block:
                            extract_from_content(block["content"], f"{location_prefix}[{i}].content")
            elif isinstance(content, dict):
                cache_control = content.get("cache_control")
                if cache_control:
                    controls.append(
                        CacheControl(
                            type=cache_control.get("type", "ephemeral"),
                            ttl=cache_control.get("ttl"),
                            location=location_prefix,
                            block_index=0,
                            content_preview=str(content.get("text", content.get("content", "")))[:100],
                        )
                    )

        # Check tools
        if "tools" in data:
            extract_from_content(data["tools"], "tools")

        # Check system
        if "system" in data:
            extract_from_content(data["system"], "system")

        # Check messages
        if "messages" in data:
            for i, message in enumerate(data["messages"]):
                if "content" in message:
                    extract_from_content(message["content"], f"messages[{i}]")

        return controls

    def _check_for_images(self, data: dict) -> bool:
        """Check if request contains images"""
        if "messages" in data:
            for message in data["messages"]:
                if isinstance(message.get("content"), list):
                    for block in message["content"]:
                        if isinstance(block, dict) and block.get("type") == "image":
                            return True
        return False

    def _check_for_thinking(self, data: dict) -> bool:
        """Check if request has thinking enabled or contains thinking blocks"""
        if data.get("thinking", {}).get("enabled"):
            return True

        if "messages" in data:
            for message in data["messages"]:
                if isinstance(message.get("content"), list):
                    for block in message["content"]:
                        if isinstance(block, dict) and block.get("type") == "thinking":
                            return True
        return False

    def _get_conversation_id(self, flow: http.HTTPFlow) -> str:
        """Determine conversation ID from request"""
        # Use API key hash or session ID if available
        auth_header = flow.request.headers.get("x-api-key", "")
        if auth_header:
            return hashlib.md5(auth_header[-10:].encode()).hexdigest()[:8]

        return "default"

    def get_optimization_report(self) -> dict:
        """Generate optimization recommendations"""
        report = {
            "summary": {
                "total_conversations": len(self.conversations),
                "total_requests": sum(len(conv.turns) for conv in self.conversations.values()),
                "cache_hit_rate": 0.0,
                "potential_savings": 0,
            },
            "recommendations": [],
        }

        if not self.conversations:
            return report

        total_hits = sum(conv.total_cache_hits for conv in self.conversations.values())
        total_requests = sum(len(conv.turns) for conv in self.conversations.values())

        if total_requests > 0:
            report["summary"]["cache_hit_rate"] = (total_hits / total_requests) * 100

        # Find 1-hour cache opportunities
        one_hour_opportunities = []
        for conv in self.conversations.values():
            for turn in conv.turns:
                if turn.potential_1h_benefit and turn.usage.cache_creation_input_tokens > 0:
                    one_hour_opportunities.append(
                        {
                            "conversation_id": conv.conversation_id,
                            "timestamp": turn.timestamp,
                            "potential_tokens_saved": turn.usage.cache_creation_input_tokens,
                            "time_gap": turn.time_since_last,
                        }
                    )

        if one_hour_opportunities:
            total_potential = sum(op["potential_tokens_saved"] for op in one_hour_opportunities)
            report["recommendations"].append(
                {
                    "type": "1_hour_cache",
                    "title": f"{len(one_hour_opportunities)} opportunities for 1-hour cache TTL",
                    "description": f"Could save ~{total_potential} tokens with longer cache TTL",
                    "opportunities": one_hour_opportunities[:10],  # Top 10
                }
            )

        return report


class UnifiedCacheAnalyzer:
    """Unified mitmproxy addon with reverse proxy and cache analysis"""

    def __init__(self):
        self.analyzer = CacheAnalyzer()
        self.target_host = "api.anthropic.com"
        self.target_scheme = "https"
        self.visualization_server = None
        self.start_visualization_server()
        ctx.log.info("Unified Cache Analyzer with Reverse Proxy initialized")

    def start_visualization_server(self):
        """Start Flask server for visualization dashboard"""
        app = Flask(__name__)
        CORS(app)

        @app.route("/")
        def dashboard():
            return render_template_string(DASHBOARD_HTML)

        @app.route("/api/conversations")
        def get_conversations():
            data = []
            for conv_id, conv in self.analyzer.conversations.items():
                conv_data = {
                    "id": conv_id,
                    "start_time": conv.start_time,
                    "turns": [asdict(turn) for turn in conv.turns],
                    "metrics": {
                        "total_cache_hits": conv.total_cache_hits,
                        "total_cache_misses": conv.total_cache_misses,
                        "total_tokens_saved": conv.total_tokens_saved,
                        "gaps_5min_to_1hr": conv.gaps_5min_to_1hr,
                    },
                }
                data.append(conv_data)
            return jsonify(data)

        @app.route("/api/optimization")
        def get_optimization():
            return jsonify(self.analyzer.get_optimization_report())

        @app.route("/clear", methods=["POST"])
        def clear():
            self.analyzer.conversations.clear()
            self.analyzer.current_requests.clear()
            return redirect(url_for("dashboard"))

        # Run Flask in a separate thread
        def run_server():
            app.run(host="0.0.0.0", port=5555, debug=False)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        ctx.log.info("Cache visualization dashboard running at http://localhost:5555")

    def request(self, flow: http.HTTPFlow):
        """Handle incoming requests - both proxy and analyze"""

        # Handle Anthropic API paths - rewrite to forward to api.anthropic.com
        if flow.request.path.startswith("/v1/"):
            # This is an Anthropic API request - forward it and analyze it
            flow.request.host = self.target_host
            flow.request.scheme = self.target_scheme
            flow.request.port = 443

            ctx.log.info(f"Forwarding to {self.target_scheme}://{self.target_host}{flow.request.path}")

            # Also analyze the request for cache patterns
            if "/v1/messages" in flow.request.path:
                request_id = self.analyzer.analyze_request(flow)
                if request_id:
                    flow.metadata["cache_request_id"] = request_id

        # Handle health check endpoint
        elif flow.request.path == "/health":
            flow.response = http.Response.make(
                200,
                b'{"status": "ok", "proxy": "unified-cache-analyzer", "dashboard": "http://localhost:5555"}',
                {"Content-Type": "application/json"},
            )
            ctx.log.info("Health check requested")

        # Handle root path
        elif flow.request.path == "/":
            flow.response = http.Response.make(
                200,
                b'{"message": "Anthropic Cache Analyzer with Reverse Proxy", "status": "running", "dashboard": "http://localhost:5555"}',
                {"Content-Type": "application/json"},
            )

    def response(self, flow: http.HTTPFlow):
        """Handle responses from Anthropic API"""
        if flow.request.host == self.target_host:
            ctx.log.info(f"Response from Anthropic: {flow.response.status_code}")

            # Run cache analysis on the response if we tracked the request
            if "cache_request_id" in flow.metadata:
                self.analyzer.analyze_response(flow, flow.metadata["cache_request_id"])


# HTML Dashboard Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Anthropic Cache Analyzer</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        .controls {
            margin: 20px 0;
        }
        .clear-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .metric-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }
        .chart-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px 0;
        }
        .recommendations {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px 0;
        }
        .recommendation-item {
            border-left: 4px solid #28a745;
            padding-left: 15px;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Anthropic Cache Analyzer</h1>
        
        <div class="controls">
            <form action="/clear" method="post" style="display: inline;">
                <button type="submit" class="clear-btn">Clear All Data</button>
            </form>
            <small style="color: #666; margin-left: 15px;">
                Data is automatically cleared on proxy restart
            </small>
        </div>
        
        <div class="metrics-grid" id="metrics">
            <!-- Metrics will be loaded here -->
        </div>
        
        <div class="chart-container">
            <h3>Cache Efficiency Over Time</h3>
            <canvas id="efficiencyChart" width="800" height="400"></canvas>
        </div>
        
        <div class="recommendations" id="recommendations">
            <h3>💡 Optimization Recommendations</h3>
            <div id="recommendationList">
                <!-- Recommendations will be loaded here -->
            </div>
        </div>
    </div>

    <script>
        let efficiencyChart;
        
        async function loadData() {
            try {
                const [conversationsRes, optimizationRes] = await Promise.all([
                    axios.get('/api/conversations'),
                    axios.get('/api/optimization')
                ]);
                
                const conversations = conversationsRes.data;
                const optimization = optimizationRes.data;
                
                updateMetrics(conversations, optimization);
                updateChart(conversations);
                updateRecommendations(optimization);
            } catch (error) {
                console.error('Error loading data:', error);
            }
        }
        
        function updateMetrics(conversations, optimization) {
            const totalTurns = conversations.reduce((sum, conv) => sum + conv.turns.length, 0);
            const totalCacheHits = conversations.reduce((sum, conv) => sum + conv.metrics.total_cache_hits, 0);
            const totalTokensSaved = conversations.reduce((sum, conv) => sum + conv.metrics.total_tokens_saved, 0);
            
            document.getElementById('metrics').innerHTML = `
                <div class="metric-card">
                    <div class="metric-value">${conversations.length}</div>
                    <div>Active Conversations</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${totalTurns}</div>
                    <div>Total Requests</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${optimization.summary.cache_hit_rate.toFixed(1)}%</div>
                    <div>Cache Hit Rate</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${totalTokensSaved.toLocaleString()}</div>
                    <div>Tokens Saved</div>
                </div>
            `;
        }
        
        function updateChart(conversations) {
            const ctx = document.getElementById('efficiencyChart').getContext('2d');
            
            if (efficiencyChart) {
                efficiencyChart.destroy();
            }
            
            const allTurns = conversations.flatMap(conv => 
                conv.turns.map(turn => ({
                    timestamp: new Date(turn.timestamp * 1000),
                    efficiency: turn.usage.cache_efficiency || 0,
                    conversation: conv.id
                }))
            ).sort((a, b) => a.timestamp - b.timestamp);
            
            efficiencyChart = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: [{
                        label: 'Cache Efficiency %',
                        data: allTurns.map(turn => ({
                            x: turn.timestamp,
                            y: turn.efficiency
                        })),
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                displayFormats: {
                                    minute: 'HH:mm'
                                }
                            }
                        },
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });
        }
        
        function updateRecommendations(optimization) {
            const recommendationList = document.getElementById('recommendationList');
            
            if (optimization.recommendations.length === 0) {
                recommendationList.innerHTML = '<p style="color: #666;">No specific recommendations yet. Continue using Claude to gather more data.</p>';
                return;
            }
            
            recommendationList.innerHTML = optimization.recommendations.map(rec => `
                <div class="recommendation-item">
                    <strong>${rec.title}</strong><br>
                    <small>${rec.description}</small>
                </div>
            `).join('');
        }
        
        // Load data initially and refresh every 10 seconds
        loadData();
        setInterval(loadData, 10000);
    </script>
</body>
</html>
"""

# Create addon instance
addons = [UnifiedCacheAnalyzer()]

