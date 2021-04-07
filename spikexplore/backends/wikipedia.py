import wikipediaapi
import pandas as pd
from spikexplore.NodeInfo import NodeInfo
from spikexplore.graph import add_node_attributes, add_edges_attributes


class WikipediaNetwork:
    class WikipediaNodeInfo(NodeInfo):
        def __init__(self, page_info={}, nodes_df=pd.DataFrame()):
            self.page_info = page_info
            self.nodes_df = nodes_df

        def update(self, new_info):
            self.page_info.update(new_info.page_info)
            return

        def get_nodes(self):
            return self.nodes_df

    def __init__(self, config):
        self.api = wikipediaapi.Wikipedia(config.lang)
        self.config = config

    def get_node_info(self):
        return self.WikipediaNodeInfo()

    def get_neighbors(self, page):
        if not isinstance(page, str):
            return self.WikipediaNodeInfo(), pd.DataFrame()
        p = self.api.page(page)
        links = list(p.links.keys())
        ns = [v.namespace for k, v in p.links.items()]
        edges_df = pd.DataFrame(links, columns=['target'])
        edges_df['source'] = p.title
        edges_df = edges_df.reindex(columns=['source', 'target'])

        edges_df['weight'] = 1.0
        edges_df['target_ns'] = ns

        node_info = self.WikipediaNodeInfo({p.title: []}, pd.DataFrame([p.title], columns=['title']))
        return node_info, edges_df

    def neighbors_list(self, edges_df):
        if edges_df.empty:
            return edges_df
        pages_connected = edges_df['target'].tolist()
        return pages_connected

    def neighbors_with_weights(self, edges_df):
        pages_list = self.neighbors_list(edges_df)
        return dict.fromkeys(pages_list, 1)

    def filter(self, node_info, edges_df):
        edges_bl_df = edges_df[~edges_df['target'].isin(self.config.pages_ignored)]
        edges_df_filt = edges_bl_df[edges_bl_df['target_ns'] == 0]  # only keep links to articles
        return node_info, edges_df_filt

    def reshape_node_data(self, nodes_df):
        nodes_df.set_index('title', inplace=True)
        return nodes_df

    def add_graph_attributes(self, g, nodes_df, edges_df, nodes_info):
        g = add_edges_attributes(g, edges_df)
        g = add_node_attributes(g, self.reshape_node_data(nodes_df))
        return g
