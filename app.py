import ipaddress
import pickle
import re
from threading import Thread

from flask import Flask, render_template, request, redirect
from datetime import datetime, timedelta

import config
from models import RouteServer

app = Flask(__name__)

rs1 = RouteServer(server=config.SERVERS['rs1'])
rs2 = RouteServer(server=config.SERVERS['rs2'])

try:
    f = open('next_hop_map.pickle', 'rb')
except FileNotFoundError:
    f = open('next_hop_map.pickle', 'wb')
    pickle.dump({'wix': {4: {}, 6: {}}, 'fv': {4: {}, 6: {}}}, f)
    f.close()
else:
    f.close()


class GetParallel:
    results = [None, None]

    def __init__(self, rs1_func=None, rs2_func=None, func_args=None, func_kwargs=None):
        self.functions = [rs1_func, rs2_func]
        self.func_args = func_args or []
        self.func_kwargs = func_kwargs or {}

        task1 = Thread(target=self.exec, args=[0])
        task2 = Thread(target=self.exec, args=[1])
        task1.start()
        task2.start()
        task1.join()
        task2.join()

    def exec(self, index):
        func = self.functions[index]
        result = func(*self.func_args, **self.func_kwargs)
        self.results[index] = result


def peer_id_is_valid(peer_id):
    peer_re = re.compile(r'^peer_\d{4,6}$')
    if peer_re.match(peer_id):
        return True
    return False


@app.route('/')
def index():
    return redirect('/wix/summary/')


@app.route('/<service>/summary/')
def peers(service):
    if service not in ['fv', 'wix']:
        return render_template('error.html', error='Wrong service'), 404

    ip_version = get_family(request)

    parallel = GetParallel(rs1_func=rs1.peers,
                           rs2_func=rs2.peers,
                           func_kwargs={'service': service, 'ip_version': ip_version})

    pairs = peers_pairs(parallel.results[0], parallel.results[1])

    # filter neighbors with hidden as
    if config.HIDDEN_PEER_AS:
        filtered_pairs = []
        for pair in pairs:
            if pair['neighbor_as'] in config.HIDDEN_PEER_AS:
                continue
            filtered_pairs.append(pair)
        pairs = filtered_pairs

    # filter by interval arg
    interval = None
    given_interval = request.args.get('interval', '')
    if given_interval.isdigit():
        interval = int(given_interval)

    if interval:
        filtered_pairs = []
        now = datetime.now()
        delta = timedelta(minutes=interval)
        for pair in pairs:
            rs1_data = pair.get('rs1')
            rs2_data = pair.get('rs2')
            rs1_last_time = datetime.strptime(rs1_data.last_event_time, '%Y-%m-%d %H:%M:%S')
            rs2_last_time = datetime.strptime(rs2_data.last_event_time, '%Y-%m-%d %H:%M:%S')
            if now - rs1_last_time < delta:
                filtered_pairs.append(pair)
                continue
            if now - rs2_last_time < delta:
                filtered_pairs.append(pair)
                continue
        pairs = filtered_pairs

    # filter by status arg
    status = None
    given_status = request.args.get('status', '')
    if given_status in ['up', 'down']:
        status = given_status
    if status:
        filtered_pairs = []
        for pair in pairs:
            rs1_data = pair.get('rs1')
            rs2_data = pair.get('rs2')
            if rs1_data.state == status:
                filtered_pairs.append(pair)
                continue
            if rs2_data.state == status:
                filtered_pairs.append(pair)
                continue
        pairs = filtered_pairs

    return render_template('summary.html',
                           pairs=pairs,
                           service=service,
                           family=ip_version,
                           page='summary')


@app.route('/<service>/peer/<peer_id>/')
def peer(service, peer_id):
    if service not in ['wix', 'fv']:
        return render_template('error.html', error='Wrong service'), 404

    if not peer_id_is_valid(peer_id):
        return render_template('error.html', error='Invalid peer format'), 404

    ip_version = get_family(request)

    parallel = GetParallel(rs1_func=rs1.peer,
                           rs2_func=rs2.peer,
                           func_args=[peer_id],
                           func_kwargs={'service': service, 'ip_version': ip_version})

    rs1_peer, rs2_peer = parallel.results[0], parallel.results[1]

    return render_template('peer_page.html',
                           service=service,
                           family=ip_version,
                           peer_id=peer_id,
                           rs1=rs1,
                           rs2=rs2,
                           rs1_peer=rs1_peer,
                           rs2_peer=rs2_peer,
                           peer=peer)


