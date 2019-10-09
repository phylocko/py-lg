import ipaddress
import re

from flask import Flask, render_template, request, redirect

from models import RouteServer

app = Flask(__name__)

servers = {
    'rs1': 'hostel.ihome.ru',
    'rs2': 'novosib-srv0.ihome.ru'
}


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
        return redirect('/wix/summary/')

    family = request.args.get('family', '4')
    if family not in ['4', '6']:
        family = '4'

    rs1 = RouteServer(servers['rs1'], service, family)
    rs2 = RouteServer(servers['rs2'], service, family)

    rs1_peers = rs1.peers()
    rs2_peers = rs2.peers()

    pairs = peers_pairs(rs1_peers, rs2_peers)

    return render_template('summary.html',
                           pairs=pairs,
                           service=service,
                           family=family,
                           page='summary')


@app.route('/<service>/peer/<peer_id>/routes/')
def peer_prefixes(service, peer_id):

    if not peer_id_is_valid(peer_id):
        return render_template('error.html', error='Invalid peer format'), 404

    if service not in ['wix', 'fv']:
        return redirect('/')

    filtered = False

    family = request.args.get('family', '4')
    if family not in ['4', '6']:
        family = '4'

    rs1 = RouteServer(servers['rs1'], service, family)
    rs2 = RouteServer(servers['rs2'], service, family)

    rs1_peer = rs1.peer(peer_id)
    rs2_peer = rs2.peer(peer_id)

    rs1_routes = rs1.prefixes(peer_id, filtered)
    rs2_routes = rs2.prefixes(peer_id, filtered)

    return render_template('peer_routes.html',
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

    family = request.args.get('family', '4')
    if family not in ['4', '6']:
        family = '4'

    rs1 = RouteServer(servers['rs1'], service, family)
    rs2 = RouteServer(servers['rs2'], service, family)

    rs1_peer = rs1.peer(peer_id)
    rs2_peer = rs2.peer(peer_id)

    rs1_routes = rs1.prefixes(peer_id, rejected_mode)
    rs2_routes = rs2.prefixes(peer_id, rejected_mode)

    return render_template('peer_routes.html',
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
        return redirect('/')

    family = request.args.get('family', '4')
    if family not in ['4', '6']:
        family = '4'

    destination = request.args.get('prefix', None)

    rs1, rs2 = None, None
    rs1_route, rs2_route = None, None

    prefix = None
    address = None

    if destination:
        if '/' in destination:
            prefix = destination
        else:
            address = destination

        # TODO: Validate prefix!
        rs1 = RouteServer(servers['rs1'], service, family)
        rs2 = RouteServer(servers['rs2'], service, family)

        rs1_route = rs1.route(prefix=prefix, address=address)
        rs2_route = rs2.route(prefix=prefix, address=address)

    return render_template('route.html',
                           service=service,
                           family=family,
                           destination=destination,
                           rs1=rs1,
                           rs2=rs2,
                           rs1_route=rs1_route,
                           rs2_route=rs2_route,
                           page='route')


@app.route('/<service>/peer/<peer_id>/')
def peer(service, peer_id):

    if not peer_id_is_valid(peer_id):
        return render_template('error.html', error='Invalid peer format'), 404

    if service not in ['wix', 'fv']:
        return redirect('/')

    family = request.args.get('family', '4')
    if family not in ['4', '6']:
        family = '4'

    rs1 = RouteServer(servers['rs1'], service, family)
    rs2 = RouteServer(servers['rs2'], service, family)

    rs1_peer = rs1.peer(peer_id)
    rs2_peer = rs2.peer(peer_id)

    return render_template('peer.html',
                           service=service,
                           family=family,
                           peer_id=peer_id,
                           rs1=rs1,
                           rs2=rs2,
                           rs1_peer=rs1_peer,
                           rs2_peer=rs2_peer,
                           peer=peer)


@app.route('/show/')
def show():
    service = request.args.get('service', 'wix')
    if service not in ['fv', 'wix']:
        return redirect('/wix/summary/')

    destination = request.args.get('search', '')

    try:
        network = ipaddress.ip_network(destination)
    except ValueError as e:
        return render_template('error.html', error='Wrong data given. %s' % e,
                               search_string=destination,
                               service=service,
                               family=get_family(request))

    if network.version == '4' and network.prefixlen == 32:
        new_destination = str(network)

    elif network.version == '6' and network.prefixlen == 128:
        new_destination = str(network)
    else:
        new_destination = str(network.network_address)

    return redirect('/%s/route/?prefix=%s&family=%s&search=%s' % (service,
                                                                  new_destination,
                                                                  network.version,
                                                                  destination))


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


def get_service(r):
    service = r.args.get('service', None)
    if service not in ['wix', 'fv']:
        service = None
    return service


def get_family(r):
    family = r.args.get('family', '4')
    if family not in ['4', '6']:
        family = '4'
    return family


def destination(destination):
    try:
        network = ipaddress.ip_network(destination)
    except ValueError as e:
        raise ValueError('Wrong data given. %s' % e)

    if network.version == '4' and network.prefixlen == 32:
        new_destination = str(network)

    elif network.version == '6' and network.prefixlen == 128:
        new_destination = str(network)
    else:
        new_destination = str(network.network_address)

    return new_destination


if __name__ == '__main__':
    app.run(host='85.112.118.20', port=5150)
