from dataclasses import dataclass


@dataclass
class GraphConfig:
    min_weight: int = 1
    min_degree: int = 1
    community_detection: bool = False
    min_community_size: int = 1
    as_undirected: bool = True


@dataclass
class DataCollectionConfig:
    exploration_depth: int = 3
    random_subset_mode: str = "percent"
    random_subset_size: int = 20
    expansion_type: str = "coreball"
    degree: int = 2
    max_nodes_per_hop: int = 1000
    number_of_nodes: int = None


@dataclass
class SamplingConfig:
    graph = GraphConfig()  # graph construction parameters
    data_collection = DataCollectionConfig()  # spikyball parameters

    def __init__(self, graph, data_collection):
        self.graph = graph
        self.data_collection = data_collection


@dataclass
class BlueskyConfig:
    min_mentions: int = 0
    max_day_old: int = 30
    max_skeets_per_user: int = 100
    nb_popular_skeets: int = 10
    users_to_remove = []


@dataclass
class SyntheticConfig:
    min_degree: int = 1


@dataclass
class WikipediaConfig:
    user_agent: str = ""
    lang: str = "en"
    pages_ignored = []
