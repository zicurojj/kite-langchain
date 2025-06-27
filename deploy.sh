#!/bin/bash

echo "🚀 Deploying Zerodha Kite Trading MCP Server to Droplet"
echo "=" * 60

# Set environment variables with your API credentials
export KITE_API_KEY="imtwpp6e5x9ozlwt"
export KITE_API_SECRET="21urj6s58d9j4l1gyigpb33sbeta20ac"
export KITE_REDIRECT_URL="https://zap.zicuro.shop/callback"
export DROPLET_CALLBACK_URL="http://localhost:8080"

echo "✅ Environment variables set:"
echo "   KITE_API_KEY: ${KITE_API_KEY}"
echo "   KITE_API_SECRET: ${KITE_API_SECRET:0:8}..."
echo "   KITE_REDIRECT_URL: ${KITE_REDIRECT_URL}"
echo "   DROPLET_CALLBACK_URL: ${DROPLET_CALLBACK_URL}"

echo ""
echo "🐳 Starting Docker containers..."

# Deploy with docker-compose
docker-compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

echo ""
echo "🔍 Checking service health..."

# Check OAuth callback server
echo "Checking OAuth Callback Server..."
if curl -f -s https://zap.zicuro.shop:8080/health > /dev/null; then
    echo "✅ OAuth Callback Server: HEALTHY"
else
    echo "❌ OAuth Callback Server: NOT RESPONDING"
fi

# Check MCP server
echo "Checking MCP Server..."
if curl -f -s https://zap.zicuro.shop:3000/health > /dev/null; then
    echo "✅ MCP Server: HEALTHY"
else
    echo "❌ MCP Server: NOT RESPONDING"
fi

echo ""
echo "📋 Deployment Summary:"
echo "=" * 40
echo "🌐 OAuth Callback Server: https://zap.zicuro.shop:8080"
echo "🤖 MCP Server: https://zap.zicuro.shop:3000/mcp"
echo "🔗 OAuth Callback URL: https://zap.zicuro.shop/callback"
echo "📁 Token Storage: ./data/kite_tokens.json (mounted)"

echo ""
echo "🖥️ Claude Desktop Configuration:"
echo "Add this to your Claude Desktop config file:"
echo ""
echo '{'
echo '  "mcpServers": {'
echo '    "zerodha-kite-trading": {'
echo '      "url": "https://zap.zicuro.shop:3000/mcp",'
echo '      "transport": "http"'
echo '    }'
echo '  }'
echo '}'

echo ""
echo "🎉 Deployment Complete!"
echo "💡 Next steps:"
echo "1. Configure Claude Desktop with the JSON above"
echo "2. Restart Claude Desktop"
echo "3. Test with: 'Check my authentication status'"
echo "4. If needed: 'Get me a login URL'"
echo "5. Start trading: 'Buy 10 shares of RELIANCE'"
