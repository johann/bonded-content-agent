#!/bin/bash
# Quick script to run the agent locally for testing

echo "🔍 Checking environment..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "📝 Create a .env file with your credentials:"
    echo "   cp .env.example .env"
    echo "   # Then edit .env with your actual API keys"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found!"
    exit 1
fi

# Check if dependencies are installed
if ! python3 -c "import anthropic" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip3 install -r requirements.txt
fi

echo "✅ Environment ready!"
echo ""
echo "🚀 Running agent..."
echo ""

# Run the agent
cd src && python3 main.py

