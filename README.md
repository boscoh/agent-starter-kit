# Agent Starter Kit

AI-powered agent for matching candidates to job opportunities and managing communications.

## 🚀 Quick Start

1. **Install dependencies**
   ```bash
   uv sync
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY to .env
   ```

3. **Initialize data**
   ```bash
   uv run reset.py
   ```

4. **Start services**
   - Manual (development):
     ```bash
     # Terminal 1
     rm -f emails.json*
     uv run people_server.py

     # Terminal 2
     uv run mcp_server.py

     # Terminal 3
     uv run agent_server.py --reload
     ```
   - Or use the start script (requires `ttab`):
     ```bash
     npm install -g ttab  # If not installed
     chmod +x start.sh
     ./start.sh
     ```

## 🌐 Web Interfaces
- **Agent Dashboard**: `http://localhost:3000`
- **People Simulator**: `http://localhost:8000`

## 🔧 Project Structure

```
.
├── chat_client.py     # Chat interface to LLM
├── agent.py           # Agents and control loop
├── agent_server.py    # Web server
├── mcp_client.py      # MCP client
├── mcp_server.py      # MCP server to candidate db
├── people.py          # People database 
├── people_server.py   # Email broker and people simulator
├── jobs.py            # Job management database
├── candidates.py      # Candidate database
├── email.py           # Email database
└── reset.py           # Reset and regenerate databases
├── utils.py           # Utilities
├── json_store.py      # Storage
```

## 📝 License
MIT - See [LICENSE](LICENSE)

