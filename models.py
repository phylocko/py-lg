# Copyright 2019 Vladislav Pavkin

import re
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, ip_address
from socket import gaierror

import paramiko
from paramiko.ssh_exception import SSHException

import config


class ParsingError(Exception):
    pass


class RouteServer:
    def __init__(self, server=None):
        self._session = None
        self.server = server
        self.connect()

    def connect(self):
        session = paramiko.SSHClient()
        session.load_system_host_keys()
        try:
            session.connect(self.server, username=config.SSH_USERNAME, password=config.SSH_PASSWORD)
        except (gaierror, SSHException) as e:
            pass
        else:
            self._session = session

    def _disconnect(self):
        self._session.close()

    def _cmd(self, command):
        try:
            stdin, stdout, stderr = self._session.exec_command(command, timeout=5)
        except (TimeoutError, SSHException):
            self.connect()
            self._cmd(command)
        else:
            bird_dump_bytes = stdout.read()
            return bird_dump_bytes.decode("utf-8")

    def _parse__show_protocols(self, bird_dump, ip_version=4):
        peers_lines = []
        peer_lines = []

        for l in bird_dump.splitlines():
            if l.startswith('peer'):
                if peer_lines:
                    peers_lines.append(peer_lines)
                    peer_lines = []
                peer_lines.append(l)
            else:
                if peer_lines and peer_lines[0].startswith('peer%s_' % ip_version):
                    peer_lines.append(l)

        if peer_lines and peer_lines[0].startswith('peer%s_' % ip_version):
            peers_lines.append(peer_lines)

        return peers_lines

    @staticmethod
    def _parse__show_route_peer(bird_dump):
        routes = []
        route = []

        ip_pattern = re.compile(r'^\d{1,4}\.\d{1,4}\.\d{1,4}\.\d{1,4}\/\d{1,2}')

        for l in bird_dump.splitlines():
            # if 'via' in l:
            if ip_pattern.match(l):
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

    def route(self, destination=None, service=None, ip_version=None):
        if self._session is None:
            return

        if '/' in destination:
            bird_command = "show route %s all" % destination
        else:
            bird_command = "show route for %s all" % destination

        server_command = '/var/run/bird.%s.ctl %s' % (service, bird_command)
        bird_dump = self._cmd(server_command)

        prefixes = []

        route = Route(dump=bird_dump, routes=prefixes)
        for prefix_dump in self._parse__show_route_peer(bird_dump):
            prefix = Prefix(prefix_dump, ip_version)
            prefix.prefix = route.prefix  # we can't parse it from the dump because of 'via'
            prefixes.append(prefix)
        return route

    def peers(self, service='wix', ip_version=4):
        if self._session is None:
            return []

        bird_command = 'show protocols all'
        server_command = '/var/run/bird.%s.ctl %s' % (
            service, bird_command)
        bird_dump = self._cmd(server_command)

        peers = []
        protocols_dump = self._parse__show_protocols(bird_dump, ip_version)
        for peer_dump in protocols_dump:
            try:
                peer = Peer(peer_dump, ip_version)
            except ParsingError:
                continue
            else:
                peers.append(peer)
        return peers

    def peer(self, peer_id, service=None, ip_version=4):
        if self._session is None:
            return

        peer_id = peer_id.replace('peer_', 'peer%s_' % ip_version)

        bird_command = 'show protocols all %s' % peer_id
        server_command = '/var/run/bird.%s.ctl %s' % (service, bird_command)
        bird_dump = self._cmd(server_command)

        peers = []
        parsed_protocols = self._parse__show_protocols(bird_dump)
        for peer_dump in parsed_protocols:
            try:
                peer = Peer(peer_dump, ip_version)
            except ParsingError:
                pass
            else:
                peers.append(peer)

        if peers:
            return peers[0]
        return None

    def prefixes(self, peer_id, rejected, service=None, ip_version=4):
        if self._session is None:
            return []

        peer = self.peer(peer_id, service=service, ip_version=ip_version)

        if not rejected and peer.imported_routes > 300:
            return peer, []

        if rejected and peer.filtered_routes > 300:
            return peer, []

        peer_id = peer_id.replace('peer_', 'peer%s_' % ip_version)
        bird_command = 'show route protocol %s all' % peer_id
        if rejected:
            bird_command = 'show route protocol %s filtered all' % peer_id

        server_command = '/var/run/bird.%s.ctl %s' % (service, bird_command)

        bird_dump = self._cmd(server_command)

        prefixes = []
        for prefix_dump in self._parse__show_route_peer(bird_dump):
            if len(prefixes) < 301:
                prefix = Prefix(prefix_dump, ip_version)
                if rejected:
                    prefix.filtered = True
                prefixes.append(prefix)
        return peer, prefixes


