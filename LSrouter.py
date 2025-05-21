####################################################
# LSrouter.py
# Name: 
# HUID:
#####################################################

import json
import heapq
from router import Router
from packet import Packet

class LSrouter(Router):
    """Link state routing protocol implementation."""

    def __init__(self, addr, heartbeat_time):
        super().__init__(addr)       # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        # sequence number for our own LSPs
        self.seq_num = 0
        # port -> (neighbor_addr, cost)
        self.neighbors = {}
        # router_addr -> (seq_num, {neighbor_addr: cost})
        self.link_state_db = {}
        # forwarding table: dest_addr -> out_port
        self.forwarding = {}

        # broadcast initial link state
        self._update_own_link_state()

    def _update_own_link_state(self):
        """Generate and flood our own LSP to all neighbors."""
        self.seq_num += 1
        links = {nbr: cost for (_, (nbr, cost)) in self.neighbors.items()}
        self.link_state_db[self.addr] = (self.seq_num, links)
        content = json.dumps({"router": self.addr, "seq": self.seq_num, "links": links})
        for port in self.neighbors:
            pkt = Packet(Packet.ROUTING, self.addr, None)
            pkt.content = content
            self.send(port, pkt)

    def _recompute_forwarding(self):
        """Recompute shortest paths (Dijkstra) and rebuild forwarding table."""
        # Build graph from LSDB
        graph = {r: links.copy() for r, (_, links) in self.link_state_db.items()}
        # Collect any neighbor nodes not yet in graph
        extras = set()
        for links in graph.values():
            for nbr in links:
                if nbr not in graph:
                    extras.add(nbr)
        # Add them with no outgoing edges
        for nbr in extras:
            graph[nbr] = {}

        # Dijkstra
        dist = {node: float('inf') for node in graph}
        prev = {}
        dist[self.addr] = 0
        heap = [(0, self.addr)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for v, cost in graph[u].items():
                nd = d + cost
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))

        # Build new forwarding table
        new_fwd = {}
        for dest in graph:
            if dest == self.addr or dest not in prev:
                continue
            cur = dest
            while prev[cur] != self.addr:
                cur = prev[cur]
            for port, (nbr, _) in self.neighbors.items():
                if nbr == cur:
                    new_fwd[dest] = port
                    break

        self.forwarding = new_fwd

    def handle_packet(self, port, packet):
        """Process incoming traceroute or LSP packet."""
        if packet.is_traceroute:
            out = self.forwarding.get(packet.dst_addr)
            if out is not None:
                self.send(out, packet)
        else:
            data = json.loads(packet.content)
            origin = data["router"]; seq = data["seq"]; links = data["links"]
            old = self.link_state_db.get(origin)
            if old is None or seq > old[0]:
                self.link_state_db[origin] = (seq, links)
                for p in self.neighbors:
                    if p != port:
                        fwd = Packet(Packet.ROUTING, self.addr, None)
                        fwd.content = packet.content
                        self.send(p, fwd)
                self._recompute_forwarding()

    def handle_new_link(self, port, endpoint, cost):
        """Handle a new link coming up."""
        self.neighbors[port] = (endpoint, cost)
        self._update_own_link_state()

    def handle_remove_link(self, port):
        """Handle a link going down."""
        if port in self.neighbors:
            del self.neighbors[port]
        self._update_own_link_state()

    def handle_time(self, time_ms):
        """Periodic heartbeat: rebroadcast our LSP."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._update_own_link_state()

    def __repr__(self):
        return f"LSrouter(addr={self.addr}, fwd={self.forwarding})"
