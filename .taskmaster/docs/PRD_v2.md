# CCProxy Context Preservation: Claude Code Integration

## Executive Summary

Implement comprehensive context preservation for ccproxy by leveraging Claude Code's existing JSONL conversation storage, enabling seamless conversation continuity across provider routing decisions while avoiding duplicate storage systems.

## Project Overview

```
CURRENT STATE               TARGET STATE
 ┌─────────────────┐        ┌─────────────────┐
 │ Claude Code     │        │ Claude Code     │
 │ ~/.claude/      │   =>   │ ~/.claude/      │
 │ projects/       │        │ projects/       │◄──┐
 │ {session}.jsonl │        │ {session}.jsonl │   │
 └─────────────────┘        └─────────────────┘   │
                                                  │
 ┌─────────────────┐        ┌─────────────────┐   │
 │ ccproxy         │        │ ccproxy         │   │
 │                 │   =>   │ ~/.ccproxy/     │   │
 │ NO CONTEXT      │        │ metadata/       │   │
 │ PRESERVATION    │        │ {routing}.json  │───┘
 └─────────────────┘        └─────────────────┘

NO CONTEXT CONTINUITY       UNIFIED CONTEXT SYSTEM
```

## Architecture Design

### Core Components

#### 1. ClaudeProjectLocator

**Location**: `src/ccproxy/claude_integration.py`
**Purpose**: Discover Claude Code project paths from working directory

```python
class ClaudeProjectLocator:
    def find_project_path(self, cwd: Path) -> Path | None
    def get_session_files(self, project_path: Path) -> list[Path]
    def cache_project_info(self, project_path: Path) -> ProjectInfo
```

#### 2. ClaudeCodeReader

**Location**: `src/ccproxy/claude_integration.py`
**Purpose**: Parse JSONL files and reconstruct conversation history

```python
class ClaudeCodeReader:
    def read_conversation(self, session_file: Path) -> ConversationHistory
    def extract_messages(self, jsonl_entries: list[dict]) -> list[Message]
    def get_session_id(self, jsonl_entries: list[dict]) -> str
```

#### 3. ProviderMetadataStore

**Location**: `src/ccproxy/provider_metadata.py`
**Purpose**: Lightweight storage for provider routing information only

```python
# Storage format: {session_id: {provider_history: [...], routing_decisions: [...]}}
class ProviderMetadataStore:
    def record_routing_decision(self, session_id: str, provider: str, model: str)
    def get_provider_history(self, session_id: str) -> list[ProviderDecision]
```

#### 4. ContextManager

**Location**: New `src/ccproxy/context_manager.py`
**Purpose**: Orchestrate Claude Code reader + provider metadata for context preservation

## Implementation Phases

### Phase 1: JSONL Reader Foundation

**Duration**: Critical path development

```
1.1 Project Discovery Service
    |-- Implement ClaudeProjectLocator
    |-- Handle nested project structures
    |-- Add caching for repeated lookups

1.2 JSONL Parser Implementation
    |-- Create ClaudeCodeReader with streaming parsing
    |-- Implement conversation reconstruction
    |-- Add error handling for malformed files
    |-- Support user/assistant messages and tool calls

1.3 Session ID Mapping
    |-- Extract sessionId from Claude Code metadata
```

**Deliverables**: Functional JSONL reader with comprehensive test suite

### Phase 2: Context Manager Implementation

```
2.1 Context Manager Design
    |-- Create new ContextManager to orchestrate ClaudeCodeReader
    |-- Integrate lightweight ProviderMetadataStore
    |-- Implement context injection from Claude Code JSONL
    |-- Add configuration options for necessary properties

2.2 Hook System Integration
    |-- Create context_injection_hook to add missing conversation history
    |-- Create context_recording_hook to track provider routing decisions
    |-- Integrate hooks into CCProxyHandler pipeline
    |-- Add error handling and performance monitoring

2.3 Fallback Mechanisms
    |-- Add circuit breaker pattern for JSONL parsing failures
```

**Deliverables**: Complete ContextManager with hook integration and fallback capabilities

### Phase 3: Integration & Testing

```
3.1 Handler Integration
    |-- Integrate context hooks into CCProxyHandler request pipeline
    |-- Add context preservation to async_pre_call_hook
    |-- Add provider tracking to async_log_success_event
    |-- Ensure backward compatibility with existing routing logic

3.2 Comprehensive Testing Suite
    |-- Create cross-provider context preservation integration tests
    |-- Build JSONL parsing and session ID mapping unit tests
    |-- Test fallback mechanisms and error scenarios
    |-- Validate context preservation with real conversation flows
```

