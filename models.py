import re
import paramiko
from ipaddress import IPv4Address


class RouteServer:
    server = None
    service = None
    ip_version = None
    _dump = None
    _peers = []

    def __init__(self, server=None, service=None, ip_version=None):
        self.server = server
        self.service = service
        self.ip_version = ip_version or 4
        self._dump = []
        self._peers = []

    def _fill_dump(self):

        if not self.service:
            return None
        if not self.server:
            return None

        bird_command = "show protocols all"
        server_command = "echo '%s' | sudo birdc -s /var/run/bird%s.%s.ctl" % (bird_command, self.ip_version, self.service)

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.connect(self.server, username='vlad')
        stdin, stdout, stderr = client.exec_command(server_command)

        data = stdout.read()
        self._dump = None
        self._dump = data.decode("utf-8")

    def _parse_dump(self):
        peers = []
        peer = list()

        for l in self._dump.splitlines():
            if l[0:5] == "peer_":
                if peer:
                    peers.append(peer)
                    peer = []
                peer.append(l)
            else:
                if peer:
                    peer.append(l)

        if peer:
            peers.append(peer)

        return peers

    def _fill_peers(self):
        self._fill_dump()
        for peer_dump in self._parse_dump():
            peer = Peer(peer_dump)
            self._peers.append(peer)

    def peers(self):
        self._fill_peers()
        return self._peers


class Peer:
    """Dump example:
    peer_12217 BGP      master   up     2018-02-07 21:40:48  Established
  Description:    tushino
  Preference:     100
  Input filter:   (unnamed)
  Output filter:  (unnamed)
  Import limit:   1000
    Action:       restart
  Routes:         3 imported, 0 filtered, 687190 exported, 3 preferred
  Route change stats:     received   rejected   filtered    ignored   accepted
    Import updates:              3          0          0          0          3
    Import withdraws:            0          0        ---          0          0
    Export updates:         938753          3     108701        ---     830049
    Export withdraws:         7983        ---        ---        ---       6257
  BGP state:          Established
    Neighbor address: 85.112.122.17
    Neighbor AS:      41349
    Neighbor ID:      89.250.0.254
    Neighbor caps:    refresh restart-aware AS4
    Session:          external route-server AS4
    Source address:   85.112.122.1
    Route limit:      3/1000
    Hold timer:       10/15
    Keepalive timer:  2/5
    """

    _dump = None

    peer_id = None
    state = None
    bgp_state = None
    bgp_state_details = None
    last_event_time = None
    description = None
    preference = None
    import_limit = None
    imported_routes = None
    filtered_routes = None
    exported_routes = None
    preferred_routes = None
    neighbor_address = None
    neighbor_as = None
    source_address = None
    route_limit = None
    hold_timer = None
    keepalive_timer = None
    value = None

    def __init__(self, dump):
        self._dump = dump
        self._parse_dump()

    def _parse_dump(self):
        """
        Fills all peer information
        """
        self.peer_id = self._parse_peer_id()
        self.state = self._parse_state()
        self.bgp_state = self._parse_bgp_state()
        self.bgp_state_details = self._parse_bgp_state_details()
        self.last_event_time = self._parse_last_event_time()
        self.description = self._parse_description()
        self.preference = self._parse_preference()
        self.import_limit = self._parse_import_limit()

        self.imported_routes = self._parse_imported_routes()
        self.filtered_routes = self._parse_filtered_routes()
        self.exported_routes = self._parse_exported_routes()
        self.preferred_routes = self._parse_preferred_routes()

        self.neighbor_address = self._parse_neighbor_address()
        self.neighbor_as = self._parse_neighbor_as()
        self.source_address = self._parse_source_address()
        self.route_limit = self._parse_route_limit()
        self.hold_timer = self._parse_hold_timer()
        self.keepalive_timer = self._parse_keepalive_timer()

        try:
            ip_address = IPv4Address(self.neighbor_address)
            self.value = int(ip_address)
        except:
            self.value = 0

    def _parse_peer_id(self):
        l = self._dump[0]
        parts = l.split()
        return parts[0][5:]

    def _parse_bgp_state_details(self):
        """
        peer_12217 BGP      master   up     2018-02-07 21:40:48  Established
        """
        l = self._dump[0]
        parts = l.split()
        state_details = " ".join(parts[6:])
        return state_details

    def _parse_last_event_time(self):
        """
        peer_12217 BGP      master   up     2018-02-07 21:40:48  Established
        """
        l = self._dump[0]
        parts = l.split()
        last_event_time = " ".join(parts[4:6])
        return last_event_time

    def _parse_state(self):
        """
        peer_12217 BGP      master   up     2018-02-07 21:40:48  Established
        """
        l = self._dump[0]
        parts = l.split()
        state = parts[3]

        if state == "start":
            state = "down"

        return state

    def _parse_bgp_state(self):
        return self._extract_word("BGP state", 2)

    def _parse_description(self):
        return self._extract_word("Description", 1)

    def _parse_preference(self):
        return self._extract_word("Preference", 1)

    def _parse_import_limit(self):
        return self._extract_word("Import limit", 2)

    def _parse_imported_routes(self):
        return self._extract_word("Routes", 1)

    def _parse_filtered_routes(self):
        return self._extract_word("Routes", 3)

    def _parse_exported_routes(self):
        return self._extract_word("Routes", 5)

    def _parse_preferred_routes(self):
        return self._extract_word("Routes", 7)

    def _parse_neighbor_address(self):
        return self._extract_word("Neighbor address", 2)

    def _parse_neighbor_as(self):
        return self._extract_word("Neighbor AS", 2)

    def _parse_source_address(self):
        return self._extract_word("Source address", 2)

    def _parse_route_limit(self):
        return self._extract_word("Route limit", 2)

    def _parse_hold_timer(self):
        return self._extract_word("Hold timer", 2)

    def _parse_keepalive_timer(self):
        return self._extract_word("Keepalive timer", 2)

    def _extract_word(self, pattern, position):
        word = None
        for l in self._dump:
            if pattern in l:
                parts = l.split()
                word = parts[position]
        return word


