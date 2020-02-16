# Copyright 2019 Vladislav Pavkin

import re
from datetime import datetime
from ipaddress import ip_address
from socket import gaierror
from typing import Optional

import paramiko
from paramiko.ssh_exception import SSHException

import config


class RequiredAttrs:
    def __init__(self, *args, **kwargs):
        for attr in ['dump', 'ip_version']:
            if attr not in kwargs:
                error = '%s initialized without "%s" attribute given' % (self.__class__.__name__, attr)
                raise ValueError(error)
        if kwargs['ip_version'] not in (4, 6):
            raise ValueError('Wrong ip_version given: "%s"' % kwargs['ip_version'])


class ParsingError(Exception):
    pass


class Peer(RequiredAttrs):
    # a product or 'show protocol <peer_id>' bird command

    _dump = None

    state = None
    peer_id = None
    bgp_state = None
    ip_version = None
    preference = None
    description = None
    neighbor_as = None
    route_limit = None
    import_limit = None
    source_address = None
    last_event_time = None
    imported_routes = None
    filtered_routes = None
    exported_routes = None
    preferred_routes = None
    neighbor_address = None
    bgp_state_details = None

    hold_timer = None
    keepalive_timer = None

    value = None  # peer address as int value, for sorting

    def __init__(self, dump=None, ip_version=None):
        super().__init__(dump=dump, ip_version=ip_version)
        self.ip_version = int(ip_version)
        self._dump = dump
        self._parse_dump()

    def __str__(self):
        return '<Peer %s [%s, %s]>' % (self.peer_id, self.neighbor_address, self.description or '?')

    def _parse_dump(self):
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
    # a product or 'show route' bird command

    def __init__(self, dump=None, ip_version=None):
        destination = None
        self.paths = []
        _dump = None
        self.ip_version = ip_version

        if dump:
            self._parse_dump(dump)

    def _parse_dump(self, dump):
        # getting a real destination prefix
        start_with_ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/\d{1,2}', re.MULTILINE)
        groups = start_with_ip_pattern.search(dump)
        if groups:
            self.destination = groups[0]

        # getting paths from the dump
        path_dumps = dump.split('unicast')
        for path_dump in path_dumps:
            if 'via' in path_dump:
                # we don't want to work with "BIRD 2.0.7 ready. \nTable master4" strings
                bgp_prefix = BGPPrefix(dump=path_dump, ip_version=self.ip_version, destination=self.destination)
                self.paths.append(bgp_prefix)

    def __str__(self):
        return '<Route to %s: %s>' % (self.destination, self.paths)

    def __repr__(self):
        return self.__str__()


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
    def _parse__show_route_peer(bird_dump) -> list:
        # splits dump into text blocks, each of them represent a single route
        blocks = []
        dump = ''

        for line in bird_dump.splitlines():
            if 'unicast' in line:
                if dump:
                    blocks.append(dump)
                    dump = ''
                dump += line + '\n'
            else:
                if dump:
                    dump += line + '\n'
        if dump:
            blocks.append(dump)
        return blocks

    def route(self, destination=None, service=None, ip_version=None) -> Optional[Route]:
        if self._session is None:
            return

        if '/' in destination:
            bird_command = "show route %s all" % destination
        else:
            bird_command = "show route for %s all" % destination

        server_command = '/var/run/bird.%s.ctl %s' % (service, bird_command)
        bird_dump = self._cmd(server_command)

        route = Route(dump=bird_dump, ip_version=ip_version)
        return route

    def peers(self, service='wix', ip_version=4) -> list:
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
                peer = Peer(dump=peer_dump, ip_version=ip_version)
            except ParsingError:
                continue
            else:
                peers.append(peer)
        return peers

    def peer(self, peer_id, service=None, ip_version=None) -> Optional[Peer]:
        if self._session is None:
            return

        peer_id = peer_id.replace('peer_', 'peer%s_' % ip_version)

        bird_command = 'show protocols all %s' % peer_id
        server_command = '/var/run/bird.%s.ctl %s' % (service, bird_command)
        bird_dump = self._cmd(server_command)

        peers = []
        parsed_protocols = self._parse__show_protocols(bird_dump=bird_dump, ip_version=ip_version)
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

    def peer_routes(self, peer_id, rejected, service=None, ip_version=None) -> (Peer, list):
        if self._session is None:
            return None, []

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

        dump = self._cmd(server_command)

        routes = []
        route_dumps = self._parse__show_route_peer(dump)

        for prefix_dump in route_dumps:

            prefix = BGPPrefix(dump=prefix_dump, ip_version=ip_version)
            if rejected:
                prefix.filtered = True
            routes.append(prefix)

        return peer, routes


class BGPPrefix:
    # a BGP prefix with it's attributes (such as next-hop, as_path, etc...)
    def __init__(self, dump=None, ip_version=None, destination=None):
        self.destination = None
        self.as_path = []
        self.communities = []
        self.via = None
        self.time = None
        self.origin = None
        self.next_hop = None
        self.filtered = False
        self.local_pref = None
        self.preferred = False
        self.next_hop_netname = None

        if destination:
            self.destination = destination

        if dump is None:
            raise ValueError('%s initialized without "dump"' % self.__class__.__name__)
        self._dump = dump.splitlines()

        if ip_version is None:
            raise ValueError('%s initialized without "ip_version"' % self.__class__.__name__)
        self.ip_version = int(ip_version)

        self._parse_dump()

    def __repr__(self):
        return 'Path to %s via %s%s' % (self.destination, self.next_hop, ' *' if self.preferred else '')

    def _parse_dump(self):
        if not self.destination:
            self.destination = self._extract_by_re(r'^\d{1,4}\.\d{1,4}\.\d{1,4}\.\d{1,4}\/\d{1,2}', 0)
        self.origin = self._extract_word('BGP.origin', 1)
        self.next_hop = self._extract_word('BGP.next_hop', 1)
        self.local_pref = self._extract_word('BGP.local_pref', 1)
        self.communities = self._parse_communities()
        self.as_path = self._parse_as_path()
        self.preferred = self._parse_preferred()

    def _parse_preferred(self):
        for line in self._dump:
            if '] * (' in line:
                return True
        return False

    def _parse_communities(self):
        community_values = []
        pattern = re.compile(r'(\(\d{1,8}\,\d{1,8}\))')
        for list in self._dump:
            if 'BGP.community' in list:
                groups = pattern.findall(list)
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
        for list in self._dump:
            if pattern in list:
                parts = list.split()
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

    def __repr__(self):
        return self.__str__()
