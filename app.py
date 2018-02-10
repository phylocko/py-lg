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

    family = request.args.get('family', "rs1")
    if not family in ['4', '6']:
        family = "4"

    rs1 = RouteServer(servers['rs1'], service, family)
    rs2 = RouteServer(servers['rs2'], service, family)
    rs1_peers = rs1.peers()
    rs2_peers = rs2.peers()

    pairs = peers_pairs(rs1_peers, rs2_peers)

    return render_template("summary.html",
                           pairs=pairs,
                           service=service,
                           family=family)


def peers_pairs(rs1_peers, rs2_peers):
    pairs = []

    checked_values = []

    for peer in rs1_peers:
        pair = find_pair(peer.value, rs2_peers)
        twins = {
            'value': peer.value,
            'neighbor_address': peer.neighbor_address,
            'neighbor_as': peer.neighbor_as,
            'description': peer.description,
            'rs1': peer,
            'rs2': pair,
        }
        pairs.append(twins)
        checked_values.append(peer.value)

    for peer in rs2_peers:
        if not peer.value in checked_values:
            pair = find_pair(peer.value, rs1_peers)
            twins = {
                'value': peer.value,
                'neighbor_address': peer.neighbor_address,
                'neighbor_as': peer.neighbor_as,
                'description': peer.description,
                'rs1': peer,
                'rs2': pair,
            }
            pairs.append(twins)

    return pairs


def find_pair(value, peers):
    for peer in peers:
        if peer.value == value:
            return peer
    return None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5150)
