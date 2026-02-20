# /history - Claude Code History Search

Search & analyze your Claude Code conversation history for patterns and insights.

## Install

### macOS/Linux
```bash
mkdir -p ~/.claude/commands
curl -o ~/.claude/commands/history.md https://raw.githubusercontent.com/JerryWu0430/promptMaster/main/commands/history.md
```

### Windows (PowerShell)
```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\commands"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/JerryWu0430/promptMaster/main/commands/history.md" -OutFile "$env:USERPROFILE\.claude\commands\history.md"
```

## Usage

```
/history what patterns do I have in my prompting?
/history find conversations about authentication
/history how did I solve the auth bug last time?
```

## Troubleshooting

Command not showing? Restart Claude Code CLI.
