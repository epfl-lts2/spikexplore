import pandas as pd
import networkx as nx
import numpy as np
import json
import logging
from .helpers import combine_dicts
from datetime import datetime, timedelta
import community
from tqdm import tqdm


logger = logging.getLogger(__name__)


def convert_to_json(edge_df):
    """
    Check if column type is list or dict and convert it to json
        list or dict can not be saved using gexf or graphml format.
    """
    edge_df_str = edge_df.copy()
    for idx, col in enumerate(edge_df.columns):
        first_row_element = edge_df.iloc[0, idx]
        if isinstance(first_row_element, list) or isinstance(first_row_element, dict):
            edge_df_str[col] = edge_df[col].apply(json.dumps)
            logger.debug('Field "{}" of class {} converted to json string'.format(col, type(first_row_element)))
    return edge_df_str


def graph_from_edgeslist(edge_df, min_weight=0):
    logger.debug('Creating the graph from the edge list')
    # The indices in the dataframe are source and target for the edges
    G = nx.from_pandas_edgelist(edge_df[edge_df['weight'] >= min_weight],
                                source='source', target='target', create_using=nx.DiGraph)
    logger.info('Nb of nodes: {}'.format(G.number_of_nodes()))
    return G


def attributes_tojson(data_dic):
    for propname, propdic in data_dic.items():
        for key, value in propdic.items():
            if isinstance(value, list):
                data_dic[propname][key] = json.dumps(value)
            else:
                data_dic[propname][key] = value
    return data_dic


def add_node_attributes(graph, node_df, attr_dic=None, attr_name=''):
    node_dic = node_df.to_dict()

    node_dic = attributes_tojson(node_dic)
    for propname, propdic in node_dic.items():
        nx.set_node_attributes(graph, propdic, name=propname)
    if attr_dic:
        nx.set_node_attributes(graph, attr_dic, name=attr_name)
    return graph


def add_edges_attributes(g, edges_df, drop_cols=None):
    if edges_df.empty:
        return g
    if drop_cols:
        edge_attr_df = edges_df.drop(columns=drop_cols)
    else:
        edge_attr_df = edges_df
    edge_attr_df['ii'] = edge_attr_df[['source', 'target']].apply(tuple, axis=1)
    edge_dic = edge_attr_df.set_index('ii').drop(columns=['source', 'target']).to_dict()

    for propname, propdic in edge_dic.items():
        nx.set_edge_attributes(g, propdic, name=propname)
    return g


def reduce_graph(g, degree_min):
    # Drop node with small degree
    remove = [node for node, degree in dict(g.degree()).items() if degree < degree_min]
    g.remove_nodes_from(remove)
    logger.info('Nb of nodes after removing nodes with degree strictly smaller than {}: {}'.format(degree_min,
                                                                                                    g.number_of_nodes()))
    isolates = list(nx.isolates(g))
    g.remove_nodes_from(isolates)
    logger.info('removed {} isolated nodes.'.format(len(isolates)))
    return g


def detect_communities(G):
    # first compute the best partition
    if isinstance(G, nx.DiGraph):
        Gu = G.to_undirected()
    else:
        Gu = G
    partition = community.best_partition(Gu, weight='weight')
    if not partition.values():
        logger.warning('No communities found in graph')
        return G, {}
    nx.set_node_attributes(G, partition, name='community')
    logger.debug('Communities saved on the graph as node attributes.')
    nb_partitions = max(partition.values()) + 1
    logger.info('Nb of partitions: {}'.format(nb_partitions))
    # Create a dictionary of subgraphs, one per community
    community_dic = {}
    for idx in range(nb_partitions):
        subgraph = G.subgraph([key for (key, value) in partition.items() if value == idx])
        community_dic[idx] = subgraph
    # clusters_modularity = community.modularity(partition, Gu)
    return G, community_dic


def remove_small_communities(G, community_dic, min_size):
    community_tmp = {k: v.copy() for k, v in community_dic.items()}
    nb_removed = 0
    for key in community_tmp:
        graph = community_tmp[key]
        if graph.number_of_nodes() <= min_size:
            G.remove_nodes_from(graph.nodes())
            nb_removed += 1
    logger.info('removed {} community(ies) smaller than {} nodes.'.format(nb_removed, min_size))
    return G


def process_hop(graph_handle, node_list, nodes_info_acc):
    """ collect the tweets and tweet info of the users in the list username_list
    """
    new_node_dic = {}
    total_edges_df = pd.DataFrame()
    total_nodes_df = pd.DataFrame()

    # Display progress bar if needed
    disable_tqdm = logging.root.level >= logging.INFO
    logger.info('processing next hop with {} nodes'.format(len(node_list)))
    for node in tqdm(node_list, disable=disable_tqdm):
        # Collect neighbors for the next hop
        node_info, edges_df = graph_handle.get_neighbors(node)
        node_info, edges_df = graph_handle.filter(node_info, edges_df)

        total_nodes_df = pd.concat([total_nodes_df, node_info.get_nodes()])
        nodes_info_acc.update(node_info)  # add new info

        total_edges_df = pd.concat([total_edges_df, edges_df])
        neighbors_dic = graph_handle.neighbors_with_weights(edges_df)
        new_node_dic = combine_dicts(new_node_dic, neighbors_dic)

    return new_node_dic, total_edges_df, total_nodes_df, nodes_info_acc


def handle_spikyball_neighbors(graph, backend, remove=True, node_acc=None):
    # Complete the info of the nodes not collected
    sp_neighbors = [node for node, data in graph.nodes(data=True) if 'spikyball_hop' not in data]
    logger.info('Number of neighbors of the spiky ball: {}'.format(len(sp_neighbors)))

    # 2 options: 1) remove the neighbors or 2) rerun the collection to collect the missing node info
    if remove:
        # Option 1:
        logger.info('Removing spiky ball neighbors...')
        graph.remove_nodes_from(sp_neighbors)
        logger.info('Number of nodes after removal: {}'.format(graph.number_of_nodes()))
    else:
        # TODO this needs checking
        # Option 2: collect the missing node data
        logger.info('Collecting info for neighbors...')
        new_nodes_founds, edges_df, nodes_df, node_acc = process_hop(backend, sp_neighbors, node_acc)
        graph = add_node_attributes(graph, nodes_df)
        sp_nodes_dic = {node: -1 for node in sp_neighbors}
        nx.set_node_attributes(graph, sp_nodes_dic, name='spikyball_hop')
        logger.info('Node info added to the graph.')
    # Check integrity
    for node, data in graph.nodes(data=True):
        if 'spikyball_hop' not in data:
            logger.error('Missing information for node ', node)
    return graph


def compute_meantime(date_list):
    # return mean time and standard deviation of a list of dates in days
    # import numpy as np
    d_list = [datetime.strptime(dt, '%Y-%m-%d %H:%M:%S') for dt in date_list]
    second_list = [x.timestamp() for x in d_list]
    meand = np.mean(second_list)
    stdd = np.std(second_list)
    return datetime.fromtimestamp(meand), timedelta(seconds=stdd)


def save_graph(graph, graphfilename):
    nx.write_gexf(graph, graphfilename)
    logger.debug('Graph saved to', graphfilename)
