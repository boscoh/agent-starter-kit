# Agent Starter Kit

An AI-powered Agent that autonomously matches candidates to job opportunities and handles initial communications.

## Features

- Autonomous agent control loop
- MCP driven candidate-job matching
- Autnomous AI-powered communication 
- Simple message service integration

## Prerequisites

- Python 3.8+
- [UV](https://github.com/astral-sh/uv) package manager
- Ollama or an OpenAI API key in `.env`

## 🚀 Quick Start

1. **Install dependencies**
   ```bash
   uv sync
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. **Initialize Data**
   ```bash
   uv run reset.py
   ```

## 🏃‍♂️ Running the System

### Option 1: Manual Startup (Recommended for Development)

1. **People Server** (handles candidate data)
   ```bash
   # In a new terminal
   rm -f emails.json*  # Clear any existing email data
   uv run people_server.py
   ```

2. **MCP Server** (message control protocol)
   ```bash
   # In a new terminal
   uv run mcp_server.py
   ```

3. **Agent Server** (main application)
   ```bash
   # In a new terminal
   uv run agent_server.py --reload  # Auto-reload for development
   ```

### Option 2: Quick Start (Requires `ttab`)

1. Install ttab (if not already installed):
   ```bash
   npm install -g ttab
   ```

2. Run the start script:
   ```bash
   chmod +x start.sh  # Make script executable if needed
   ./start.sh
   ```
   This will start all services and open the web interfaces in your browser.

## Project Structure

```
.
├── agent.py           # Main agent implementation
├── agent_server.py    # Web server and agent loop runner
├── mcp_client.py      # MCP client connects to MCP server and chat_client
├── mcp_server.py      # MCP protocol server
├── people.py          # Candidate management
├── people_server.py   # HTTP server for candidate data
├── jobs.py            # Job management
├── candidates.py      # Candidates database
├── chat_client.py     # Chat client interface
├── utils.py           # Utility functions
├── json_store.py      # Data persistence
├── reset.py           # Reset application state
├── start.sh           # Start all services
└── browser.sh         # Browser launcher utility
```

## 🌐 Web Interface

Once all services are running, access the following interfaces:

- **Agent Dashboard**: `http://localhost:3000`
- **People Simulator**: `http://localhost:8000`

## 🔍 Troubleshooting

- If you encounter port conflicts, check which process is using the port:
  ```bash
  lsof -i :8000  # Check port 8000
  ```
  
- For debugging, set `DEBUG=true` in your `.env` file for more verbose output

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

