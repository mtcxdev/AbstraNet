import asyncio
import json
import os
import sqlite3
from fastapi import FastAPI, Request, HTTPException, Depends
import uvicorn
import aiohttp
from typing import Optional
from fastapi.security import APIKeyHeader

DB_FILE = "nodes.db"  # SQLite database file
PORT = 8000  # Enforce a single port for all nodes

app = FastAPI()
api_key_header = APIKeyHeader(name="X-API-Key")

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            api_key TEXT PRIMARY KEY,
            email TEXT NOT NULL
        )
    """)
    conn.commit()

    # Check if the table is empty
    cursor.execute("SELECT COUNT(*) FROM api_keys")
    if cursor.fetchone()[0] == 0:
        api_key = input("Enter API key for bootstrap node: ")
        email = input("Enter email for bootstrap node: ")
        cursor.execute("INSERT INTO api_keys (api_key, email) VALUES (?, ?)", (api_key, email))
        conn.commit()
        print("✅ API key registered successfully")
    
    conn.close()

init_db()

def get_api_keys():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT api_key FROM api_keys")
    keys = {row[0] for row in cursor.fetchall()}
    conn.close()
    return keys

class Node:
    def __init__(self, api_key="0.0.0", bootstrap_host=None):
        self.api_key = api_key
        self.bootstrap_host = bootstrap_host
        self.api_keys = get_api_keys()

    async def connect_to_network(self):
        """Connects to the network using HTTP."""
        if self.api_key not in self.api_keys:
            print("❌ Connection refused: Invalid API key")
            return

        if not self.bootstrap_host:
            print("⚠️ No bootstrap node specified. Skipping connection.")
            return
        
        url = f"http://{self.bootstrap_host}:{PORT}/connect"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"X-API-Key": self.api_key}) as response:
                    if response.status == 200:
                        print(f"✅ Connected to network via {self.bootstrap_host}:{PORT}")
        except Exception as e:
            print(f"❌ Failed to connect to network {self.bootstrap_host}:{PORT} - {e}")

def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key not in get_api_keys():
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

@app.get("/")
async def handle_connection(request: Request, api_key: str = Depends(get_api_key)):
    """Handles incoming HTTP node connections."""
    print(f"🔗 Connected with {request.client.host}")
    return {"message": "Connected successfully"}

@app.post("/message")
async def send_message(request: Request, api_key: str = Depends(get_api_key)):
    """Handles message exchange between nodes."""
    data = await request.json()
    message = data.get("message", "")
    print(f"📩 Received from {request.client.host}: {message}")
    return {"response": f"Host has received your message: {message}"}

@app.post("/register")
async def register_node(request: Request):
    """Registers a new node with an API key and email."""
    data = await request.json()
    api_key = data.get("api_key")
    email = data.get("email")
    
    if not api_key or not email:
        raise HTTPException(status_code=400, detail="Missing API key or email")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO api_keys (api_key, email) VALUES (?, ?)", (api_key, email))
    conn.commit()
    conn.close()
    
    return {"message": "Node registered successfully"}

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 2 and sys.argv[1] == "start_node":
        api_key = "0.0.0"
        bootstrap_host = None
    elif len(sys.argv) >= 3:
        api_key = sys.argv[1]
        bootstrap_host = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        print("Usage: python node.py <api_key> [bootstrap_host] or python node.py start_node")
        sys.exit(1)

    node = Node(api_key=api_key, bootstrap_host=bootstrap_host)
    asyncio.run(node.connect_to_network())
    uvicorn.run(app, host="0.0.0.0", port=PORT)
