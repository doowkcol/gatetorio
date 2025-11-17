#!/bin/bash
# Start development server

set -e

# Activate virtual environment
source venv/bin/activate

# Set DEBUG mode
export DEBUG=True

# Run the server
echo "Starting Gatetorio Central Server (development mode)..."
python run.py