### Phase 4: Production Readiness

```
4.1 Performance Optimization
    |-- Implement JSONL parsing caching strategies
    |-- Optimize project path discovery with memoization
    |-- Profile and tune critical path performance

4.2 Documentation & Deployment
    |-- Document configuration options and troubleshooting
```

## Risk Management

### High-Risk Scenarios & Mitigation

| Risk                             | Impact | Mitigation Strategy                                           |
| -------------------------------- | ------ | ------------------------------------------------------------- |
| Claude Code JSONL format changes | High   | Monitor Claude Code updates, implement version detection      |
| Performance degradation          | Medium | Establish <100ms parsing benchmarks, implement caching layers |

### Success Criteria

- **Context Continuity**: 100% preservation across provider switches
- **Performance**: <10% latency increase vs current system

## Configuration Schema

```yaml
ccproxy:
  context:
    # configuration here
```

## Definition of Done

**Technical Requirements:**

- Zero conversation context loss during provider switches
- Elimination of duplicate storage (`.ccproxy/context/` vs `~/.claude/projects/`)
- <10% performance impact vs current implementation
- Comprehensive test coverage including edge cases
- Production-ready deployment with monitoring and rollback capability

**Documentation Requirements:**

- Architecture documentation updated with new hybrid approach
- Migration procedures for existing ccproxy installations
- Troubleshooting guides for common integration issues
- Configuration reference for all new options

## Next Actions

**Week 1 Sprint:**

1. Analyze Claude Code JSONL format with real files from `~/.claude/projects/`
2. Create proof-of-concept ClaudeProjectLocator with basic path discovery
3. Build minimal JSONL parser to validate conversation reconstruction
4. Design HybridContextManager interface and migration strategy
5. Create comprehensive test plan and validation criteria

**Resource Requirements:**

- Development environment with access to Claude Code projects
- Testing infrastructure for ccproxy integration validation
- Monitoring and alerting setup for production deployment

---

# Product Requirements Document (PRD)

## Problem Statement

ccproxy currently lacks conversation context preservation when routing requests between different AI providers, creating:

- **Context Loss**: When a conversation switches from one provider (e.g., Anthropic) to another (e.g., Google), the new provider has no access to previous conversation history
- **Broken User Experience**: Users lose conversation continuity and must re-establish context manually
- **Provider Routing Limitations**: Advanced routing rules that switch providers mid-conversation are impractical due to context loss
- **Inefficient API Usage**: Users repeat context unnecessarily, increasing token costs and latency

## Solution Overview

Implement context preservation for ccproxy by leveraging Claude Code's existing JSONL conversation storage to create a unified context system that:

- Preserves conversation continuity across provider switches
- Leverages Claude Code's proven conversation management without duplication
- Maintains ccproxy's flexible provider routing capabilities
- Enables seamless cross-provider context continuity for users

## User Stories

### AS A ccproxy user

**I WANT** seamless conversation continuity when requests are routed to different providers
**SO THAT** I don't lose context when switching between Anthropic, Google, OpenAI, etc.

**Acceptance Criteria:**

- When I continue a conversation that was previously routed to a different provider, I receive complete context history
- Provider switches are transparent to my user experience
- No conversation exchanges are lost regardless of provider routing decisions

### AS A ccproxy administrator

**I WANT** context preservation without additional storage overhead
**SO THAT** I can enable advanced routing features while maintaining system simplicity

**Acceptance Criteria:**

- Context preservation leverages existing Claude Code storage without duplication
- System monitoring shows no significant performance degradation
- Configuration is simple with clear options

### AS A ccproxy developer

**Acceptance Criteria:**

- Error conditions are logged and monitored appropriately

## Functional Requirements

### FR1: JSONL Integration

- **FR1.1**: Read conversation history from Claude Code's JSONL files
- **FR1.2**: Parse JSONL entries to reconstruct complete conversation context
- **FR1.3**: Support both user/assistant messages and tool calls
- **FR1.4**: Handle malformed or incomplete JSONL files gracefully

### FR2: Session Management

- **FR2.1**: Extract session IDs from Claude Code's sessionId field
- **FR2.2**: Support session validation and integrity checks

### FR3: Provider Metadata

- **FR3.1**: Store provider routing decisions separately from conversation data
- **FR3.2**: Track provider history for debugging and analytics
- **FR3.3**: Maintain lightweight metadata storage for performance
- **FR3.4**: Support provider-specific configuration and routing rules

