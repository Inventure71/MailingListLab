#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the server with nohup, redirecting output to logs folder
# stdout and stderr both go to logs/nohup.out
nohup python3 server_v2.py > logs/nohup.out 2>&1 &

# Get the process ID
PID=$!

echo "Server started with PID: $PID"
echo "Application logs: logs/server.log (rotated at 5MB, 3 backups)"
echo "System output logs: logs/nohup.out"
echo "To stop the server: kill $PID"
echo "To view logs in real-time:"
echo "  Application logs: tail -f logs/server.log"
echo "  System logs: tail -f logs/nohup.out"

# Save PID to file for easy stopping
echo $PID > logs/server.pid
echo "PID saved to logs/server.pid" 