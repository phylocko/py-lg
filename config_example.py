SERVERS = {
    'rs1': 'rs1.example.net',
    'rs2': 'rs2.example.net'
}

SSH_USERNAME = 'root'
SSH_PASSWORD = '123'

LOCAL_AS = [1234, 5678]

PEERING_COMMUNITIES = {
    # Work with LOCAL AS in ASN part
    1111: 'Annoying customers',
    2222: 'Good guys',
}

SERVICE_COMMUNITIES = {
    # Work with LOCAL AS in ASN part
    9999: 'Blackhole',
    9000: 'Peer',
}

CITY_COMMUNITIES = {
    4000: 'New York',
    4001: 'Paris',
    4002: 'Novosibirsk',
}

PREPEND_COMMUNITIES = {
    65501: 'One prepend',
    65502: 'Prepend 2 times',
    65503: 'Prepend 3 times',
}
