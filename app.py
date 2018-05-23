from flask import Flask, render_template, request, redirect
from models import RouteServer, Prefix

app = Flask(__name__)

servers = {
    'rs1': 'mr-srv0',
    'rs2': 'novosib-srv0'
}


@app.route("/")
def index():
    return redirect("/wix/summary/")


@app.route("/<service>/summary/")
def summary(service):
    if service not in ['fv', 'wix']:
        return redirect('/wix/summary/')

    family = request.args.get('family', "4")
    if family not in ['4', '6']:
        family = "4"

    rs1 = RouteServer(servers['rs1'], service, family)
    rs2 = RouteServer(servers['rs2'], service, family)

    rs1_peers = rs1.peers()
    rs2_peers = rs2.peers()

    pairs = peers_pairs(rs1_peers, rs2_peers)

    return render_template("summary.html",
                           pairs=pairs,
                           service=service,
                           family=family,
                           page='summary')


@app.route("/<service>/peer/<peer_id>/routes/")
def peer_routes(service, peer_id):
    if service not in ['wix', 'fv']:
        return redirect('/')

    filtered = False

    family = request.args.get('family', "4")
    if family not in ['4', '6']:
        family = "4"

    rs1 = RouteServer(servers['rs1'], service, family)
    rs2 = RouteServer(servers['rs2'], service, family)

    rs1_peer = rs1.peer(peer_id)
    rs2_peer = rs2.peer(peer_id)

    rs1_routes = rs1.routes(peer_id, 'accepted')
    rs2_routes = rs2.routes(peer_id, 'accepted')

    return render_template("peer_routes.html",
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


@app.route("/<service>/peer/<peer_id>/routes/rejected/")
def peer_routes_rejected(service, peer_id):
    if service not in ['wix', 'fv']:
        return redirect('/')

    filtered = True

    family = request.args.get('family', "4")
    if family not in ['4', '6']:
        family = "4"

    rs1 = RouteServer(servers['rs1'], service, family)
    rs2 = RouteServer(servers['rs2'], service, family)

    rs1_peer = rs1.peer(peer_id)
    rs2_peer = rs2.peer(peer_id)

    rs1_routes = rs1.routes(peer_id, 'filtered')
    rs2_routes = rs2.routes(peer_id, 'filtered')

    return render_template("peer_routes.html",
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


@app.route("/<service>/peer/<peer_id>/")
def peer(service, peer_id):
    error = None

    if service not in ['wix', 'fv']:
        return redirect('/')

    family = request.args.get('family', "4")
    if family not in ['4', '6']:
        family = "4"

    rs1 = RouteServer(servers['rs1'], service, family)
    rs2 = RouteServer(servers['rs2'], service, family)

    rs1_peer = rs1.peer(peer_id)
    rs2_peer = rs2.peer(peer_id)

    return render_template("peer.html",
                           service=service,
                           family=family,
                           peer_id=peer_id,
                           rs1=rs1,
                           rs2=rs2,
                           rs1_peer=rs1_peer,
                           rs2_peer=rs2_peer,
                           peer=peer,
                           error=error)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5150)
