# Kite Trading MCP Server

A comprehensive Model Context Protocol (MCP) server for Zerodha Kite Connect trading platform with fully automated authentication.

## Features

- 🤖 **Fully Automated Authentication** - No manual token copying required
- 📊 **Trading Operations** - Buy/sell stocks with comprehensive error handling
- 📈 **Portfolio Management** - View positions and holdings
- 🔐 **Secure Token Management** - Automatic token refresh and validation
- 🐳 **Docker Support** - Easy deployment with Docker Compose
- 📝 **Comprehensive Logging** - Detailed order logging and error tracking
- 🛡️ **Input Validation** - Robust validation for all trading operations

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your Kite Connect credentials
# Get credentials from: https://kite.trade/
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Authenticate

```bash
# Interactive authentication
python auth_manager.py auth

# Or force re-authentication
python auth_manager.py force

# Check authentication status
python auth_manager.py check
```

### 4. Deploy to Droplet

```bash
# Set your API credentials
export KITE_API_KEY="imtwpp6e5x9ozlwt"
export KITE_API_SECRET="21urj6s58d9j4l1gyigpb33sbeta20ac"

# Deploy both servers (MCP + OAuth callback)
docker-compose up -d

# Check logs
docker-compose logs -f

# Or use the deployment script
chmod +x deploy.sh
./deploy.sh
```

The servers will be available at:
- **MCP Server**: `https://zap.zicuro.shop:3000/mcp` (for Claude Desktop)
- **OAuth Callback Server**: `https://zap.zicuro.shop:8080`
- **OAuth Callback URL**: `https://zap.zicuro.shop/callback`

### 5. Connect Claude Desktop to Droplet

Add this to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "zerodha-kite-trading": {
      "url": "https://zap.zicuro.shop:3000/mcp",
      "transport": "http"
    }
  }
}
```

**That's it!** Claude Desktop connects directly to your droplet MCP server.

## Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `KITE_API_KEY` | Yes | Your Kite Connect API Key | - |
| `KITE_API_SECRET` | Yes | Your Kite Connect API Secret | - |
| `KITE_REDIRECT_URL` | No | Custom redirect URL | `http://localhost:8080/callback` |
| `DROPLET_URL` | No | Token exchange URL | `http://localhost:5001/auth/exchange` |
| `LOCAL_PORT` | No | Local server port | `8765` |
| `DOCKER_ENV` | No | Docker environment flag | `false` |

## Authentication Methods

### 1. Droplet-Hosted MCP Server (Your Architecture)
- **MCP Server runs on droplet**: `https://zap.zicuro.shop:3000`
- **Claude Desktop connects via HTTP**: Direct connection to droplet
- **OAuth callback on droplet**: `https://zap.zicuro.shop:8080`
- **User authenticates locally**: Browser opens Kite Connect login
- **Automatic token capture**: Droplet receives callback and stores tokens
- **Seamless trading**: Claude uses MCP tools for all operations

**Perfect Flow for Your Use Case:**
1. User asks Claude to trade (e.g., "Buy 10 RELIANCE shares")
2. If not authenticated, Claude provides login URL via `get_kite_login_url()`
3. User clicks link and logs into Zerodha in their browser (any device/OS)
4. Kite redirects to `https://zap.zicuro.shop/callback`
5. Droplet automatically captures and stores tokens in mounted Docker file
6. Claude can now execute trades seamlessly
7. When token expires, Claude automatically provides new login URL

### 2. Manual Authentication
- For Docker/headless environments
- Manual URL copying required
- Fallback when browser automation fails

```bash
python auth_manager.py manual
```

## API Usage

### MCP Tools Available in Claude Desktop

- `get_kite_login_url()` - Get authentication URL for user to login
- `check_authentication_status()` - Check if user is authenticated
- `buy_stock(stock, qty)` - Buy shares (e.g., buy_stock("RELIANCE", 10))
- `sell_stock(stock, qty)` - Sell shares (e.g., sell_stock("TCS", 5))
- `show_portfolio()` - View current positions and holdings
- `server_health_check()` - Check server status and authentication

### OAuth Callback Server Endpoints

- `GET /callback` - OAuth callback handler (for Kite Connect)
- `POST /auth/exchange` - Exchange request token for access token
- `GET /health` - Server health check

### Direct Python Usage

```python
from trading import place_order, get_positions

# Place a buy order
result = place_order("RELIANCE", 10, "BUY")
print(result)

# Get current positions
positions = get_positions()
print(positions)
```

## File Structure

```
├── auth_fully_automated.py    # Main authentication logic
├── auth_manager.py            # Unified auth management CLI
├── auth_utils.py              # Common authentication utilities
├── trading.py                 # Core trading functions
├── mcp_server.py             # FastAPI server implementation
├── logger.py                 # Order logging utilities
├── manual_auth.py            # Manual authentication fallback
├── requirements.txt          # Python dependencies
├── Dockerfile               # Docker container config
├── docker-compose.yml       # Docker Compose setup
└── .env.example            # Environment template
```

## Security Notes

- Never commit `.env` files to version control
- API credentials are stored securely in environment variables
- Tokens are saved locally in `data/kite_tokens.json`
- All trading operations include comprehensive input validation

## Troubleshooting

### Authentication Issues
```bash
# Check current status
python auth_manager.py check

# Force re-authentication
python auth_manager.py force

# Try manual authentication
python auth_manager.py manual
```

### Docker Issues
```bash
# Check container logs
docker-compose logs kite-mcp-server

# Restart services
docker-compose restart

# Rebuild containers
docker-compose up --build
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

This project is for educational purposes. Please ensure compliance with Zerodha's terms of service.
