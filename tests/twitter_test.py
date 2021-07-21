import os
import unittest
import networkx as nx
from spikexplore import graph_explore
from spikexplore.backends.twitter import TwitterNetwork, TwitterCredentials
from spikexplore.config import SamplingConfig, GraphConfig, DataCollectionConfig, TwitterConfig


class TwitterGraphSampling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.twitter_config = TwitterConfig()
        cls.twitter_config.users_to_remove = ['threader_app', 'threadreaderapp']
        cls.twitter_config.api_version = 1
        twitter_credentials = TwitterCredentials(os.getenv('TWITTER_APP_KEY', ''), os.getenv('TWITTER_ACCESS_TOKEN', ''))

        cls.sampling_backend = TwitterNetwork(twitter_credentials, cls.twitter_config)
        graph_config = GraphConfig(min_degree=2, min_weight=2, community_detection=True, min_community_size=2, as_undirected=False)
        data_collection_config = DataCollectionConfig(exploration_depth=2, random_subset_mode="percent",
                                                      random_subset_size=10, expansion_type="coreball",
                                                      degree=2, max_nodes_per_hop=100)
        cls.sampling_config = SamplingConfig(graph_config, data_collection_config)
        cls.initial_nodes = ['github', 'Microsoft', 'GitHubSecurity', 'GitHubEducation']

    def test_sampling_coreball(self):
        g_sub, _ = graph_explore.explore(self.sampling_backend, self.initial_nodes, self.sampling_config)
        self.assertTrue(g_sub.number_of_nodes() > 5)
        self.assertTrue(g_sub.number_of_edges() > 10)
        communities = nx.get_node_attributes(g_sub, 'community')
        self.assertGreaterEqual(max(communities.values()), 2)
