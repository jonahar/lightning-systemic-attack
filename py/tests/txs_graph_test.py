import unittest

from networkx import DiGraph

from txs_graph import get_downstream


class TxsGraphTest(unittest.TestCase):
    def test_downstream_1(self):
        graph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", "e")
        graph.add_edge("e", "d")
        graph.add_edge("d", "b")
        graph.add_edge("e", "f")
        
        downstream = get_downstream(graph, sources={"a"})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {"a", "b", "c", "d", "e", "f"})
        
        downstream = get_downstream(graph, sources={"b", "e"})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {"b", "c", "d", "e", "f"})
        
        downstream = get_downstream(graph, sources={"e"})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {"b", "c", "d", "e", "f"})
        
        downstream = get_downstream(graph, sources={"f"})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {"f"})
    
    def test_downstream_2(self):
        graph = DiGraph()
        graph.add_edge(1, 3)
        graph.add_edge(1, 4)
        graph.add_edge(2, 4)
        graph.add_edge(2, 5)
        graph.add_edge(4, 6)
        graph.add_edge(5, 6)
        
        downstream = get_downstream(graph, sources={1, 2})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {1, 2, 3, 4, 5, 6})
        
        downstream = get_downstream(graph, sources={2})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {2, 4, 5, 6})
        
        downstream = get_downstream(graph, sources={3, 4})
        downstream_nodes = set(downstream.nodes)
        self.assertSetEqual(downstream_nodes, {3, 4, 6})


if __name__ == '__main__':
    unittest.main()
