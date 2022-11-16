import unittest
import networkx as nx
from spikexplore import graph_explore
from spikexplore.backends.wikipedia import WikipediaNetwork
from spikexplore.config import SamplingConfig, GraphConfig, DataCollectionConfig, WikipediaConfig


class WikipediaGraphSampling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wiki_config = WikipediaConfig(lang='en')
        #  Partial ignore list of not so interesting identifiers
        #  A huge number of pages link to those...
        cls.wiki_config.pages_ignored = ["BNF (identifier)",
                                         "Bibcode (identifier)",
                                         "CANTIC (identifier)",
                                         "CiNii (identifier)",
                                         "BNE (identifier)",
                                         "BIBSYS (identifier)",
                                         "ArXiv (identifier)",
                                         "Doi (identifier)",
                                         "ISBN (identifier)",
                                         "PMC (identifier)",
                                         "PMID (identifier)",
                                         "NDL (identifier)",
                                         "NKC (identifier)",
                                         "NLA (identifier)",
                                         "NLI (identifier)",
                                         "NLK (identifier)",
                                         "LCCN (identifier)",
                                         "LNB (identifier)",
                                         "MGP (identifier)",
                                         "NLP (identifier)"]

        cls.sampling_backend = WikipediaNetwork(cls.wiki_config)
        graph_config = GraphConfig(min_degree=1, min_weight=1, community_detection=False)
        data_collection_config = DataCollectionConfig(exploration_depth=2, random_subset_mode="percent",
                                                      random_subset_size=10, expansion_type="coreball",
                                                      degree=2, max_nodes_per_hop=100)
        cls.sampling_config = SamplingConfig(graph_config, data_collection_config)
        cls.initial_nodes = ['Albert Einstein', 'Quantum mechanics', 'Theory of relativity']

    def test_sampling_coreball(self):
        g_sub, _ = graph_explore.explore(self.sampling_backend, self.initial_nodes, self.sampling_config)
        self.assertTrue(g_sub.number_of_nodes() > 100)
        self.assertTrue(g_sub.number_of_edges() > 700)
        self.assertTrue(nx.is_connected(g_sub))
        self.assertTrue(set(g_sub.nodes()).intersection(self.wiki_config.pages_ignored) == set())

    def test_empty_graph(self):
        g_sub, _ = graph_explore.explore(self.sampling_backend, ['Non existent page of wikipedia forever'], self.sampling_config)
        self.assertTrue(g_sub.number_of_nodes() == 0)
        self.assertTrue(g_sub.number_of_edges() == 0)
