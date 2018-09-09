import re
import paramiko
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address


class RouteServer:
    def __init__(self, server=None, service=None, ip_version=None):
        self._session = None
        self.server = None
        self.service = None
        self.ip_version = None

        self.server = server
        self.service = service
        self.ip_version = ip_version or 4
        self.connect()

    def connect(self):
        session = paramiko.SSHClient()
        session.load_system_host_keys()
        session.connect(self.server, username='vlad')
        self._session = session

    def _disconnect(self):
        self._session.close()

    def _cmd(self, command):
        stdin, stdout, stderr = self._session.exec_command(command)

        bird_dump_bytes = stdout.read()
        return bird_dump_bytes.decode("utf-8")

    def _parse__show_protocols(self, bird_dump):
        peers = []
        peer = list()

        for l in bird_dump.splitlines():
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

    def _parse__show_route_peer(self, bird_dump):
        routes = []
        route = []

        for l in bird_dump.splitlines():
            if 'via' in l:
                if route:
                    routes.append(route)
                    route = []
                route.append(l)
            else:
                if route:
                    route.append(l)

        if route:
            routes.append(route)

        return routes

    def route(self, prefix=None, address=None):
        if prefix or address:
            if prefix:
                bird_command = "show route %s all" % prefix
            else:
                print('address: %s' % address)
                bird_command = "show route for %s all" % address
        else:
            return []

        server_command = "echo '%s' | sudo birdc -s /var/run/bird%s.%s.ctl" % (bird_command, self.ip_version, self.service)
        bird_dump = self._cmd(server_command)

        prefixes = []

        route = Route(dump=bird_dump, routes=prefixes)
        for prefix_dump in self._parse__show_route_peer(bird_dump):
            prefix = Prefix(prefix_dump, self.ip_version)
            prefix.destination = route.prefix
            prefixes.append(prefix)
        return route

    def peers(self):
        bird_command = "show protocols all"
        server_command = "echo '%s' | sudo birdc -s /var/run/bird%s.%s.ctl" % (bird_command, self.ip_version, self.service)
        bird_dump = self._cmd(server_command)

        peers = []
        for peer_dump in self._parse__show_protocols(bird_dump):
            peer = Peer()
            peer.fill_data(peer_dump, self.ip_version)
            peers.append(peer)

        return peers

    def peer(self, peer_id):
        bird_command = "show protocols all %s" % peer_id
        server_command = "echo '%s' | sudo birdc -s /var/run/bird%s.%s.ctl" % (bird_command, self.ip_version, self.service)
        bird_dump = self._cmd(server_command)
        peers = []
        for peer_dump in self._parse__show_protocols(bird_dump):
            peer = Peer()
            peer.fill_data(peer_dump, self.ip_version)
            peers.append(peer)

        return peers[0]

    def prefixes(self, peer_id, rejected):
        bird_command = "show route protocol %s all" % peer_id
        if rejected == 'filtered':
            bird_command = "show route protocol %s filtered all" % peer_id

        server_command = "echo '%s' | sudo birdc -s /var/run/bird%s.%s.ctl | head -3000" % (bird_command, self.ip_version, self.service)
        bird_dump = self._cmd(server_command)

        prefixes = []
        for prefix_dump in self._parse__show_route_peer(bird_dump):
            if len(prefixes) < 301:
                prefix = Prefix(prefix_dump, self.ip_version)
                if rejected:
                    prefix.filtered = True
                prefixes.append(prefix)
        return prefixes


