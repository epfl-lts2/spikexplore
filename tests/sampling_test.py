import unittest
import copy
import networkx as nx
from spikexplore import graph_explore
from spikexplore.backends.synthetic import SyntheticNetwork


class SyntheticGraphSamplingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        nodes = 5000
        edges_per_node = 5
        cls.G = nx.barabasi_albert_graph(nodes, edges_per_node)
        cls.sampling_backend = SyntheticNetwork(cls.G)
        cls.sampling_config = {
            "collection_settings": {
                "exploration_depth": 3,
                "mode": "percent",
                "random_subset_size": 20,
                "balltype": "coreball",
                "coeff": 2,
                "max_nodes_per_hop": 1000
            },
            "graph": {
                "min_weight": 1,
                "min_degree": 1,
            }
        }

    def test_sampling_coreball(self):
        g_sub = graph_explore.explore(self.sampling_backend, [1, 2], self.sampling_config)
        self.assertTrue(g_sub.number_of_nodes() > 50)
        self.assertTrue(g_sub.number_of_edges() > 100)
        self.assertTrue(nx.is_connected(g_sub.to_undirected()))

    def test_sampling_coreball_numnodes(self):
        cfg = copy.deepcopy(self.sampling_config)
        cfg['collection_settings']['number_of_nodes'] = 100
        cfg['collection_settings']['exploration_depth'] = 1000000
        g_sub = graph_explore.explore(self.sampling_backend, [1, 2], cfg)
        self.assertTrue(g_sub.number_of_nodes() == 100)
        self.assertTrue(g_sub.number_of_edges() > 100)
        self.assertTrue(nx.is_connected(g_sub.to_undirected()))

    def test_sampling_args_validation(self):
        self.assertRaises(ValueError, graph_explore.explore, self.sampling_backend, [], self.sampling_config)
        bad_cfg = copy.deepcopy(self.sampling_config)
        bad_cfg['collection_settings']['exploration_depth'] = 0
        self.assertRaises(ValueError, graph_explore.explore, self.sampling_backend, [1, 2, 3], bad_cfg)