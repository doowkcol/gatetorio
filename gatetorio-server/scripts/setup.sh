#!/bin/bash
# Setup script for Gatetorio Central Server

set -e

echo "Setting up Gatetorio Central Server..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env file with your configuration"
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p uploads
mkdir -p mosquitto/data
mkdir -p mosquitto/log

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Run './scripts/start-dev.sh' to start the development server"
echo "   OR"
echo "   Run 'docker-compose up' to start with Docker"
