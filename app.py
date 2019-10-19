import ipaddress
import re

from flask import Flask, render_template, request, redirect
import config
from models import RouteServer
import pickle

app = Flask(__name__)

try:
    f = open('next_hop_map.pickle', 'rb')
except FileNotFoundError:
    f = open('next_hop_map.pickle', 'wb')
    pickle.dump({'wix': {4: {}, 6: {}}, 'fv': {4: {}, 6: {}}}, f)
    f.close()
else:
    f.close()


def peer_id_is_valid(peer_id):
    peer_re = re.compile(r'^peer_\d{4,6}$')
    if peer_re.match(peer_id):
        return True
    return False


@app.route('/')
def index():
    return redirect('/wix/summary/')


@app.route('/<service>/summary/')
def summary(service):
    if service not in ['fv', 'wix']:
        return render_template('error.html', error='Wrong service'), 404

    family = get_family(request)

    rs1 = RouteServer(server=config.SERVERS['rs1'], service=service, ip_version=family)
    rs2 = RouteServer(server=config.SERVERS['rs2'], service=service, ip_version=family)

    rs1_peers = rs1.peers()
    rs2_peers = rs2.peers()

    pairs = peers_pairs(rs1_peers, rs2_peers)

    return render_template('summary.html',
                           pairs=pairs,
                           service=service,
                           family=family,
                           page='summary')


@app.route('/<service>/peer/<peer_id>/')
def peer(service, peer_id):
    if service not in ['wix', 'fv']:
        return render_template('error.html', error='Wrong service'), 404

    if not peer_id_is_valid(peer_id):
        return render_template('error.html', error='Invalid peer format'), 404

    family = get_family(request)

    rs1 = RouteServer(server=config.SERVERS['rs1'], service=service, ip_version=family)
    rs2 = RouteServer(server=config.SERVERS['rs2'], service=service, ip_version=family)

    rs1_peer = rs1.peer(peer_id)
    rs2_peer = rs2.peer(peer_id)

    return render_template('peer_page.html',
                           service=service,
                           family=family,
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

    filtered = False

    family = get_family(request)

    rs1 = RouteServer(config.SERVERS['rs1'], service, family)
    rs2 = RouteServer(config.SERVERS['rs2'], service, family)

    rs1_peer = rs1.peer(peer_id)
    rs2_peer = rs2.peer(peer_id)

    rs1_routes = rs1.prefixes(peer_id, filtered)
    rs2_routes = rs2.prefixes(peer_id, filtered)

    return render_template('peer_routes_page.html',
                           service=service,
                           family=family,
                           peer_id=peer_id,
                           rs1=rs1,
                           rs2=rs2,
                           rs1_peer=rs1_peer,
                           rs2_peer=rs2_peer,
                           rs1_routes=rs1_routes,
                           rs2_routes=rs2_routes,
                           filtered=filtered,
                           peer=peer)


@app.route('/<service>/peer/<peer_id>/routes/rejected/')
def peer_prefixes_rejected(service, peer_id):
    if not peer_id_is_valid(peer_id):
        return render_template('error.html', error='Invalid peer format'), 404

    if service not in ['wix', 'fv']:
        return redirect('/')

    rejected_mode = True

    family = get_family(request)

    rs1 = RouteServer(config.SERVERS['rs1'], service, family)
    rs2 = RouteServer(config.SERVERS['rs2'], service, family)

    rs1_peer = rs1.peer(peer_id)
    rs2_peer = rs2.peer(peer_id)

    rs1_routes = rs1.prefixes(peer_id, rejected_mode)
    rs2_routes = rs2.prefixes(peer_id, rejected_mode)

    return render_template('peer_routes_page.html',
                           service=service,
                           family=family,
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
        prefix, family = adopt_prefix(given_prefix)
    except ValueError as e:
        return render_template('error.html', error=e)

    rs1, rs2 = None, None
    rs1_route, rs2_route = None, None

    prefix = None
    address = None

    if given_prefix:
        if '/' in given_prefix:
            prefix = given_prefix
        else:
            address = given_prefix

        rs1 = RouteServer(config.SERVERS['rs1'], service, family)
        rs2 = RouteServer(config.SERVERS['rs2'], service, family)

        rs1_route = rs1.route(prefix=prefix, address=address)
        rs2_route = rs2.route(prefix=prefix, address=address)

    return render_template('route_page.html',
                           service=service,
                           family=family,
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
        destination, family = adopt_prefix(search_string)
    except ValueError as e:
        return render_template('error.html', error=e, service=service, search_string=search_string)

    return redirect('/%s/route/?destination=%s&family=%s' % (service, destination, family))


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
