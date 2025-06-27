# Claude Desktop + Droplet Setup Guide

## 🎯 **Perfect Setup for Your Use Case**

This guide sets up the exact workflow you want:
1. **MCP Server runs on droplet** (at https://zap.zicuro.shop:3000)
2. **Claude Desktop connects via HTTP** (to droplet MCP server)
3. **User clicks login link** (provided by Claude)
4. **Automatic token capture** (on droplet, stored in mounted file)
5. **Seamless trading** (through Claude Desktop)

## 🚀 **Step 1: Deploy Droplet Server**

### On your droplet (zap.zicuro.shop):

```bash
# Clone your repository
git clone <your-repo-url> kite-trading
cd kite-trading

# Set environment variables
export KITE_API_KEY="your_actual_api_key"
export KITE_API_SECRET="your_actual_api_secret"

# Deploy the callback server
docker-compose up -d

# Verify it's running
curl https://zap.zicuro.shop:8080/health
```

## 🖥️ **Step 2: Setup Claude Desktop (Local Machine)**

### Configure Claude Desktop to connect to your droplet:

Add this to your Claude Desktop MCP configuration file:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "zerodha-kite-trading": {
      "url": "https://zap.zicuro.shop:3000",
      "transport": "http"
    }
  }
}
```

**That's it!** No local installation needed - Claude connects directly to your droplet.

## 🔄 **Step 3: Authentication Flow**

### First time authentication:

1. **Ask Claude:** "Check my authentication status"
   - Claude calls: `check_authentication_status()`
   - Response: "❌ Not authenticated"

2. **Ask Claude:** "Get me a login URL"
   - Claude calls: `get_kite_login_url()`
   - Response: Login URL for Kite Connect

3. **Click the URL** in your browser (any device)
   - Login with your Zerodha credentials
   - Kite redirects to: `https://zap.zicuro.shop/callback`
   - Droplet automatically captures and stores token

4. **Ready to trade!**
   - Ask Claude: "Buy 10 shares of RELIANCE"
   - Claude executes the trade using stored tokens

## 📱 **Step 4: Daily Usage**

### Normal trading (when authenticated):
```
You: "Buy 5 shares of TCS"
Claude: ✅ BUY Order Successful! Order ID: 240101000000001

You: "Show my portfolio"
Claude: [Portfolio details]

You: "Sell 3 shares of RELIANCE"
Claude: ✅ SELL Order Successful! Order ID: 240101000000002
```

### When token expires:
```
You: "Buy 10 shares of INFY"
Claude: ❌ Authentication Expired
        Your session has expired. Please use get_kite_login_url() to re-authenticate.

You: "Get me a login URL"
Claude: 🔗 Click this link to login: [URL]
[You click, login, done]

You: "Buy 10 shares of INFY"
Claude: ✅ BUY Order Successful!
```

## 🔧 **Available Commands in Claude**

- `check_authentication_status()` - Check if you're logged in
- `get_kite_login_url()` - Get login URL when needed
- `buy_stock("SYMBOL", quantity)` - Buy shares
- `sell_stock("SYMBOL", quantity)` - Sell shares  
- `show_portfolio()` - View your positions
- `server_health_check()` - Check system status

## 🛠️ **Troubleshooting**

### If authentication fails:
```bash
# Check droplet server
curl https://zap.zicuro.shop:8080/health

# Check logs
docker-compose logs -f

# Restart if needed
docker-compose restart
```

### If Claude can't connect:
1. Check MCP configuration path
2. Verify environment variables
3. Restart Claude Desktop

## 🔐 **Security Notes**

- ✅ **Tokens stored securely** on droplet in mounted volume
- ✅ **HTTPS throughout** the authentication flow
- ✅ **No credentials in Claude config** (only API keys)
- ✅ **Automatic token refresh** when expired

## 📁 **File Locations**

- **Droplet tokens:** `/app/data/kite_tokens.json` (in Docker container)
- **Local MCP server:** Runs from your local machine
- **Callback handler:** Runs on droplet at port 8080

This setup gives you exactly what you want: seamless trading through Claude with automatic authentication handling!
