#!/usr/bin/env python3
"""Extract JSON body from captured HTTP request/response text files."""

import json
import sys
from pathlib import Path
from typing import Optional


def extract_json_body(filepath: Path) -> Optional[str]:
    """Extract JSON body from HTTP request/response file."""
    try:
        content = filepath.read_text()
        
        # Find the start of JSON content
        # Look for common JSON starting patterns after headers
        json_starts = ['{', '[']
        
        # Split by double newline (separates headers from body)
        parts = content.split('\n\n', 1)
        if len(parts) < 2:
            # Try with \r\n\r\n for Windows line endings
            parts = content.split('\r\n\r\n', 1)
        
        if len(parts) >= 2:
            body = parts[1].strip()
            
            # Check if body starts with JSON
            if body and body[0] in json_starts:
                # Validate it's proper JSON
                try:
                    parsed = json.loads(body)
                    # Return pretty-printed JSON
                    return json.dumps(parsed, indent=2)
                except json.JSONDecodeError:
                    # Try to find JSON within the body
                    for i, char in enumerate(body):
                        if char in json_starts:
                            try:
                                parsed = json.loads(body[i:])
                                return json.dumps(parsed, indent=2)
                            except json.JSONDecodeError:
                                continue
        
        # If no body found after headers, try to find JSON anywhere in content
        for i, char in enumerate(content):
            if char in json_starts:
                # Try to parse from this position
                try:
                    # Find the end of JSON by parsing
                    parsed = json.loads(content[i:])
                    return json.dumps(parsed, indent=2)
                except json.JSONDecodeError:
                    # Try to extract just the JSON part
                    bracket_count = 0
                    in_string = False
                    escape_next = False
                    
                    for j, c in enumerate(content[i:], i):
                        if escape_next:
                            escape_next = False
                            continue
                            
                        if c == '\\' and in_string:
                            escape_next = True
                            continue
                            
                        if c == '"' and not in_string:
                            in_string = True
                        elif c == '"' and in_string:
                            in_string = False
                        elif not in_string:
                            if c in '{[':
                                bracket_count += 1
                            elif c in '}]':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    try:
                                        parsed = json.loads(content[i:j+1])
                                        return json.dumps(parsed, indent=2)
                                    except json.JSONDecodeError:
                                        break
        
        return None
        
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return None


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: extract_json.py <filepath>", file=sys.stderr)
        sys.exit(1)
    
    filepath = Path(sys.argv[1])
    
    if not filepath.exists():
        print(f"Error: File '{filepath}' not found", file=sys.stderr)
        sys.exit(1)
    
    json_body = extract_json_body(filepath)
    
    if json_body:
        print(json_body)
    else:
        print("Error: No valid JSON body found in file", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()