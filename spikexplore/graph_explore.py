from spikexplore.graph import graph_from_edgeslist, reduce_graph, handle_spikyball_neighbors
from spikexplore.graph import detect_communities, remove_small_communities
from spikexplore.collect_edges import spiky_ball
import networkx as nx


def create_graph(backend, nodes_df, edges_df, nodes_info, config):
    min_weight = config.min_weight
    g = graph_from_edgeslist(edges_df, min_weight=min_weight)
    if nx.is_empty(g):
        return g
    g = backend.add_graph_attributes(g, nodes_df, edges_df, nodes_info)
    g = reduce_graph(g, config.min_degree)
    g = handle_spikyball_neighbors(g, backend)
    if config.as_undirected:
        g = g.to_undirected()
        c = nx.number_connected_components(g)
        if c == 1:
            return g
        # take largest connected component
        largest_cc = max(nx.connected_components(g), key=len)
        return nx.subgraph(g, largest_cc)
    # cannot do the connected component on directed graphs
    return g


def explore(backend, initial_nodes, config, progress_callback=None):
    if not initial_nodes:
        raise ValueError("Cannot start without initial nodes.")
    nodes_list, nodes_df, edges_df, nodes_info = spiky_ball(
        initial_nodes, backend, config.data_collection, node_acc=backend.create_node_info(), progress_callback=progress_callback
    )
    # create graph from edge list
    g = create_graph(backend, nodes_df, edges_df, nodes_info, config.graph)

    if config.graph.community_detection:
        _, community_dict = detect_communities(g)
        g = remove_small_communities(g, community_dict, config.graph.min_community_size)
    return g, nodes_info
