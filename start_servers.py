#!/usr/bin/env python3
"""
Startup script to run both MCP server and OAuth callback server
"""

import asyncio
import subprocess
import sys
import logging
import signal
import os
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ServerManager:
    def __init__(self):
        self.processes = []
        self.running = True
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        _ = frame  # Unused parameter
        logger.info(f"🛑 Received signal {signum}, shutting down servers...")
        self.running = False
        self.stop_all_servers()
        sys.exit(0)
        
    def start_callback_server(self):
        """Start the OAuth callback server"""
        port = os.getenv('CALLBACK_SERVER_PORT', '8080')
        logger.info(f"🌐 Starting OAuth Callback Server (port {port})...")
        try:
            process = subprocess.Popen([
                sys.executable, "callback_server.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
               env=dict(os.environ, CALLBACK_SERVER_PORT=port))
            self.processes.append(("callback_server", process))
            logger.info("✅ OAuth Callback Server started")
            return process
        except Exception as e:
            logger.error(f"❌ Failed to start callback server: {e}")
            return None
            
    def start_mcp_server(self):
        """Start the MCP server"""
        port = os.getenv('MCP_SERVER_PORT', '3000')
        logger.info(f"🤖 Starting MCP Server (port {port})...")
        try:
            process = subprocess.Popen([
                sys.executable, "mcp_server.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
               env=dict(os.environ, MCP_SERVER_PORT=port))
            self.processes.append(("mcp_server", process))
            logger.info("✅ MCP Server started")
            return process
        except Exception as e:
            logger.error(f"❌ Failed to start MCP server: {e}")
            return None
            
    def stop_all_servers(self):
        """Stop all running servers"""
        for name, process in self.processes:
            if process and process.poll() is None:
                logger.info(f"🛑 Stopping {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                    logger.info(f"✅ {name} stopped")
                except subprocess.TimeoutExpired:
                    logger.warning(f"⚠️ Force killing {name}...")
                    process.kill()
                    
    def monitor_processes(self):
        """Monitor running processes and restart if needed"""
        while self.running:
            for i, (name, process) in enumerate(self.processes):
                if process.poll() is not None:
                    logger.error(f"❌ {name} has stopped unexpectedly")
                    # Restart the process
                    if name == "callback_server":
                        new_process = self.start_callback_server()
                    elif name == "mcp_server":
                        new_process = self.start_mcp_server()
                    else:
                        continue

                    if new_process:
                        self.processes[i] = (name, new_process)
                        logger.info(f"🔄 {name} restarted")

            # Sleep before next check
            time.sleep(5)
            
    async def run(self):
        """Main run method"""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("🚀 Starting Zerodha Kite Trading Servers...")
        logger.info("=" * 50)
        
        # Start both servers
        callback_process = self.start_callback_server()
        mcp_process = self.start_mcp_server()
        
        if not callback_process or not mcp_process:
            logger.error("❌ Failed to start one or more servers")
            self.stop_all_servers()
            return
            
        callback_port = os.getenv('CALLBACK_SERVER_PORT', '8080')
        mcp_port = os.getenv('MCP_SERVER_PORT', '3000')

        logger.info("=" * 50)
        logger.info("✅ All servers started successfully!")
        logger.info(f"🌐 OAuth Callback Server: https://zap.zicuro.shop:{callback_port}")
        logger.info(f"🤖 MCP Server: https://zap.zicuro.shop:{mcp_port}/mcp")
        logger.info("🔗 Callback URL: https://zap.zicuro.shop/callback")
        logger.info("💡 Claude Desktop MCP URL: https://zap.zicuro.shop:3000/mcp")
        logger.info("=" * 50)
        
        # Monitor processes
        try:
            while self.running:
                await asyncio.sleep(5)
                
                # Check if processes are still running
                for name, process in self.processes:
                    if process.poll() is not None:
                        logger.error(f"❌ {name} has stopped")
                        self.running = False
                        break
                        
        except KeyboardInterrupt:
            logger.info("🛑 Received keyboard interrupt")
        finally:
            self.stop_all_servers()

async def main():
    """Main entry point"""
    manager = ServerManager()
    await manager.run()

if __name__ == "__main__":
    asyncio.run(main())
