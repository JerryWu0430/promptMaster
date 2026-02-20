Search and answer questions about your Claude Code conversation history.

User's question: $ARGUMENTS

Instructions:
1. First, extract key search terms from the user's question
2. Run the search script to find relevant past conversations:
   ```
   python3 ~/.claude/scripts/history_search.py search "<search terms>"
   ```
3. If user asks to list sessions: `python3 ~/.claude/scripts/history_search.py sessions`
4. If user asks about a specific session: `python3 ~/.claude/scripts/history_search.py show <session_id>`
5. Analyze the search results and answer the user's question based on the conversation history
6. If no results found, try different/broader search terms
7. Quote relevant parts of past conversations when answering

If database doesn't exist, tell user to run:
```
python3 ~/.claude/scripts/history_index.py
```
