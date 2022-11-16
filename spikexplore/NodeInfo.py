class NodeInfo:  # abstract interface
    def update(self, new_info):
        raise NotImplementedError

    def get_nodes(self):
        raise NotImplementedError
