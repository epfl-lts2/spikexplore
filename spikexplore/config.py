from dataclasses import dataclass


@dataclass
class GraphConfig:
    min_weight: int = 1
    min_degree: int = 1


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