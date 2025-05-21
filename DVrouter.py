####################################################
# DVrouter.py
# Name: Lương Quang Huy
# HUID: 23021572
#####################################################

from router import Router
from packet import Packet
import json

class DVrouter(Router):
    def __init__(self, addr, heartbeat_time):
        super().__init__(addr)
        self.heartbeat_time = heartbeat_time
        self.last_broadcast = 0
        self.MAX_COST = 16

        # Maps port -> link cost
        self.link_costs = {}

        # Maps port -> neighbor address
        self.port_to_neighbor = {}

        # Maps neighbor address -> their last known distance vector
        self.neighbor_vectors = {}

        # This router's distance vector and forwarding table
        self.distance_vector = {self.addr: 0}
        self.forwarding_table = {}

    def send_distance_vector(self):
        """Send this router's distance vector to all neighbors."""
        payload = json.dumps(self.distance_vector)
        for port in self.link_costs:
            packet = Packet(kind=Packet.ROUTING, src_addr=self.addr, dst_addr=None, content=payload)
            self.send(port, packet)

    def update_routing(self):
        """Recalculate distance vector and forwarding table."""
        updated = False
        new_dv = {self.addr: 0}
        new_ft = {}

        # Direct neighbors
        for port, cost in self.link_costs.items():
            neighbor = self.port_to_neighbor[port]
            if cost < new_dv.get(neighbor, self.MAX_COST + 1):
                new_dv[neighbor] = cost
                new_ft[neighbor] = port

        # Indirect paths via neighbors' vectors
        for port, cost in self.link_costs.items():
            neighbor = self.port_to_neighbor[port]
            if neighbor not in self.neighbor_vectors:
                continue
            for dest, neighbor_cost in self.neighbor_vectors[neighbor].items():
                if dest == self.addr:
                    continue
                total_cost = min(self.MAX_COST, cost + neighbor_cost)
                if total_cost < new_dv.get(dest, self.MAX_COST + 1):
                    new_dv[dest] = total_cost
                    new_ft[dest] = port

        if new_dv != self.distance_vector or new_ft != self.forwarding_table:
            self.distance_vector = new_dv
            self.forwarding_table = new_ft
            updated = True

        return updated

    def handle_packet(self, port, packet):
        if packet.kind == Packet.ROUTING:
            try:
                vector = json.loads(packet.content)
            except json.JSONDecodeError:
                return
            self.neighbor_vectors[packet.src_addr] = vector
            if self.update_routing():
                self.send_distance_vector()
        else:
            # Data packet (traceroute or real traffic)
            dst = packet.dst_addr
            if dst in self.forwarding_table:
                out_port = self.forwarding_table[dst]
                self.send(out_port, packet)

    def handle_new_link(self, port, endpoint, cost):
        self.link_costs[port] = cost
        self.port_to_neighbor[port] = endpoint
        if cost < self.distance_vector.get(endpoint, self.MAX_COST + 1):
            self.distance_vector[endpoint] = cost
            self.forwarding_table[endpoint] = port
        if self.update_routing():
            self.send_distance_vector()

    def handle_remove_link(self, port):
        if port in self.link_costs:
            neighbor = self.port_to_neighbor.pop(port, None)
            self.link_costs.pop(port)
            if neighbor:
                self.neighbor_vectors.pop(neighbor, None)
            if self.update_routing():
                self.send_distance_vector()

    def handle_time(self, time_ms):
        if time_ms - self.last_broadcast >= self.heartbeat_time:
            self.last_broadcast = time_ms
            self.send_distance_vector()

    def __repr__(self):
        return f"DVrouter(addr={self.addr}, dv={self.distance_vector})"