### FR4: System Integration

- **FR4.1**: Integrate seamlessly with existing ccproxy routing and configuration
- **FR4.2**: Provide clear error handling when context preservation fails

## Non-Functional Requirements

### NFR1: Performance

- **NFR1.1**: Context injection latency increase <10% vs baseline (no context)
- **NFR1.2**: JSONL parsing performance <100ms for typical conversations
- **NFR1.3**: Conversation history caching for repeated access
- **NFR1.4**: Memory usage optimization for large conversation histories

### NFR2: Reliability

- **NFR2.1**: 99.9% context preservation accuracy across provider switches
- **NFR2.2**: Graceful degradation when Claude Code storage unavailable
- **NFR2.3**: Comprehensive error handling and recovery mechanisms

### NFR3: Maintainability

- **NFR3.1**: Clear separation between conversation storage and provider metadata
- **NFR3.2**: Comprehensive test coverage for all integration scenarios
- **NFR3.3**: Detailed logging and monitoring for operational visibility
- **NFR3.4**: Documentation for architecture, configuration, and troubleshooting

### NFR4: Security

- **NFR4.1**: Proper handling of Claude Code project file access
- **NFR4.2**: Proper error messages without information leakage
- **NFR3.3**: Audit trail for context preservation operations

## Technical Constraints

### TC1: External Dependencies

- **TC1.1**: Must maintain compatibility with Claude Code's JSONL format
- **TC1.2**: Cannot modify Claude Code's file structure or naming conventions
- **TC1.3**: Must handle Claude Code version updates gracefully
- **TC1.4**: Limited to read-only access of Claude Code storage

### TC2: System Integration

- **TC2.1**: Must integrate with existing ccproxy hook system
- **TC2.2**: Cannot break existing LiteLLM CustomLogger interface
- **TC2.3**: Must support current ccproxy configuration schema

### TC3: Performance Limits

- **TC3.1**: JSONL parsing must not block request processing
- **TC3.2**: Context injection must complete within request timeout
- **TC3.3**: Memory usage must scale linearly with conversation length
- **TC3.4**: File system access must be optimized for concurrent requests

## Success Metrics

### Context Preservation

- **Metric**: Cross-provider context continuity rate
- **Target**: 100% preservation of conversation exchanges
- **Measurement**: Automated testing with provider switching scenarios

### Performance Impact

- **Metric**: Context injection latency increase
- **Target**: <10% increase vs baseline (no context preservation)
- **Measurement**: Performance benchmarking before/after implementation

### Storage Efficiency

- **Metric**: Storage overhead from context preservation
- **Target**: Minimal additional storage (leverage existing Claude Code JSONL)
- **Measurement**: File system usage analysis after implementation

## Out of Scope

- Modification of Claude Code's JSONL format or storage structure
- Integration with other CLI tools beyond Claude Code
- Real-time synchronization of conversation state
- Backup and recovery of Claude Code project files
- Performance optimization of Claude Code's JSONL writing

## Implementation Priority

### P0 (Critical)

- JSONL reader implementation and testing
- Session ID mapping and validation
- Basic context injection using Claude Code data

### P1 (High)

- Hook system integration with CCProxyHandler
- Performance optimization and caching
- Comprehensive test suite and validation
- Production monitoring and alerting

### P2 (Medium)

- Advanced configuration options and tuning
- Extended error handling and recovery
- Documentation and deployment guides
- Analytics and debugging capabilities

### P3 (Low)

- Additional provider metadata features
- Enhanced caching strategies
- Performance profiling and optimization
- Extended compatibility testing

## Dependencies & Assumptions

### External Dependencies

- Claude Code continues using current JSONL storage format
- `~/.claude/projects/` directory structure remains stable
- JSONL files remain accessible for read operations
- Session ID format in Claude Code remains consistent

### Internal Dependencies

- Existing ccproxy hook system architecture
- LiteLLM CustomLogger interface compatibility
- Current configuration and deployment procedures
- Test infrastructure for cross-provider scenarios

### Key Assumptions

- Claude Code project files are accessible from ccproxy runtime environment
- JSONL parsing performance is acceptable for production usage
- Session ID mapping can be reliably established between systems
- ccproxy users will benefit significantly from cross-provider context continuity

This feature represents a significant capability enhancement that enables advanced provider routing while maintaining seamless user experience through comprehensive context preservation.