class Prefix:
    """Prefix example:
    BIRD 1.4.5 ready.
    [?1034hbird> show route all 185.174.194.0/24
    bird>
    [K185.174.194.0/24   via 85.112.122.101 on br5 [peer_122101 2018-02-08 08:19:20] * (100) [AS60764i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 60764
        BGP.next_hop: 85.112.122.101
        BGP.local_pref: 130
        BGP.community: (25478,1000) (25478,4016) (0,28709) (0,47541) (0,47542) (25478,19992) (50384,5013) (50384,5073) (50384,5513) (50384,5523) (50384,5533) (50384,5573) (50384,5583) (50384,5593)
                       via 85.112.122.13 on br5 [peer_12213 2018-02-08 08:19:35] (100) [AS60764i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 20764 60764
        BGP.next_hop: 85.112.122.13
        BGP.med: 290
        BGP.local_pref: 100
        BGP.community: (25478,3002) (25478,3000) (20764,3002) (20764,3011) (20764,3021)
                       via 85.112.122.20 on br5 [peer_12220 2018-01-30 12:51:37] (100) [AS60764i]
        Type: BGP unicast univ
        BGP.origin: IGP
        BGP.as_path: 20764 60764
        BGP.next_hop: 85.112.122.20
        BGP.med: 295
        BGP.local_pref: 100
        BGP.community: (25478,3002) (25478,3000) (20764,3002) (20764,3011) (20764,3021)
    bird>[K"""

    _dump = None
    _next_hops = []

    def __init__(self):
        self._fill_dump()
        for dump in self._parse_dump():
            next_hop = NextHop(dump)

    def _fill_dump(self):
        with open("prefix_output.txt") as f:
            self._dump = f.read()

    def _fill_next_hops(self):
        for dump in self._parse_dump():
            next_hop = NextHop(dump)
            self._next_hops.append(next_hop)

    def _parse_dump(self):
        next_hops = []
        next_hop = list()

        next_prefix_pattern = re.compile("via [0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3} on")

        for l in self._dump.splitlines():
            if next_prefix_pattern.search(l):
                if next_hop:
                    next_hops.append(next_hop)
                    next_hop = []
                next_hop.append(l)
            else:
                if next_hop:
                    next_hop.append(l)

        if next_hop:
            next_hops.append(next_hop)

        return next_hops

    def next_hops(self):
        self._fill_next_hops()
        return self._next_hops


        # def _extract_word_re(self, string_pattern, value_pattern, data):
        #     """
        #     Returns certain value from matching string or None
        #     :param string_pattern: re pattern to identify if this is the needed string
        #     :param value_pattern: re pattern that mathes the needed value exactly
        #     :return: certain value from matching string or None
        #     """
        #
        #     string_pattern = re.compile(string_pattern)
        #     value_pattern = re.compile(value_pattern)
        #
        #     if string_pattern.search(data):
        #         matching = value_pattern.search(data)
        #         return matching.group()
        #
        #     return None


class NextHop:
    """Example
                       via 85.112.122.20 on br5 [peer_12220 2018-01-30 12:51:37] (100) [AS60764i]
    Type: BGP unicast univ
    BGP.origin: IGP
    BGP.as_path: 20764 60764
    BGP.next_hop: 85.112.122.20
    BGP.med: 295
    BGP.local_pref: 100
    BGP.community: (25478,3002) (25478,3000) (20764,3002) (20764,3011) (20764,3021)
    """

    _dump = None

    origin = None
    as_path = None
    next_hop = None
    med = None
    local_pref = None
    community = []

    def __init__(self, dump):
        self._dump = dump
        self._parse_dump()

    def _parse_dump(self):
        self.origin = self._parse_origin()
        self.as_path = self._parse_as_path()
        self.next_hop = self._parse_next_hop()
        self.med = self._parse_med()
        self.local_pref = self._parse_local_pref()
        self.community = self._parse_community()

    def _parse_origin(self):
        return self._extract_word("BGP.origin", 1)

    def _parse_as_path(self):
        return "n/a"

    def _parse_next_hop(self):
        return self._extract_word("BGP.next_hop", 1)

    def _parse_med(self):
        return self._extract_word("BGP.med", 1)

    def _parse_local_pref(self):
        return self._extract_word("BGP.local_pref", 1)

    def _parse_community(self):
        return "n/a"

    def _extract_word(self, pattern, position):
        word = None
        for l in self._dump:
            if pattern in l:
                parts = l.split()
                word = parts[position]
        return word

    def __repr__(self):
        return self.next_hop
