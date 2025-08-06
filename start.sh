#!/bin/bash
# Starts all servers in separate Terminal tabs using ttab. Assumes Python venv is in .venv and ttab is installed.


if command -v psword &> /dev/null; then
    psword -k Cellar
    psword -k pycandidate
    sleep 5
fi

# Check if ttab is installed
if ! command -v ttab &> /dev/null; then
    echo "ttab allows this script to open servers in new terminal tabs for you"
    echo "Error: 'ttab' command not found. Please install it using:"
    echo "  npm install -g ttab"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

ttab bash -c "cd $PROJECT_DIR; rm emails.json*; uv run people_server.py"
./browser.sh http://localhost:8000 &

ttab bash -c "cd $PROJECT_DIR; uv run mcp_server.py"

ttab bash -c "cd $PROJECT_DIR; uv run agent_server.py"
./browser.sh http://localhost:3000 &
