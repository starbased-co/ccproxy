# ccproxy Development Plan

## Project Overview

**ccproxy** - A LiteLLM proxy tool that intelligently routes Claude Code requests to different LLM providers. Current status: v1.2.0, production-ready, under active development.

## User Preferences

- **Focus:** All areas (bug fix, new features, code quality)
- **Shell Integration:** To be completed and activated
- **Web UI:** Not required (CLI is sufficient)

---

## 1. Critical Fixes (High Priority)

### 1.0 OAuth Graceful Fallback (URGENT)
- **File:** `src/ccproxy/config.py` (lines 295-300)
- **Issue:** Proxy fails to start when `oat_sources` is defined but credentials file is missing
- **Impact:** Blocks usage in development/test environments
- **Solution:**
  1. Skip OAuth if `oat_sources` is empty or undefined
  2. Make error messages more descriptive
  3. Optional: Add `oauth_required: false` config flag

### 1.1 Router Initialization Race Condition
- **File:** `src/ccproxy/router.py` (lines 51-66)
- **Issue:** `_models_loaded` flag remains `True` even if `_load_model_mapping()` throws an error
- **Impact:** Can cause silent cascade failures
- **Solution:** Fix exception handling, only set flag on successful load

### 1.2 Request Metadata Store Memory Leak
- **File:** `src/ccproxy/hooks.py` (lines 16-32)
- **Issue:** TTL cleanup only occurs during `store_request_metadata()` calls
- **Impact:** Memory accumulation under irregular traffic
- **Solution:** Add background cleanup task or max size limit

### 1.3 Model Reload Thrashing
- **File:** `src/ccproxy/hooks.py` (line 142)
- **Issue:** `reload_models()` is called every time a model is not found
- **Solution:** Add cooldown period or retry limit

### 1.4 Default Config Usability
- **File:** `src/ccproxy/templates/` or install logic
- **Issue:** `ccproxy install` sets up a non-working default config (OAuth active, no credentials)
- **Impact:** Poor first-time user experience
- **Solution:**
  1. Comment out `oat_sources` section in default config
  2. Comment out `forward_oauth` hook
  3. Document OAuth setup in README

---

## 2. Incomplete Features

### 2.1 Shell Integration Completion (PRIORITY)
- **File:** `src/ccproxy/cli.py` (lines 89-564)
- **Status:** 475 lines of commented code present
- **Goal:** Make the feature functional
- **Tasks:**
  1. Uncomment and review the commented code
  2. Activate `generate_shell_integration()` function
  3. Enable `ShellIntegration` command class
  4. Add Bash/Zsh/Fish shell support
  5. Make `ccproxy shell-integration` command functional
  6. Activate test file `test_shell_integration.py`
  7. Update documentation

### 2.2 DefaultRule Implementation
- **File:** `src/ccproxy/rules.py` (lines 38-40)
- **Issue:** Abstract `evaluate()` method not implemented
- **Solution:** Either implement it or remove the class

### 2.3 Metrics System
- **File:** `src/ccproxy/config.py` - `metrics_enabled: bool = True`
- **Issue:** Config flag exists but no actual metric collection
- **Solution:** Add Prometheus metrics integration or remove the flag

---

## 3. Code Quality Improvements

### 3.1 Exception Handling Specificity
Replace generic `except Exception:` blocks with specific exceptions:

| File | Line | Current | Suggested |
|------|------|---------|-----------|
| handler.py | 54 | `except Exception:` | `except ImportError:` |
| cli.py | 230 | `except Exception:` | `except (OSError, yaml.YAMLError):` |
| rules.py | 128 | `except Exception:` | `except tiktoken.TokenizerError:` |
| utils.py | 179 | `except Exception:` | Specific attr errors |

### 3.2 Debug Output Cleanup
- **File:** `src/ccproxy/handler.py` (lines 75, 139)
- **Issue:** Emoji usage (`🧠`) - violates CLAUDE.md guidelines
- **Solution:** Remove emojis or restrict to debug mode

