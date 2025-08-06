# Job Adder AI Outreach Agent PoC

An AI-powered Outreach Agent that can autonomously choose candidate matches
for a job and communicate via a simple message service.

Demonstrates a simple autonomous agent control loop, and their interaction
with an MCP server.

## Prerequisites

- [UV](https://github.com/astral-sh/uv) package manager
- Ollama or OPENAI_API_KEY in the environment

## Installation

1. Install dependencies:

```bash
uv sync
```

2. Copy the example environment file and update with your API key:

```bash
cp .env.example .env
# OPENAI_API_KEY=<your OpenAI API key>
```

3. Create random Outreach Agent's candidates in the db

```bash
uv run people.py
```

4. Create random Outreach Agent's jobs in the db

```bash
uv run jobs.py
```

## Usage

For Outreach Agent PoC to work, we need 3 servers running, 1) the Candidate simulator;
2) the MCP server and 3) the Outreach Agent Server.


1. the People simulator `../pycandidate/simulator/app.py`:

       cd ../pycandidatesimulatr
       uv run uvicorn app:app --reload

2. the MCP server:

       uv run mcp_server.py

3. the Agent server, which will run the agent and a GUI:

       uv run agent_server.py

4. open the people simulator GUI:

       http://localhost:8000

5. open the Outreach Agent GUI:

       http://localhost:3000

This will start the agent server with the default configuration and open `index.html` in your browser to interact with the agent through the web interface.

## Dev startup

If you can install `ttab` with `npm`, you can start all 3 servers, and
open the two GUI via one cli command:

    ./start.sh


## Project Structure

- `agent.py`: Core agent implementation
- `agent_server.py`: HTTP server for the agent, and agent loop runner
- `chat_client.py`: Chat client interface
- `mcp_client.py`: MCP client connects to MCP server and chat_client
- `mcp_server.py`: MCP server that connects to jobs and candidates
- `jobs.py`: Manages Jobs database
- `candidates.py`: Manages Candidates database
- `index.html`: GUI to the Outreach Agent