class Prefix:
    def __init__(self, dump, ip_version):
        self.prefix = None
        self.next_hop = None
        self.next_hop_netname = None
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

    def _parse_dump(self):
        """
        Fills all route information
        """

        self.prefix = self._extract_by_re(r'^\d{1,4}\.\d{1,4}\.\d{1,4}\.\d{1,4}\/\d{1,2}', 0)
        self.origin = self._extract_word('BGP.origin', 1)
        self.next_hop = self._extract_word('BGP.next_hop', 1)
        self.local_pref = self._extract_word('BGP.local_pref', 1)
        self.communities = self._parse_communities()
        self.as_path = self._parse_as_path()
        self.preferred = self._parse_preferred()

    def _parse_preferred(self):
        for l in self._dump:
            if 'unicast' in l and '*' in l:  # that's wired, better use re
                return True
        return False

    def _parse_communities(self):
        community_values = []
        pattern = re.compile('(\(\d{1,8}\,\d{1,8}\))')
        for l in self._dump:
            if 'BGP.community' in l:
                groups = pattern.findall(l)
                for g in groups:
                    community_value = g.replace('(', '')
                    community_value = community_value.replace(')', '')
                    community_values.append(community_value)

        communities = [Community(x) for x in community_values]
        communities = sorted(communities, key=lambda x: x.asn, reverse=True)
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

    def _extract_by_re(self, pattern, position):
        pattern = re.compile(pattern)
        word = None
        for l in self._dump:
            if pattern.match(l):
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

    ip_version = None
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

    def __init__(self, dump, ip_version):

        if ip_version not in [4, 6]:
            raise ValueError('No IP version given')
        self.fill_data(dump, ip_version)

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

        self.imported_routes, \
        self.filtered_routes, \
        self.exported_routes, \
        self.preferred_routes = self._parse_processed_routes_count()

        self.neighbor_address = self._parse_neighbor_address()
        self.neighbor_as = self._parse_neighbor_as()
        self.source_address = self._parse_source_address()
        self.route_limit = self._parse_route_limit()
        self.hold_timer = self._parse_hold_timer()
        self.keepalive_timer = self._parse_keepalive_timer()

        try:
            neighbor_ip_address = ip_address(self.neighbor_address)
            self.value = int(neighbor_ip_address)
        except ValueError as e:
            raise ParsingError('Wrong peer RS dump given', e)

    def _parse_peer_id(self):
        l = self._dump[0]
        parts = l.split()
        peer_id = parts[0].replace('peer%s_' % self.ip_version, 'peer_')
        return peer_id

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

    def _parse_processed_routes_count(self):
        filtered_pattern = re.compile(r'(\d*) imported, (\d*) filtered, (\d*) exported, (\d*) preferred')
        for l in self._dump:
            result = filtered_pattern.search(l)
            if result:
                groups = result.groups()
                return [int(x) for x in groups]
        return 0, 0, 0, 0

    def _parse_neighbor_address(self):
        return self._extract_word('Neighbor address', 2)

    def _parse_neighbor_as(self):
        neighbor_as = self._extract_word('Neighbor AS', 2)
        if neighbor_as:
            return int(neighbor_as)
        else:
            return None

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


class Community:

    def __init__(self, data):
        self.asn = None
        self.value = None
        self.description = ''

        parts = data.split(',')

        if not len(parts) == 2:
            raise ValueError('Wrong community data given: %s' % data)

        if not all([parts[0].isdecimal(), parts[1].isdecimal()]):
            raise ValueError('Wrong community data given: %s' % data)

        try:
            self.asn = int(parts[0])
            self.value = int(parts[1])
        except (TypeError, ValueError):
            raise ValueError('Wrong community data given: %s' % data)

        self.parse_description()

    def parse_description(self):

        if self.asn in config.LOCAL_AS:

            if self.value in config.CITY_COMMUNITIES:
                self.description = 'Received in %s' % config.CITY_COMMUNITIES.get(self.value)
            elif self.value in config.SERVICE_COMMUNITIES:
                self.description = config.SERVICE_COMMUNITIES.get(self.value)
            elif self.value in config.PEERING_COMMUNITIES:
                self.description = config.PEERING_COMMUNITIES.get(self.value)

        elif self.asn == 0:

            if self.value in config.CITY_COMMUNITIES:
                self.description = 'Do not advertise to %s' % config.CITY_COMMUNITIES.get(self.value)

            elif self.value in config.PEERING_COMMUNITIES:
                self.description = 'Do not advertise to %s' % config.PEERING_COMMUNITIES.get(self.value)

            else:
                self.description = 'Do not advertise to as%s' % self.value

        elif self.asn in config.PREPEND_COMMUNITIES:
            self.description = config.PREPEND_COMMUNITIES.get(self.asn)

            if self.value in config.CITY_COMMUNITIES:
                self.description += ' to %s' % config.CITY_COMMUNITIES.get(self.value)

            elif self.value in config.PEERING_COMMUNITIES:
                self.description += ' to %s' % config.PEERING_COMMUNITIES.get(self.value)

            else:
                self.description += ' to as%s' % self.value

    def __str__(self):
        return '%s,%s' % (self.asn, self.value)
