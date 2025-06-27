#!/bin/bash
set -euo pipefail

echo "🚀 Starting Zerodha Kite Trading Services on Droplet..."
echo "=================================================="

# Ensure data directory exists and has proper permissions
mkdir -p /app/data /app/logs
chmod 755 /app/data /app/logs

# Start the OAuth callback server in the background
echo "🌐 Starting OAuth Callback Server (port 8080)..."
python3 /app/callback_server.py &
CALLBACK_PID=$!

# Wait a moment for the callback server to start
sleep 3

# Check if callback server started successfully
if curl -s http://localhost:8080/health | grep -q "healthy"; then
    echo "✅ Callback server is responding"
else
    echo "❌ Callback server did not respond"
    exit 1
fi

# Start the MCP server in the background
echo "🤖 Starting MCP Server (port 3000)..."
python3 /app/mcp_server.py &
MCP_PID=$!

# Wait a moment for the MCP server to start
sleep 3

# Check if MCP server started successfully
if [ -e /proc/$MCP_PID ]; then
    echo "✅ MCP Server started successfully (PID: $MCP_PID)"
else
    echo "❌ Failed to start MCP Server"
    kill $CALLBACK_PID 2>/dev/null
    exit 1
fi

echo "=================================================="
echo "✅ All services are running on droplet!"
echo "🌐 OAuth Callback Server: http://0.0.0.0:8080"
echo "🤖 MCP Server: http://0.0.0.0:3000"
echo "🔗 Callback URL: https://zap.zicuro.shop/callback"
echo "🔗 Claude Desktop URL: https://zap.zicuro.shop:3000/mcp"
echo "📁 Token storage: /app/data/kite_tokens.json"
echo "=================================================="

# Function to handle shutdown
cleanup() {
    echo "🛑 Shutting down services..."
    kill $CALLBACK_PID 2>/dev/null || true
    kill $MCP_PID 2>/dev/null || true
    echo "✅ Services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Keep the script running and monitor processes
while true; do
    if [ ! -e /proc/$CALLBACK_PID ]; then
        echo "❌ OAuth Callback Server died, restarting..."
        python3 /app/callback_server.py &
        CALLBACK_PID=$!
    fi

    if [ ! -e /proc/$MCP_PID ]; then
        echo "❌ MCP Server died, restarting..."
        python3 /app/mcp_server.py &
        MCP_PID=$!
    fi

    sleep 30
done
