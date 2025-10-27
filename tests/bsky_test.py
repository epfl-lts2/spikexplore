import os
import unittest
import networkx as nx
from spikexplore import graph_explore
from spikexplore.backends.bluesky import BlueskyNetwork, BlueskyCredentials
from spikexplore.config import SamplingConfig, GraphConfig, DataCollectionConfig, BlueskyConfig


class BlueskyGraphSampling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bsky_credentials = BlueskyCredentials(os.getenv("BSKY_HANDLE", ""), os.getenv("BSKY_PASSWORD", ""))

        cls.bluesky_config = BlueskyConfig()
        cls.bluesky_config.users_to_remove = ["threader_app", "threadreaderapp"]
        cls.sampling_backend = BlueskyNetwork(bsky_credentials, cls.bluesky_config)

        graph_config = GraphConfig(min_degree=2, min_weight=1, community_detection=True, min_community_size=2, as_undirected=False)
        data_collection_config = DataCollectionConfig(
            exploration_depth=2, random_subset_mode="percent", random_subset_size=60, expansion_type="coreball", degree=2, max_nodes_per_hop=100
        )
        cls.sampling_config = SamplingConfig(graph_config, data_collection_config)
        cls.initial_nodes = ["atproto.com", "bsky.app", "jay.bsky.team", "atprotocol.dev", "freeourfeeds.com"]

    def test_sampling_coreball(self):
        g_sub, nodes_info = graph_explore.explore(self.sampling_backend, self.initial_nodes, self.sampling_config)
        self.assertGreaterEqual(g_sub.number_of_nodes(), 5)
        self.assertGreaterEqual(g_sub.number_of_edges(), 10)
        communities = nx.get_node_attributes(g_sub, "community")
        self.assertGreaterEqual(max(communities.values()), 2)
        self.assertFalse(nodes_info.skeets_meta.empty)

    def test_empty_graph(self):
        g_sub, _ = graph_explore.explore(self.sampling_backend, ["#InvalidUsername"], self.sampling_config)
        self.assertEqual(g_sub.number_of_nodes(), 0)
        self.assertEqual(g_sub.number_of_edges(), 0)
