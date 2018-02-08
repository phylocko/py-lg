class RouteServer:
    _dump = None

    _peers = []

    def __init__(self):
        self._fill_dump()

    def _fill_dump(self):
        with open("bird6_output.txt") as f:
            self._dump = f.read()

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

        return peers

    def _fill_peers(self):
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

