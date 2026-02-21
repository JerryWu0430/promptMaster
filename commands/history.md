Search and answer questions about your Claude Code conversation history.

User's question: $ARGUMENTS

Instructions:

1. List recent session files with sizes:
   ```bash
   ls -ltSh ~/.claude/projects/*/*.jsonl 2>/dev/null | head -30
   ```

2. Search strategy (files often exceed 256KB Read limit):

   a) Use Grep tool to search content:
      - pattern: "search_term"
      - path: ~/.claude/projects
      - glob: "**/*.jsonl"
      - output_mode: "content" with -C 3 for context

   b) For specific topics, chain searches:
      - First: broad topic grep
      - Then: refine with more specific terms
      - Use glob "**/*.jsonl" to search all sessions

   c) For recent activity (last N lines of a file):
      ```bash
      tail -100 ~/.claude/projects/PROJECT_PATH/SESSION.jsonl
      ```

   d) For file structure/stats:
      ```bash
      wc -l ~/.claude/projects/*/*.jsonl | sort -n | tail -20
      ```

   e) Only use Read with offset/limit for targeted extraction:
      - Get line count first: `wc -l FILE`
      - Read last portion: offset=(total-500), limit=500

3. Session JSONL format:
   - `type`: "user" or "assistant"
   - `message.content[].text`: actual conversation text
   - `cwd`: project path
   - `gitBranch`: branch name
   - `timestamp`: when

4. Analyze and provide actionable insights:
   - Patterns and repeated mistakes
   - What worked vs failed
   - Concrete suggestions
   - Quote relevant parts

Focus on personal, actionable advice - not raw search results.
