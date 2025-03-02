import asyncio
import json
import os

PEERS_FILE = "peers.json"  # Stores known peers

class Node:
    def __init__(self, host="127.0.0.1", port=5000, bootstrap_host=None, bootstrap_port=None):
        self.host = host
        self.port = port
        self.peers = set()  # Stores active peer connections
        self.bootstrap_host = bootstrap_host
        self.bootstrap_port = bootstrap_port

        # Load saved peers from file
        self.load_peers()

    def load_peers(self):
        """Load known peers from a file, converting lists to tuples."""
        if os.path.exists(PEERS_FILE):
            with open(PEERS_FILE, "r") as f:
                peer_list = json.load(f)  # Load as list
                self.peers = {tuple(peer) for peer in peer_list}  # Convert to set of tuples



    def save_peers(self):
        """Save known peers to a file."""
        with open(PEERS_FILE, "w") as f:
            json.dump(list(self.peers), f)

    async def handle_connection(self, reader, writer):
        """Handles incoming peer connections and peer discovery."""
        addr = writer.get_extra_info('peername')
        print(f"🔗 Connected with {addr}")

        self.peers.add(addr)  # Save new peer
        self.save_peers()

        # Send list of known peers to new node
        writer.write(json.dumps(list(self.peers)).encode())
        await writer.drain()

        try:
            while True:
                data = await reader.read(100)
                if not data:
                    break  # Connection closed
                message = data.decode()
                print(f"📩 Received from {addr}: {message}")

                # Echo back
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

            # Receive list of known peers
            # Receive list of known peers
            data = await reader.read(4096)
            peer_list = json.loads(data.decode())

            #   Convert peer list from list -> tuple and add to the set
            for peer in peer_list:
                self.peers.add(tuple(peer))  # Ensure we store peers as (host, port) tuples

            self.save_peers()  # Save updated peers list


            while True:
                message = input(f"Type message for {peer_host}:{peer_port} > ")
                writer.write(message.encode())
                await writer.drain()

                data = await reader.read(100)
                print(f"📩 Response from peer: {data.decode()}")

        except Exception as e:
            print(f"❌ Failed to connect to peer {peer_host}:{peer_port} - {e}")

    async def bootstrap_connect(self):
        """If the node is not a bootstrap node, connect to the bootstrap node."""
        if self.bootstrap_host and self.bootstrap_port:
            await self.connect_to_peer(self.bootstrap_host, self.bootstrap_port)

    async def start(self):
        """Start server and connect to bootstrap node if available."""
        server_task = asyncio.create_task(self.start_server())

        # If bootstrap node is provided, connect to it
        if self.bootstrap_host and self.bootstrap_port:
            await asyncio.sleep(1)  # Give server time to start
            await self.bootstrap_connect()

        await server_task  # Keep server running

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python node.py <port> [bootstrap_host bootstrap_port]")
        sys.exit(1)

    port = int(sys.argv[1])
    bootstrap_host = sys.argv[2] if len(sys.argv) > 2 else None
    bootstrap_port = int(sys.argv[3]) if len(sys.argv) > 3 else None

    node = Node(port=port, bootstrap_host=bootstrap_host, bootstrap_port=bootstrap_port)
    asyncio.run(node.start())
