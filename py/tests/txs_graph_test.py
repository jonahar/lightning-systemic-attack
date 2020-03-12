import unittest

from txs_graph.txs_graph import TxsGraph


class TxsGraphTest(unittest.TestCase):
    
    def get_test_graph_1(self) -> TxsGraph:
        graph = TxsGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", "e")
        graph.add_edge("e", "d")
        graph.add_edge("d", "b")
        graph.add_edge("e", "f")
        return graph
    
    def test_downstream_1_1(self):
        graph = self.get_test_graph_1()
        downstream = graph.get_downstream(sources={"a"})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {"a", "b", "c", "d", "e", "f"})
    
    def test_downstream_1_2(self):
        graph = self.get_test_graph_1()
        downstream = graph.get_downstream(sources={"b", "e"})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {"b", "c", "d", "e", "f"})
    
    def test_downstream_1_3(self):
        graph = self.get_test_graph_1()
        downstream = graph.get_downstream(sources={"e"})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {"b", "c", "d", "e", "f"})
    
    def test_downstream_1_4(self):
        graph = self.get_test_graph_1()
        downstream = graph.get_downstream(sources={"f"})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {"f"})
    
    def get_test_graph_2(self) -> TxsGraph:
        graph = TxsGraph()
        graph.add_edge(1, 3)
        graph.add_edge(1, 4)
        graph.add_edge(2, 4)
        graph.add_edge(2, 5)
        graph.add_edge(4, 6)
        graph.add_edge(5, 6)
        return graph
    
    def test_downstream_2_1(self):
        graph = self.get_test_graph_2()
        downstream = graph.get_downstream(sources={1, 2})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {1, 2, 3, 4, 5, 6})
    
    def test_downstream_2_2(self):
        graph = self.get_test_graph_2()
        downstream = graph.get_downstream(sources={2})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {2, 4, 5, 6})
    
    def test_downstream_2_3(self):
        graph = self.get_test_graph_2()
        downstream = graph.get_downstream(sources={3, 4})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {3, 4, 6})


if __name__ == '__main__':
    unittest.main()
