import pandas as pd
import numpy as np
import os
import logging
from spikexplore.NodeInfo import NodeInfo
from spikexplore.graph import process_hop

logger = logging.getLogger(__name__)


def split_edges(edges_df, node_list):
    # split edges between the ones connecting already collected nodes and the ones connecting new nodes
    edges_df_in = edges_df[edges_df['target'].isin(node_list)]
    edges_df_out = edges_df[~(edges_df['target'].isin(node_list))]
    return edges_df_in, edges_df_out 


def remove_edges_with_target_nodes(edges_df, node_list):
    new_edges_df = edges_df[edges_df['target'].isin(node_list)]
    return new_edges_df


def degree_weight(node_type, edges_df):
    edges_df.reset_index(inplace=True)
    degree_df = edges_df[[node_type, 'weight']].groupby([node_type]).sum()
    degree_df.columns = ['degree_'+node_type]
    # needs reset_index and set_index to keep the initial index.
    edges_df = edges_df.merge(degree_df, on=node_type)
    edges_df.set_index('index', inplace=True)
    edges_df.sort_index(inplace=True)
    # edges_df2['weight_over_degree'] = edges_df2['weight']/edges_df2['degree']
    degree_vec = np.array(edges_df['degree_'+node_type].tolist())
    return degree_vec, edges_df


def probability_function(edges_df, expansion_type, degree):
    # Taking the weights into account for the random selection
    if expansion_type == 'spikyball':
        source_degree, edge_degree, target_degree = 0, 1, 0
    elif expansion_type == 'hubball':
        source_degree,  edge_degree, target_degree = degree, 1, 0
    elif expansion_type == 'coreball':
        source_degree, edge_degree, target_degree = 0, 1, degree
    elif expansion_type == 'fireball':
        source_degree, edge_degree, target_degree = -1, 1, 0
    elif expansion_type == 'firecoreball':
        source_degree, edge_degree, target_degree = -1, 1, degree
    else:
        raise ValueError('Unknown ball type.')

    weight_vec = np.array(edges_df['weight'].tolist())
    target_degree_vec, edges_df = degree_weight('target', edges_df)
    source_degree_vec, edges_df = degree_weight('source', edges_df)

    source_func = source_degree_vec.astype(float) ** source_degree
    weight_func = weight_vec.astype(float) ** edge_degree
    target_func = target_degree_vec.astype(float) ** target_degree
    proba_unormalized = source_func * weight_func * target_func
    proba_f = proba_unormalized / np.sum(proba_unormalized)  # Normalize weights
    
    return edges_df.index.tolist(), proba_f, edges_df


def random_subset(edges_df, balltype, mode, coeff, mode_value=None):

    # TODO handle balltype
    nb_edges = len(edges_df)
    if nb_edges == 0:
        return [], pd.DataFrame()
    edges_df.reset_index(drop=True, inplace=True)  # needs unique index values for random choice
    edges_indices, proba_f, edges_df = probability_function(edges_df, balltype, coeff)

    if mode == 'constant':
        random_subset_size = mode_value
        if isinstance(random_subset_size, int) and (nb_edges > random_subset_size):
            # Only explore a random subset of users
            logger.debug('---')
            logger.debug(
                'Too many edges ({}). Keeping a random subset of {}.'.format(nb_edges, random_subset_size))
        else:
            random_subset_size = nb_edges
    elif mode == 'percent':
        if mode_value <= 100 and mode_value > 0:
            ratio = 0.01*mode_value
            random_subset_size = round(nb_edges * ratio)
            if random_subset_size < 2:  # in case the number of edges is too small
                random_subset_size = min(nb_edges, 10)
                logger.warning('Fallback used!')
        else:
            raise ValueError('the value must be between 0 and 100.')
    else:
        raise ValueError('Unknown mode. Choose "constant" or "percent".')
    r_edges_idx = np.random.choice(edges_indices, random_subset_size, p=proba_f, replace=False)
    r_edges_df = edges_df.loc[r_edges_idx, :]

    nodes_list = r_edges_df['target'].unique().tolist()
    return nodes_list, r_edges_df


def spiky_ball(initial_node_list, graph_handle, cfg,
               node_acc=NodeInfo(), progress_callback=None):
    """ Sample the graph by exploring from an initial node list
    """

    exploration_depth = cfg.exploration_depth
    random_subset_mode = cfg.random_subset_mode
    random_subset_size = cfg.random_subset_size
    max_nodes_per_hop = cfg.max_nodes_per_hop
    expansion_type = cfg.expansion_type
    degree = cfg.degree
    number_of_nodes = cfg.number_of_nodes
    if exploration_depth < 2:
        raise ValueError('Exploration depth must be > 1.')

    # Initialization
    new_node_list = initial_node_list.copy()
    total_node_list = []  # new_node_list

    total_edges_df = pd.DataFrame()
    total_nodes_df = pd.DataFrame()
    new_edges = pd.DataFrame()

    # Loop over layers
    for depth in range(exploration_depth):
        logger.debug('')
        logger.debug('******* Processing users at {}-hop distance *******'.format(depth))

        # Option to choose the number of nodes in the final graph
        if number_of_nodes:
            if len(total_node_list + new_node_list) > number_of_nodes:
                # Truncate the list of new nodes
                max_nodes = min(max_nodes_per_hop, number_of_nodes - len(total_node_list))
                if max_nodes <= 0:
                    break
                logger.info('-- max nb of nodes reached in iteration {} --'.format(depth))
                new_node_list = new_node_list[:max_nodes]
                new_edges = remove_edges_with_target_nodes(new_edges, new_node_list)

        new_node_dic, edges_df, nodes_df, node_acc = process_hop(graph_handle, new_node_list, node_acc)
        if nodes_df.empty:
            break
        nodes_df['spikyball_hop'] = depth  # Mark the depth of the spiky ball on the nodes    
        
        total_node_list = total_node_list + new_node_list
        edges_df_in, edges_df_out = split_edges(edges_df, total_node_list)

        # add edges linking to new nodes
        total_edges_df = pd.concat([total_edges_df, edges_df_in, new edges])
        total_nodes_df = pd.concat([total_nodes_df, nodes_df])
        
        new_node_list, new_edges = random_subset(edges_df_out, expansion_type, mode=random_subset_mode,
                                                 mode_value=random_subset_size, coeff=degree)
        if progress_callback:
            progress_callback(depth, exploration_depth)
        logger.debug('new edges:{} subset:{} in_edges:{}'.format(len(edges_df_out), len(new_edges), len(edges_df_in)))

    logger.debug('Nb of layers reached: {}'.format(depth))
	if not total_edges_df.empty:
    	total_edges_df = total_edges_df.sort_values('weight', ascending=False)

    return total_node_list, total_nodes_df, total_edges_df, node_acc


def save_data(nodes_df, edges_df, data_path):
    # Save to json file
    edgefilename = os.path.join(data_path, 'edges_data.json')
    nodefilename = os.path.join(data_path, 'nodes_data.json')
    logger.debug('Writing', edgefilename)
    edges_df.to_json(edgefilename)
    logger.debug('Writing', nodefilename)
    nodes_df.to_json(nodefilename)
    return None


def load_data(data_path):
    nodesfilename = os.path.join(data_path, 'nodes_data.json')
    edgesfilename = os.path.join(data_path, 'edges_data.json')
    logger.debug('Loading', nodesfilename)
    nodes_df = pd.read_json(nodesfilename)
    logger.debug('Loading', edgesfilename)
    edges_df = pd.read_json(edgesfilename)
    return nodes_df, edges_df
