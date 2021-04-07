import unittest
import copy
import networkx as nx
from spikexplore import graph_explore
from spikexplore.backends.synthetic import SyntheticNetwork
from spikexplore.config import SamplingConfig, GraphConfig, DataCollectionConfig, SyntheticConfig


class SyntheticGraphSamplingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        nodes = 5000
        edges_per_node = 5
        cls.config = SyntheticConfig()
        cls.G = nx.barabasi_albert_graph(nodes, edges_per_node)
        cls.sampling_backend = SyntheticNetwork(cls.G, cls.config)
        graph_config = GraphConfig(min_degree=1, min_weight=1)
        data_collection_config = DataCollectionConfig(exploration_depth=3, random_subset_mode="percent",
                                                      random_subset_size=20, expansion_type="coreball",
                                                      degree=2, max_nodes_per_hop=1000)
        cls.sampling_config = SamplingConfig(graph_config, data_collection_config)

    def test_sampling_coreball(self):
        g_sub = graph_explore.explore(self.sampling_backend, [1, 2], self.sampling_config)
        self.assertTrue(g_sub.number_of_nodes() > 50)
        self.assertTrue(g_sub.number_of_edges() > 100)
        self.assertTrue(nx.is_connected(g_sub))

    def test_sampling_coreball_numnodes(self):
        cfg = copy.deepcopy(self.sampling_config)
        cfg.data_collection.number_of_nodes = 100
        cfg.data_collection.exploration_depth = 1000000
        g_sub = graph_explore.explore(self.sampling_backend, [1, 2], cfg)
        self.assertTrue(g_sub.number_of_nodes() == 100)
        self.assertTrue(g_sub.number_of_edges() > 100)
        self.assertTrue(nx.is_connected(g_sub))

    def test_sampling_args_validation(self):
        self.assertRaises(ValueError, graph_explore.explore, self.sampling_backend, [], self.sampling_config)
        bad_cfg = copy.deepcopy(self.sampling_config)
        bad_cfg.data_collection.exploration_depth = 0
        self.assertRaises(ValueError, graph_explore.explore, self.sampling_backend, [1, 2, 3], bad_cfg)
        bad_cfg.data_collection.exploration_depth = 3
        bad_cfg.data_collection.expansion_type = "unknown"
        self.assertRaises(ValueError, graph_explore.explore, self.sampling_backend, [1, 2, 3], bad_cfg)
        bad_cfg.data_collection.expansion_type = "fireball"
        bad_cfg.data_collection.random_subset_mode = "invalid"
        self.assertRaises(ValueError, graph_explore.explore, self.sampling_backend, [1, 2, 3], bad_cfg)
        bad_cfg.data_collection.random_subset_mode = "percent"
        bad_cfg.data_collection.random_subset_size = 102
        self.assertRaises(ValueError, graph_explore.explore, self.sampling_backend, [1, 2, 3], bad_cfg)
