####################################################
# DVrouter.py
# Name: <Your Name>
# HUID: <Your HUID>
#####################################################

import json
from router import Router
from packet import Packet

class DVrouter(Router):
    """Distance vector routing protocol implementation."""

    def __init__(self, addr, heartbeat_time):
        # Khởi tạo base class (chỉ nhận addr)
        super().__init__(addr)
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        # port -> cost đến neighbor
        self.neighbor_costs = {}
        # port -> neighbor address
        self.neighbor_addrs = {}
        # neighbor address -> last advertised distance vector
        self.neighbor_vectors = {}

        # distance vector của chính mình: dest_addr -> cost
        self.distances = {self.addr: 0}
        # forwarding table: dest_addr -> out_port
        self.forwarding = {}

        # broadcast vector khởi tạo
        self._broadcast_vector()

    def _broadcast_vector(self):
        """Gửi distance vector hiện tại đến tất cả neighbor."""
        payload = json.dumps({"vector": self.distances})
        for port in self.neighbor_addrs:
            pkt = Packet()
            pkt.kind = Packet.ROUTING
            pkt.src_addr = self.addr
            pkt.dst_addr = None
            pkt.content = payload
            self.send(port, pkt)

    def _recompute(self):
        """Bellman–Ford: tính lại distances & forwarding table."""
        # tập mọi đích do neighbors quảng bá
        all_dests = set()
        for vec in self.neighbor_vectors.values():
            all_dests.update(vec.keys())
        all_dests.discard(self.addr)

        new_dist = {self.addr: 0}
        for dest in all_dests:
            best = float('inf')
            for port, nei_addr in self.neighbor_addrs.items():
                cost_to_nei = self.neighbor_costs[port]
                nei_vec = self.neighbor_vectors.get(nei_addr, {})
                c = nei_vec.get(dest, float('inf'))
                best = min(best, cost_to_nei + c)
            if best < float('inf'):
                new_dist[dest] = best

        # xây forwarding mới
        new_fwd = {}
        for dest, dist in new_dist.items():
            if dest == self.addr:
                continue
            for port, nei_addr in self.neighbor_addrs.items():
                cost_to_nei = self.neighbor_costs[port]
                nei_vec = self.neighbor_vectors.get(nei_addr, {})
                if nei_vec.get(dest, float('inf')) + cost_to_nei == dist:
                    new_fwd[dest] = port
                    break

        changed = (new_dist != self.distances)
        if changed:
            self.distances = new_dist
            self.forwarding = new_fwd
        return changed

    def handle_packet(self, port, packet):
        """Xử lý gói đến: traceroute hoặc routing."""
        if packet.is_traceroute:
            # data packet: forward theo bảng
            out = self.forwarding.get(packet.dst_addr)
            if out is not None:
                self.send(out, packet)
        else:
            # routing packet: neighbor gửi distance vector
            data = json.loads(packet.content)
            vec = data.get("vector", {})
            src = packet.src_addr
            if self.neighbor_vectors.get(src) != vec:
                self.neighbor_vectors[src] = vec
                if self._recompute():
                    self._broadcast_vector()

    def handle_new_link(self, port, endpoint, cost):
        """Khi có link mới up."""
        self.neighbor_addrs[port] = endpoint
        self.neighbor_costs[port] = cost
        # khởi vector neighbor rỗng cho đến khi nhận được
        self.neighbor_vectors.setdefault(endpoint, {})
        if self._recompute():
            self._broadcast_vector()

    def handle_remove_link(self, port):
        """Khi link down."""
        if port in self.neighbor_addrs:
            nei = self.neighbor_addrs.pop(port)
            self.neighbor_costs.pop(port, None)
            self.neighbor_vectors.pop(nei, None)
        if self._recompute():
            self._broadcast_vector()

    def handle_time(self, time_ms):
        """Heartbeat: gửi lại vector dù không thay đổi."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast_vector()

    def __repr__(self):
        return (f"DVrouter(addr={self.addr}, "
                f"dist={self.distances}, fwd={self.forwarding})")