### 3.3 Type Ignore Comments
- **File:** `src/ccproxy/utils.py` (line 77)
- **Issue:** Complex type ignore - `# type: ignore[operator,unused-ignore,unreachable]`
- **Solution:** Refactor code or fix type annotations

---

## 4. New Feature Proposals

### 4.1 Configuration Validation System
```python
# Validate during ccproxy start:
- Rule name uniqueness check
- Rule name → model name mapping check
- Handler path existence check
- OAuth command syntax validation
```

### 4.2 OAuth Token Refresh
- **Current:** Tokens are only loaded at startup
- **Proposal:** Background refresh mechanism
- **Complexity:** Medium

### 4.3 Rule Caching & Performance
- **Issue:** Each `TokenCountRule` instance has its own tokenizer cache
- **Solution:** Global/shared tokenizer cache

### 4.4 Health Check Endpoint
- `/health` endpoint for monitoring
- Rule evaluation statistics
- Model availability status

### 4.5 Request Retry Logic
- Configurable retry for failed requests
- Backoff strategy
- Fallback model on failure

---

## 5. Test Coverage Improvement

### 5.1 Current Status
- 18 test files, 321 tests
- >90% coverage requirement

### 5.2 Missing Test Areas
1. **CLI Error Recovery** - PID file corruption, race conditions
2. **Config Discovery Precedence** - 3 different source interactions
3. **OAuth Loading Failures** - Timeout, partial failure
4. **Handler Graceful Degradation** - Hook failure scenarios
5. **Langfuse Integration** - Lazy-load and silent fail

### 5.3 Integration Test
- `test_claude_code_integration.py` - Currently skipped
- Make it runnable in CI/CD environment

---

## 6. Documentation Improvements

### 6.1 Troubleshooting Section
- Custom rule loading errors
- Hook chain interruption
- Model routing fallback behavior

### 6.2 Architecture Diagram
- Request flow visualization
- Component interaction diagram

### 6.3 Configuration Examples
- Example configs for different use cases
- Multi-provider setup guide

---

## 7. Potential Major Features

### 7.1 Multi-User Support
- User-specific routing rules
- Per-user token limits
- Usage tracking per user

### 7.2 Request Caching
- Duplicate request detection
- Response caching for identical prompts
- Cache invalidation strategies

### 7.3 A/B Testing Framework
- Model comparison capability
- Response quality metrics
- Cost/performance trade-off analysis

### 7.4 Cost Tracking
- Per-request cost calculation
- Budget limits per model/user
- Cost alerts

---

## 8. Implementation Priority

| Priority | Category | Complexity | Files |
|----------|----------|------------|-------|
| 1 | **OAuth graceful fallback** | Low | `config.py` |
| 2 | **Default config fix** | Low | templates, `cli.py` |
| 3 | Router race condition fix | Low | `router.py` |
| 4 | Metadata store memory fix | Low | `hooks.py` |
| 5 | Model reload cooldown | Low | `hooks.py` |
| 6 | **Shell Integration completion** | Medium | `cli.py`, `test_shell_integration.py` |
| 7 | Exception handling improvement | Medium | `handler.py`, `cli.py`, `rules.py`, `utils.py` |
| 8 | Debug emoji cleanup | Low | `handler.py` |
| 9 | DefaultRule implementation | Low | `rules.py` |
| 10 | Config validation system | Medium | `config.py` |
| 11 | Metrics implementation | Medium | New file may be needed |
| 12 | Test coverage improvement | Medium | `tests/` directory |
| 13 | OAuth token refresh | Medium | `hooks.py`, `config.py` |
| 14 | Documentation | Low | `docs/`, `README.md` |

---

## Critical Files

Main files to be modified:
- `src/ccproxy/router.py` - Race condition fix
- `src/ccproxy/hooks.py` - Memory leak, reload cooldown
- `src/ccproxy/cli.py` - Shell integration
- `src/ccproxy/handler.py` - Exception handling, emoji cleanup
- `src/ccproxy/rules.py` - DefaultRule, exception handling
- `src/ccproxy/config.py` - Validation system
- `tests/test_shell_integration.py` - Activate shell tests
