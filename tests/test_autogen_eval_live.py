from archolith_bench.r1.autogen_eval import CorpusNode
from archolith_bench.r1.autogen_eval_live import Neo4jCorpusReader, normalized_tokens


def test_normalized_tokens_are_lane_neutral() -> None:
    assert normalized_tokens("Foo_bar, BAZ!") == frozenset({"foo", "bar", "baz"})


def test_duplicate_cluster_uses_token_jaccard() -> None:
    reader = Neo4jCorpusReader(driver=None)
    reader._nodes = [
        CorpusNode("a", "a", "alpha beta gamma"),
        CorpusNode("b", "b", "alpha beta gamma"),
        CorpusNode("c", "c", "unrelated memory"),
    ]
    reader._tokens = {node.uuid: normalized_tokens(node.text) for node in reader._nodes}
    assert reader.duplicate_cluster(reader._nodes[0], 0.9) == ["b"]
