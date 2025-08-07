#!/usr/bin/env python3
"""
mitmproxy addon script to save Anthropic API requests and responses to JSON files.
"""

import json
import os
import time
from pathlib import Path

from mitmproxy import http


class SaveAnthropicRequests:
    def __init__(self):
        self.request_counter = 0
        self.output_dir = Path().home() / "tmp" / "claude-mitm" / f"{time.ctime()}"
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        # Map flow objects to their request data
        self.flow_data = {}

    def request(self, flow: http.HTTPFlow) -> None:
        # Only process Anthropic API messages endpoint
        if "api.anthropic.com/v1/messages" not in flow.request.pretty_url:
            return

        self.request_counter += 1

        # Parse request content as JSON if possible
        request_content = None
        if flow.request.content:
            try:
                request_content = flow.request.json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If not JSON, store as string
                request_content = flow.request.content.decode("utf-8", errors="replace")

        # Store request data for this flow
        self.flow_data[id(flow)] = {
            "counter": self.request_counter,
            "request": {
                "method": flow.request.method,
                "headers": {k.lower(): v for k, v in flow.request.headers.items()},
                "content": request_content,
            },
        }

    def response(self, flow: http.HTTPFlow) -> None:
        # Only process Anthropic API messages endpoint
        if "api.anthropic.com/v1/messages" not in flow.request.pretty_url:
            return

        # Get the stored request data for this flow
        flow_info = self.flow_data.get(id(flow))
        if flow_info is None:
            # This shouldn't happen, but handle it gracefully
            return

        # Parse response content as JSON if possible
        response_content = None
        if flow.response.content:
            try:
                response_content = flow.response.json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If not JSON, store as string
                response_content = flow.response.content.decode("utf-8", errors="replace")

        # Add response data
        flow_info["response"] = {
            "status": flow.response.status_code,
            "headers": {k.lower(): v for k, v in flow.response.headers.items()},
            "content": response_content,
        }

        # Save combined data to JSON file
        output_file = self.output_dir / f"flow_{flow_info['counter']}.json"
        with Path.open(output_file, "w") as f:
            # Remove the counter from the output, keep only request/response
            output_data = {"request": flow_info["request"], "response": flow_info["response"]}
            json.dump(output_data, f, indent=2)

        # Clean up the mapping to avoid memory leaks
        del self.flow_data[id(flow)]


addons = [SaveAnthropicRequests()]
