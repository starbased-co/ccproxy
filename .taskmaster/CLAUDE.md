# Task Master CLAUDE.md

## Quick Reference

```bash
# Setup
task-master init
task-master parse-prd .taskmaster/docs/prd.txt
task-master models --setup

# Daily
task-master next                               # Get next task
task-master show <id>                          # View task details
task-master set-status --id=<id> --status=done # Complete task

# Management
task-master add-task --prompt="..." --research
task-master expand --id=<id> --research --force
task-master update-task --id=<id> --prompt="..."
task-master update-subtask --id=<id> --prompt="..."

# Analysis
task-master analyze-complexity --research
task-master expand --all --research
```

## Structure

- `.taskmaster/tasks/tasks.json` - Task database (auto-managed)
- `.taskmaster/config.json` - Model config
- `.taskmaster/docs/prd.txt` - PRD for parsing
- `.mcp.json` - MCP config
- `CLAUDE.md` - This file

## MCP Tools

```javascript
// Setup
initialize_project    // task-master init
parse_prd            // task-master parse-prd

// Daily
get_tasks            // task-master list
next_task            // task-master next
get_task             // task-master show <id>
set_task_status      // task-master set-status

// Management
add_task             // task-master add-task
expand_task          // task-master expand
update_task          // task-master update-task
update_subtask       // task-master update-subtask

// Analysis
analyze_project_complexity
complexity_report
```

## Workflows

### Initialize
```bash
task-master init
task-master parse-prd .taskmaster/docs/prd.txt
task-master analyze-complexity --research
task-master expand --all --research
```

### Daily Loop
```bash
task-master next
task-master update-subtask --id=<id> --prompt="notes"
task-master set-status --id=<id> --status=done
```

### Append Tasks
`task-master parse-prd --append` for new PRD additions

### Slash Commands

`.claude/commands/tm-next.md`:
```
task-master next && task-master show <id>
```

`.claude/commands/tm-done.md`:
```
task-master set-status --id=$ARGUMENTS --status=done && task-master next
```

## Allowlist

```json
{
  "allowedTools": [
    "Edit",
    "Bash(task-master *)",
    "mcp__task_master_ai__*"
  ]
}
```

## Setup

**Required**: One+ API key (ANTHROPIC_API_KEY, PERPLEXITY_API_KEY recommended)

```bash
task-master models --setup
```

## Task IDs & Status

**IDs**: `1`, `1.1`, `1.1.1`
**Status**: `pending`, `in-progress`, `done`, `deferred`, `cancelled`, `blocked`

## Best Practices

### Implementation Flow
1. `task-master show <id>`
2. `task-master update-subtask --id=<id> --prompt="plan"`
3. `task-master set-status --id=<id> --status=in-progress`
4. Implement
5. `task-master update-subtask --id=<id> --prompt="progress"`
6. `task-master set-status --id=<id> --status=done`

### Git
```bash
git commit -m "feat: implement feature (task 1.2)"
```

## Troubleshooting

- **AI fails**: Check API keys, run `task-master models`
- **MCP fails**: Check `.mcp.json`, use CLI fallback
- **Sync issues**: `task-master generate`
- **Never re-initialize** - won't fix issues

## Notes

**AI Operations** (may take ~1min): parse-prd, analyze-complexity, expand, add-task, update operations

**Files**: Never edit tasks.json or config.json manually

**Research**: Add --research flag (requires PERPLEXITY_API_KEY)

**Updates**:
- `update --from=<id>` for multiple tasks
- `update-task --id=<id>` for single task
- `update-subtask --id=<id>` for logging
