import sys
import types

from src import task10_generation


def test_generation_passes_reranking_choice_to_retrieval(monkeypatch):
    calls = []

    def fake_retrieve(query, top_k, use_reranking):
        calls.append((query, top_k, use_reranking))
        return []

    fake_module = types.ModuleType("src.task9_retrieval_pipeline")
    fake_module.retrieve = fake_retrieve
    monkeypatch.setitem(sys.modules, "src.task9_retrieval_pipeline", fake_module)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = task10_generation.generate_with_citation(
        "Lương thử việc?", top_k=3, use_reranking=False
    )

    assert calls == [("Lương thử việc?", 3, False)]
    assert result["sources"] == []
