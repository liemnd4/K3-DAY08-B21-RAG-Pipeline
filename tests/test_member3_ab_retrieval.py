import importlib
import sys
import types


def load_task9(monkeypatch, calls):
    dense = [
        {"content": "dense", "score": 0.9, "metadata": {}},
        {"content": "dense-2", "score": 0.8, "metadata": {}},
    ]
    sparse = [{"content": "sparse", "score": 4.2, "metadata": {}}]

    semantic_module = types.ModuleType("src.task5_semantic_search")
    semantic_module.semantic_search = lambda *_args, **_kwargs: list(dense)
    lexical_module = types.ModuleType("src.task6_lexical_search")
    lexical_module.lexical_search = lambda *_args, **_kwargs: list(sparse)
    reranking_module = types.ModuleType("src.task7_reranking")

    def fake_rrf(ranked_lists, top_k):
        calls.append((ranked_lists, top_k))
        return [{"content": "rrf", "score": 0.02, "metadata": {}}]

    reranking_module.rerank_rrf = fake_rrf
    reranking_module.rerank = lambda *_args, **_kwargs: []
    pageindex_module = types.ModuleType("src.task8_pageindex_vectorless")
    pageindex_module.pageindex_search = lambda *_args, **_kwargs: []

    monkeypatch.setitem(sys.modules, "src.task5_semantic_search", semantic_module)
    monkeypatch.setitem(sys.modules, "src.task6_lexical_search", lexical_module)
    monkeypatch.setitem(sys.modules, "src.task7_reranking", reranking_module)
    monkeypatch.setitem(sys.modules, "src.task8_pageindex_vectorless", pageindex_module)
    sys.modules.pop("src.task9_retrieval_pipeline", None)
    return importlib.import_module("src.task9_retrieval_pipeline")


def test_no_reranking_configuration_is_dense_only(monkeypatch):
    calls = []
    task9 = load_task9(monkeypatch, calls)

    results = task9.retrieve(
        "query", top_k=1, score_threshold=0.0, use_reranking=False
    )

    assert calls == []
    assert results[0]["content"] == "dense"
    assert results[0]["source"] == "dense"


def test_reranking_configuration_uses_hybrid_rrf(monkeypatch):
    calls = []
    task9 = load_task9(monkeypatch, calls)

    results = task9.retrieve(
        "query", top_k=1, score_threshold=0.0, use_reranking=True
    )

    assert len(calls) == 1
    assert results[0]["content"] == "rrf"
    assert results[0]["source"] == "hybrid"
