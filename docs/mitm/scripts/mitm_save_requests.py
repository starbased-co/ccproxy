#!/usr/bin/env python3
"""
mitmproxy addon script to save Anthropic API requests and responses to files.
"""
import json
from pathlib import Path
from mitmproxy import http

class SaveAnthropicRequests:
    def __init__(self):
        self.request_counter = 0
        self.output_dir = Path.cwd()
        # Map flow objects to their request numbers
        self.flow_map = {}
    
    def request(self, flow: http.HTTPFlow) -> None:
        # Only process Anthropic API messages endpoint
        if "api.anthropic.com/v1/messages" not in flow.request.pretty_url:
            return
        
        self.request_counter += 1
        # Store the request number for this flow
        self.flow_map[id(flow)] = self.request_counter
        
        # Save request
        request_file = self.output_dir / f"{self.request_counter}_request.txt"
        with open(request_file, "w") as f:
            # Write request line
            f.write(f"{flow.request.method} {flow.request.pretty_url} {flow.request.http_version}\n")
            
            # Write headers
            for name, value in flow.request.headers.items():
                f.write(f"{name}: {value}\n")
            
            # Write body
            f.write("\n")
            if flow.request.content:
                f.write(flow.request.content.decode('utf-8', errors='replace'))
    
    def response(self, flow: http.HTTPFlow) -> None:
        # Only process Anthropic API messages endpoint
        if "api.anthropic.com/v1/messages" not in flow.request.pretty_url:
            return
        
        # Get the request number for this flow
        request_num = self.flow_map.get(id(flow))
        if request_num is None:
            # This shouldn't happen, but handle it gracefully
            return
        
        # Save response
        response_file = self.output_dir / f"{request_num}_response.txt"
        with open(response_file, "w") as f:
            # Write status line
            f.write(f"{flow.response.http_version} {flow.response.status_code} {flow.response.reason}\n")
            
            # Write headers
            for name, value in flow.response.headers.items():
                f.write(f"{name}: {value}\n")
            
            # Write body
            f.write("\n")
            if flow.response.content:
                f.write(flow.response.content.decode('utf-8', errors='replace'))
        
        # Clean up the mapping to avoid memory leaks
        del self.flow_map[id(flow)]

addons = [SaveAnthropicRequests()]