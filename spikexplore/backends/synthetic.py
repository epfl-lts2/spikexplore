import networkx as nx
import pandas as pd
from spikexplore.NodeInfo import NodeInfo
from spikexplore.graph import add_node_attributes, add_edges_attributes


class SyntheticNetwork:
	class SynthNodeInfo(NodeInfo):
		def __init__(self, nodes=pd.DataFrame()):
			self.nodes = nodes

		def update(self, new_info):
			return

		def get_nodes(self):
			return self.nodes

	def __init__(self, g, config):
		# Instantiate an object
		self.G = g
		self.config = config

	def create_node_info(self):
		return self.SynthNodeInfo()

	def get_neighbors(self, node_id):
		# collect info on the node and its (out going) edges
		# return 2 dataframes, one with edges info and the other with the node info
		G = self.G
		if node_id not in G:
			return self.SynthNodeInfo(pd.DataFrame()), pd.DataFrame()
		# node data
		node_df = pd.DataFrame([{'source': node_id, **G.nodes[node_id]}])
		# Edges and edge data		
		if nx.is_directed(G):
			edges = G.out_edges(node_id, data=True)
		else:
			edges = G.edges(node_id, data=True)

		edgeprop_dic_list = []
		for source, target, data in edges:
			edge_dic = {'source': source, 'target': target, **data}
			edgeprop_dic_list.append(edge_dic)
		edges_df = pd.DataFrame(edgeprop_dic_list)
		edges_df['weight'] = 1.0
		return self.SynthNodeInfo(node_df), edges_df

	def filter(self, node_info, edges_df):
		if len(edges_df) < self.config.min_degree:
			# discard the node
			node_info = self.SynthNodeInfo(pd.DataFrame())
			edges_df = pd.DataFrame()
		# filter the edges
		edges_df = self.filter_edges(edges_df)
		return node_info, edges_df

	def filter_edges(self, edges_df):
		return edges_df

	def neighbors_list(self, edges_df):
		if edges_df.empty:
			return edges_df
		neighbors = edges_df['target'].unique().tolist()
		return neighbors

	def neighbors_with_weights(self, edges_df):
		node_list = self.neighbors_list(edges_df)
		node_dic = {}
		for node in node_list:
			node_dic[node] = len(edges_df) # degree of the node
		return node_dic

	def reshape_node_data(self, nodes_df):
		nodes_df.set_index('source', inplace=True)
		return nodes_df

	def add_graph_attributes(self, g, nodes_df, edges_df, nodes_info):
		g = add_edges_attributes(g, edges_df)
		g = add_node_attributes(g, self.reshape_node_data(nodes_df))
		return g
