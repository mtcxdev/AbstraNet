import asyncio
import json
import os
from fastapi import FastAPI
import uvicorn

PEERS_FILE = "peers.json"  # Stores known peers

app = FastAPI()

class Node:
    def __init__(self, host="127.0.0.1", port=5000, bootstrap_host=None, bootstrap_port=None):
        self.host = host
        self.port = port
        self.peers = set()
        self.bootstrap_host = bootstrap_host
        self.bootstrap_port = bootstrap_port

        self.load_peers()

    def load_peers(self):
        """Load known peers from a file, converting lists to tuples."""
        if os.path.exists(PEERS_FILE):
            with open(PEERS_FILE, "r") as f:
                peer_list = json.load(f)
                self.peers = {tuple(peer) for peer in peer_list}

    def save_peers(self):
        """Save known peers to a file."""
        with open(PEERS_FILE, "w") as f:
            json.dump(list(self.peers), f)

    async def handle_connection(self, reader, writer):
        """Handles incoming peer connections and peer discovery."""
        addr = writer.get_extra_info('peername')
        print(f"🔗 Connected with {addr}")

        self.peers.add(addr)
        self.save_peers()

        writer.write(json.dumps(list(self.peers)).encode())
        await writer.drain()

        try:
            while True:
                data = await reader.read(100)
                if not data:
                    break
                message = data.decode()
                print(f"📩 Received from {addr}: {message}")

                writer.write(f"✅ ACK: {message}".encode())
                await writer.drain()
        except asyncio.CancelledError:
            pass
        finally:
            print(f"❌ Connection closed: {addr}")
            self.peers.discard(addr)
            self.save_peers()
            writer.close()
            await writer.wait_closed()

    async def start_server(self):
        """Starts the server for incoming connections."""
        server = await asyncio.start_server(self.handle_connection, self.host, self.port)
        print(f"🚀 Node started on {self.host}:{self.port}")
        async with server:
            await server.serve_forever()

    async def connect_to_peer(self, peer_host, peer_port):
        """Connects to another peer."""
        try:
            reader, writer = await asyncio.open_connection(peer_host, peer_port)
            addr = writer.get_extra_info('peername')
            print(f"✅ Connected to peer {peer_host}:{peer_port}")

            self.peers.add((peer_host, peer_port))
            self.save_peers()

            data = await reader.read(4096)
            peer_list = json.loads(data.decode())

            for peer in peer_list:
                self.peers.add(tuple(peer))

            self.save_peers()
        except Exception as e:
            print(f"❌ Failed to connect to peer {peer_host}:{peer_port} - {e}")

    async def bootstrap_connect(self):
        """If the node is not a bootstrap node, connect to the bootstrap node."""
        if self.bootstrap_host and self.bootstrap_port:
            await self.connect_to_peer(self.bootstrap_host, self.bootstrap_port)

    async def start(self):
        """Start the peer-to-peer server in the background."""
        loop = asyncio.get_running_loop()
        loop.create_task(self.start_server())

node = Node(port=5000)

@app.get("/")
def root():
    return {"message": "Node is running!"}

@app.get("/peers")
def get_peers():
    return {"peers": list(node.peers)}

@app.post("/connect")
async def connect_peer(peer_host: str, peer_port: int):
    await node.connect_to_peer(peer_host, peer_port)
    return {"message": f"Attempting to connect to {peer_host}:{peer_port}"}

@app.on_event("startup")
async def startup_event():
    await node.start()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
