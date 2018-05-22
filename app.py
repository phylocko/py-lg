import re
import paramiko
from flask import Flask, render_template, request, redirect
from models import RouteServer, Prefix

app = Flask(__name__)

servers = {
    'rs1': 'mr-srv0',
    'rs2': 'novosib-srv0'
}


@app.route("/")
def index():
    return redirect("/summary/")


@app.route("/summary/")
def summary():

    service = request.args.get('service', "wix")
    if not service in ['fv', 'wix']:
        service = "wix"

    family = request.args.get('family', "4")
    if not family in ['4', '6']:
        family = "4"

    rs1 = RouteServer(servers['rs1'], service, family)
    rs2 = RouteServer(servers['rs2'], service, family)
    rs1.connect()
    rs2.connect()
    rs1_peers = rs1.peers()
    rs2_peers = rs2.peers()

    pairs = peers_pairs(rs1_peers, rs2_peers)

    return render_template("summary.html",
                           pairs=pairs,
                           service=service,
                           family=family)


@app.route("/peer/<peer>/routes/")
def peer_routes(peer):
    error = None
    service = "wix"
    rs1_peer = None
    rs2_peer = None

    family = request.args.get('family', "4")
    if not family in ['4', '6']:
        family = "4"

    peer_string = peer.strip()
    wix_pattern = re.compile("^193\.106\.(112|113)\.[0-9]{1,3}$")
    fv_pattern = re.compile("^85\.112\.(122|123)\.[0-9]{1,3}$")

    if not wix_pattern.search(peer_string) and not fv_pattern.search(peer_string):
        error = "The peer address %s is not correct." % peer_string

    else:
        if "193.106" in peer_string:
            service = "wix"
        else:
            service = "fv"

        rs1 = RouteServer(servers['rs1'], service, family)
        rs2 = RouteServer(servers['rs2'], service, family)

        rs1.peer(peer_string)
        rs2.peer(peer_string)

        rs1_peer = rs1._peers[0]
        rs2_peer = rs2._peers[0]

    return render_template("peer_routes.html",
                           service=service,
                           family=family,
                           peer_address=peer_string,
                           rs1=rs1,
                           rs2=rs2,
                           rs1_peer=rs1_peer,
                           rs2_peer=rs2_peer,
                           peer=peer,
                           error=error)


@app.route("/peer/<peer>/")
def peer(peer):
    error = None
    service = "wix"
    rs1_peer = None
    rs2_peer = None

    family = request.args.get('family', "4")
    if not family in ['4', '6']:
        family = "4"

    peer_string = peer.strip()
    wix_pattern = re.compile("^193\.106\.(112|113)\.[0-9]{1,3}$")
    fv_pattern = re.compile("^85\.112\.(122|123)\.[0-9]{1,3}$")

    if not wix_pattern.search(peer_string) and not fv_pattern.search(peer_string):
        error = "The peer address %s is not correct." % peer_string

    else:
        if "193.106" in peer_string:
            service = "wix"
        else:
            service = "fv"

        rs1 = RouteServer(servers['rs1'], service, family)
        rs2 = RouteServer(servers['rs2'], service, family)
        rs1.connect()
        rs2.connect()

        rs1_peer = rs1.peer(peer_string)
        rs2_peer = rs2.peer(peer_string)

    return render_template("peer.html",
                           service=service,
                           family=family,
                           peer_address=peer_string,
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
