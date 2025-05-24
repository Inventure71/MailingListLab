#!/bin/bash

if [ -f logs/server.pid ]; then
    PID=$(cat logs/server.pid)
    echo "Stopping server with PID: $PID"
    kill $PID
    
    # Wait a moment and check if process still exists
    sleep 2
    if kill -0 $PID 2>/dev/null; then
        echo "Process still running, force killing..."
        kill -9 $PID
    fi
    
    rm logs/server.pid
    echo "Server stopped"
else
    echo "No PID file found. Server may not be running or was started manually."
    echo "To find and kill manually:"
    echo "  ps aux | grep server_v2.py"
    echo "  kill <PID>"
fi 