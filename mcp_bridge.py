#!/usr/bin/env python3
"""
Optimized MCP Bridge - Faster responses, better error handling
"""
import json
import sys
import urllib.request
import urllib.parse
import ssl
import time

def send_request(data):
    """Send HTTPS request with optimized timing"""
    try:
        # Prepare request
        json_data = json.dumps(data).encode('utf-8')
        
        # Use HTTPS through reverse proxy (faster route)
        req = urllib.request.Request(
            'https://zap.zicuro.shop/mcp',
            data=json_data,
            headers={
                'Content-Type': 'application/json',
                'Connection': 'keep-alive',  # Reuse connections
                'User-Agent': 'Claude-MCP-Bridge/1.0'
            }
        )
        
        # Optimized SSL context
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers('HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA')
        
        # Shorter timeout for faster failure detection
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
            
    except urllib.error.HTTPError as e:
        # Handle HTTP errors specifically
        try:
            error_response = json.loads(e.read().decode('utf-8'))
            return error_response
        except:
            return {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"HTTP {e.code}: {e.reason}"
                }
            }
    except urllib.error.URLError as e:
        return {
            "jsonrpc": "2.0",
            "id": data.get("id"),
            "error": {
                "code": -32603,
                "message": f"Connection error: {str(e.reason)}"
            }
        }
    except Exception as e:
        # ENSURE ID IS NEVER None
        safe_id = data.get("id", "bridge-error") if isinstance(data, dict) else "bridge-error"
        return {
            "jsonrpc": "2.0",
            "id": safe_id,
            "error": {
                "code": -32603,
                "message": f"Bridge error: {str(e)}"
            }
        }

def main():
    """Optimized main loop with better error handling"""
    try:
        # Set stdout to line buffering for immediate output
        sys.stdout.reconfigure(line_buffering=True)
        
        while True:
            try:
                # Read line with timeout handling
                line = sys.stdin.readline()
                
                if not line:  # EOF
                    break
                    
                line = line.strip()
                if not line:
                    continue
                
                # Parse and validate JSON
                try:
                    request = json.loads(line)
                    
                    # Quick validation
                    if not isinstance(request, dict) or "method" not in request:
                        raise ValueError("Invalid request format")
                        
                except (json.JSONDecodeError, ValueError) as e:
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": f"Parse error: {str(e)}"
                        }
                    }
                    print(json.dumps(error_response), flush=True)
                    continue
                
                # Send request and get response
                response = send_request(request)
                
                # Output response immediately
                print(json.dumps(response), flush=True)
                
            except KeyboardInterrupt:
                break
            except BrokenPipeError:
                # Claude Desktop closed the connection
                break
            except Exception as e:
                # Log unexpected errors to stderr
                print(f"Bridge error: {e}", file=sys.stderr)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": f"Bridge internal error: {str(e)}"
                    }
                }
                print(json.dumps(error_response), flush=True)
                
    except Exception as e:
        print(f"Fatal bridge error: {e}", file=sys.stderr)
    finally:
        # Clean shutdown
        try:
            sys.stdout.flush()
        except:
            pass

if __name__ == "__main__":
    main()