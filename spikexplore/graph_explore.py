import graph
from .collect_edges import spiky_ball


def create_graph(backend, nodes_df, edges_df, nodes_info, config):
    g = graph.graph_from_edgeslist(edges_df, min_weight=config['min_weight'])
    g = graph.add_edges_attributes(g, edges_df, drop_cols=['tweet_id', 'degree_target', 'degree_source'])
    g = graph.add_node_attributes(g, backend.reshape_node_data(nodes_df), attr_dic=nodes_info, attr_name='all_hashtags')
    g = graph.reduce_graph(g, config['min_degree'])
    g = graph.handle_spikyball_neighbors(g, backend)
    return g


def explore(backend, initial_nodes, config):
    nodes_list, nodes_df, edges_df, nodes_info = spiky_ball(initial_nodes,
                                                            backend,
                                                            config['collection_settings'],
                                                            node_acc=backend.get_node_info()
                                                            )
    # create graph from edge list
    g = create_graph(backend, nodes_df, edges_df, nodes_info, config['graph'])
    return g