@app.route('/<service>/peer/<peer_id>/routes/')
def peer_prefixes(service, peer_id):
    if service not in ['wix', 'fv']:
        return render_template('error.html', error='Page not found'), 404

    if not peer_id_is_valid(peer_id):
        return render_template('error.html', error='Invalid peer format'), 404

    rejected_mode = request.args.get('rejected', False)
    if rejected_mode:
        rejected_mode = True

    ip_version = get_family(request)
    parallel = GetParallel(rs1_func=rs1.peer,
                           rs2_func=rs2.peer,
                           func_args=[peer_id],
                           func_kwargs={'service': service, 'ip_version': ip_version})
    rs1_peer, rs2_peer = parallel.results[0], parallel.results[1]

    parallel = GetParallel(rs1_func=rs1.prefixes,
                           rs2_func=rs2.prefixes,
                           func_args=[peer_id, rejected_mode],
                           func_kwargs={'service': service, 'ip_version': ip_version})
    rs1_routes, rs2_routes = parallel.results[0], parallel.results[1]

    return render_template('peer_routes_page.html',
                           service=service,
                           family=ip_version,
                           peer_id=peer_id,
                           rs1=rs1,
                           rs2=rs2,
                           rs1_peer=rs1_peer,
                           rs2_peer=rs2_peer,
                           rs1_routes=rs1_routes,
                           rs2_routes=rs2_routes,
                           rejected_mode=rejected_mode,
                           peer=peer)


@app.route('/<service>/route/')
def route(service):
    if service not in ['wix', 'fv']:
        return render_template('error.html', error='Wrong service'), 404

    given_prefix = request.args.get('destination', None)
    if not given_prefix:
        return render_template('error.html', error='No prefix given')

    try:
        destination, ip_version = adopt_prefix(given_prefix)
    except ValueError as e:
        return render_template('error.html', error=e)

    parallel = GetParallel(rs1_func=rs1.route,
                           rs2_func=rs2.route,
                           func_kwargs={'destination': destination,
                                        'service': service,
                                        'ip_version': ip_version})
    rs1_route, rs2_route = parallel.results[0], parallel.results[1]

    return render_template('route_page.html',
                           service=service,
                           family=ip_version,
                           destination=given_prefix,
                           search_string=given_prefix,
                           rs1=rs1,
                           rs2=rs2,
                           rs1_route=rs1_route,
                           rs2_route=rs2_route,
                           page='route')


@app.route('/search/')
def search():
    service = request.args.get('service', 'wix')

    if service not in ['fv', 'wix']:
        return render_template('error.html', error='Wrong service')

    search_string = request.args.get('search', '').strip()
    if not search_string:
        return render_template('error.html', error='Nothing to search', service=service)

    try:
        destination, ip_version = adopt_prefix(search_string)
    except ValueError as e:
        return render_template('error.html', error=e, service=service, search_string=search_string)

    return redirect('/%s/route/?destination=%s&family=%s' % (service, destination, ip_version))


def peers_pairs(rs1_peers, rs2_peers):
    pairs = []

    checked_values = []

    for rs1_peer in rs1_peers:
        pair = find_pair(rs1_peer.neighbor_address, rs2_peers)
        twins = {
            'value': rs1_peer.value,
            'neighbor_address': rs1_peer.neighbor_address,
            'neighbor_as': rs1_peer.neighbor_as,
            'description': rs1_peer.description,
            'rs1': rs1_peer,
            'rs2': pair,
            'peer_id': rs1_peer.peer_id,
        }
        pairs.append(twins)
        checked_values.append(rs1_peer.value)

    for rs2_peer in rs2_peers:
        if not rs2_peer.value in checked_values:
            pair = find_pair(rs2_peer.value, rs1_peers)
            twins = {
                'value': rs2_peer.value,
                'neighbor_address': rs2_peer.neighbor_address,
                'neighbor_as': rs2_peer.neighbor_as,
                'description': rs2_peer.description,
                'rs1': rs2_peer,
                'rs2': pair,
            }
            pairs.append(twins)

    return pairs


def find_pair(neighbor_address, peers):
    for peer in peers:
        if peer.neighbor_address == neighbor_address:
            return peer
    return None


def get_family(r):
    family = r.args.get('family', '4')
    if family not in ['4', '6']:
        family = '4'
    return int(family)


def adopt_prefix(destination):
    try:
        network = ipaddress.ip_network(destination)
    except ValueError as e:
        raise ValueError('Wrong data given: %s' % e)

    # network.network_address — no mask lenght
    # str(network) — with mask lengh

    if network.version == 4:
        if network.prefixlen == 32:
            return '%s' % network.network_address, 4
        else:
            return '%s' % network, 4

    if network.version == 6:
        if network.prefixlen == 128:
            return '%s' % network.network_address, 6
        else:
            return '%s' % network, 6


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5777)