class Prefix:
    def __init__(self, dump, ip_version):
        self.prefix = None
        self.next_hop = None
        self.via = None
        self.local_pref = None
        self.as_path = []
        self.communities = []
        self.preferred = False
        self.origin = None
        self.time = None
        self.ip_version = int(ip_version)
        self._dump = dump
        self._parse_dump()
        self.filtered = False
        self.destination = None

    def _parse_dump(self):
        """
        Fills all route information
        """
        self.prefix = self._extract_word('via', 0)
        self.origin = self._extract_word('BGP.origin', 1)
        self.next_hop = self._extract_word('BGP.next_hop', 1)
        self.local_pref = self._extract_word('BGP.local_pref', 1)
        for c in self._parse_communities():
            self.communities.append(c)
        self.as_path = self._parse_as_path()
        self.preferred = self._parse_preferred()

    def _parse_preferred(self):
        for l in self._dump:
            if 'via' in l and '*' in l:
                return True
        return False

    def _parse_communities(self):
        communities = []
        pattern = re.compile('(\(\d{1,8}\,\d{1,8}\))')
        for l in self._dump:
            if 'BGP.community' in l:
                groups = pattern.findall(l)
                for g in groups:
                    community = g.replace('(', '')
                    community = community.replace(')', '')
                    # community = community.replace(',', ':')
                    communities.append(community)
        return communities

    def _parse_as_path(self):
        as_path = []
        for l in self._dump:
            if 'BGP.as_path' in l:
                pattern = re.compile('(\d{2,10})')
                groups = pattern.findall(l)
                as_path.extend([x for x in groups])
        return as_path

    def _extract_word(self, pattern, position):
        word = None
        for l in self._dump:
            if pattern in l:
                parts = l.split()
                word = parts[position]
        return word


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

    ip_version = 0
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

    def fill_data(self, dump, ip_version):
        self.ip_version = int(ip_version)
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

        self.imported_routes = int(self._parse_imported_routes())
        self.filtered_routes = int(self._parse_filtered_routes())
        self.exported_routes = int(self._parse_exported_routes())
        self.preferred_routes = int(self._parse_preferred_routes())

        self.neighbor_address = self._parse_neighbor_address()
        self.neighbor_as = self._parse_neighbor_as()
        self.source_address = self._parse_source_address()
        self.route_limit = self._parse_route_limit()
        self.hold_timer = self._parse_hold_timer()
        self.keepalive_timer = self._parse_keepalive_timer()

        if self.ip_version == 4:
            try:
                ip_address = IPv4Address(self.neighbor_address)
                self.value = int(ip_address)
            except:
                self.value = 0

        elif self.ip_version == 6:
            try:
                ip_address = IPv6Address(self.neighbor_address)
                self.value = int(ip_address)
            except:
                self.value = 0

        else:
            self.value = 0

    def _parse_peer_id(self):
        l = self._dump[0]
        parts = l.split()
        return parts[0]

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
        filtered_pattern = re.compile("[0-9]{1,10} imported")
        for l in self._dump:
            result = filtered_pattern.search(l)
            if result:
                parts = result.group().split()
                return parts[0]

    def _parse_filtered_routes(self):
        filtered_pattern = re.compile("[0-9]{1,10} filtered")
        for l in self._dump:
            result = filtered_pattern.search(l)
            if result:
                parts = result.group().split()
                return parts[0]

    def _parse_exported_routes(self):
        filtered_pattern = re.compile("[0-9]{1,10} exported")
        for l in self._dump:
            result = filtered_pattern.search(l)
            if result:
                parts = result.group().split()
                return parts[0]

    def _parse_preferred_routes(self):
        filtered_pattern = re.compile("[0-9]{1,10} preferred")
        for l in self._dump:
            result = filtered_pattern.search(l)
            if result:
                parts = result.group().split()
                return parts[0]

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

    def persistency(self):
        last_event_time = datetime.strptime(self.last_event_time, "%Y-%m-%d %H:%M:%S")
        difference = datetime.now() - last_event_time

        if difference.days < 1:
            total_minutes = difference.seconds / 60
            if total_minutes < 60:
                return "{:10.0f} min".format(total_minutes)
            else:
                return "{:10.0f} hours".format(total_minutes / 60)
        else:
            return "%s days" % difference.days


class Route:
    def __init__(self, dump, routes):
        self.prefix = None
        for l in dump.splitlines():
            pattern = re.compile('^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\/[0-9]{1,3}')
            groups = pattern.findall(l)
            if groups:
                self.prefix = groups[0]
        self.routes = routes
