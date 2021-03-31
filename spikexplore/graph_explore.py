from spikexplore.graph import graph_from_edgeslist, reduce_graph, handle_spikyball_neighbors
from spikexplore.collect_edges import spiky_ball


def create_graph(backend, nodes_df, edges_df, nodes_info, config):
    g = graph_from_edgeslist(edges_df, min_weight=config['min_weight'])
    g = backend.add_graph_attributes(g, nodes_df, edges_df, nodes_info)
    g = reduce_graph(g, config['min_degree'])
    g = handle_spikyball_neighbors(g, backend)
    return g


def explore(backend, initial_nodes, config):
    if not initial_nodes:
        raise ValueError('Cannot start without initial nodes.')
    nodes_list, nodes_df, edges_df, nodes_info = spiky_ball(initial_nodes,
                                                            backend,
                                                            config['collection_settings'],
                                                            node_acc=backend.get_node_info()
                                                            )
    # create graph from edge list
    g = create_graph(backend, nodes_df, edges_df, nodes_info, config['graph'])
    return g
