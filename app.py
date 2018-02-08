from models import RouteServer, Prefix

#r = RouteServer()
#peers = r.peers()

# for peer in peers:

    # Summary
    # print(peer.peer_id)
    # print("%s: %s since %s" % (peer.state, peer.bgp_state_details, peer.last_event_time))
    # print(" Description:\t%s" % peer.description)
    # print(" Preference:\t%s" % peer.preference)
    # print(" Import_limit:\t%s" % peer.import_limit)
    # print(" Neighbor_address:\t%s" % peer.neighbor_address)
    # print(" Neighbor_as:\t%s" % peer.neighbor_as)
    # print(" Source_address:\t%s" % peer.source_address)
    # print(" Route_limit:\t%s" % peer.route_limit)
    # print(" Hold_timer:\t%s" % peer.hold_timer)
    # print(" Keepalive_timer:\t%s" % peer.keepalive_timer)
    #
    # print(" Routes:")
    # print("\tImported:\t%s" % peer.imported_routes)
    # print("\tFiltered:\t%s" % peer.filtered_routes)
    # print("\tExported:\t%s" % peer.exported_routes)
    # print("\tPreferred:\t%s" % peer.preferred_routes)
    # print("")

# Prefix

prefix = Prefix()
for next_hop in prefix.next_hops():
    print(next_hop)
    print("\tOrigin:\t\t%s" % next_hop.origin)
    print("\tAS Path:\t%s" % next_hop.as_path)
    print("\tMED:\t\t%s" % next_hop.med)
    print("\tLocal Pref:\t%s" % next_hop.local_pref)
    print("\tCommunity:\t%s" % next_hop.community)
