Search and answer questions about your Claude Code conversation history.

User's question: $ARGUMENTS

Instructions:
1. List recent session files:
   ```
   ls -lt ~/.claude/projects/-/*.jsonl 2>/dev/null | head -20
   ```

2. Read relevant sessions based on user's question (use Read tool):
   - General questions → read 2-3 most recent sessions
   - Specific topics → grep first, then read matches:
     ```
     grep -l "search term" ~/.claude/projects/-/*.jsonl | head -5
     ```

3. Session JSONL format:
   - `type`: "user" or "assistant"
   - `message.content[].text`: actual conversation text
   - `cwd`: project path
   - `gitBranch`: branch name
   - `timestamp`: when

4. Analyze and provide actionable insights:
   - Patterns and repeated mistakes
   - What worked vs failed
   - Concrete suggestions for improvement
   - Quote relevant parts when useful

Focus on personal, actionable advice - not raw search results.
