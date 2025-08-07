#!/usr/bin/env python3
"""Debug script to check Flow 2 timeline generation"""

import json

# Load flow 2
with open('captured/flow_2.json', 'r') as f:
    flow2 = json.load(f)

data = flow2['request']['body']

print("=== FLOW 2 TIMELINE DEBUG ===\n")

# System messages
print("SYSTEM MESSAGES:")
for i, sys_msg in enumerate(data['system']):
    has_cache = 'cache_control' in sys_msg
    print(f"  [{i}] cache_control: {has_cache}, text preview: {sys_msg.get('text', '')[:50]}...")

# Messages
print("\nMESSAGES:")
for msg_idx, msg in enumerate(data['messages']):
    role = msg['role']
    print(f"\nMessage {msg_idx} (role: {role}):")
    
    if 'content' in msg and isinstance(msg['content'], list):
        for cont_idx, content in enumerate(msg['content']):
            print(f"  Content [{cont_idx}]:")
            
            # Check what type of content this is
            if 'text' in content:
                has_cache = 'cache_control' in content
                text_preview = content['text'][:50].replace('\n', ' ')
                print(f"    Type: text")
                print(f"    cache_control: {has_cache}")
                print(f"    preview: {text_preview}...")
                
            elif 'tool_use' in content:
                has_cache = 'cache_control' in content
                tool_name = content.get('name', 'Unknown')
                print(f"    Type: tool_use")
                print(f"    cache_control: {has_cache}")
                print(f"    tool: {tool_name}")
                
            elif 'tool_result' in content:
                has_cache = 'cache_control' in content
                result_preview = content.get('content', '')[:50].replace('\n', ' ')
                print(f"    Type: tool_result")
                print(f"    cache_control: {has_cache}")
                print(f"    preview: {result_preview}...")
            
            else:
                print(f"    UNKNOWN TYPE: {list(content.keys())}")