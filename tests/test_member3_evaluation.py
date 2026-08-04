import json
import os
import subprocess
import sys

import pytest

from group_project.evaluation import eval_pipeline


def golden_record(index=1):
    return {
        "id": f"labor_{index:03d}",
        "question": "Lương thử việc tối thiểu là bao nhiêu?",
        "expected_answer": "Ít nhất bằng 85% mức lương của công việc đó.",
        "ground_truth_context": "Điều 26 quy định tiền lương thử việc ít nhất bằng 85%.",
        "sources": [
            {
                "document": "Bộ luật Lao động 2019",
                "article": "Điều 26",
                "source_url": "https://vanban.chinhphu.vn/example",
            }
        ],
        "category": "thu_viec",
        "difficulty": "easy",
    }


def test_load_golden_dataset_validates_minimum_size(tmp_path):
    path = tmp_path / "golden.json"
    path.write_text(json.dumps([golden_record()]), encoding="utf-8")

    with pytest.raises(ValueError, match="ít nhất 15"):
        eval_pipeline.load_golden_dataset(path)


def test_load_golden_dataset_reports_missing_fields(tmp_path):
    records = [golden_record(i) for i in range(1, 16)]
    del records[4]["ground_truth_context"]
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(records), encoding="utf-8")

    with pytest.raises(ValueError, match="ground_truth_context"):
        eval_pipeline.load_golden_dataset(path)


def test_collect_evaluation_rows_normalizes_source_objects():
    records = [golden_record()]

    def pipeline(question, **config):
        assert config == {"use_reranking": True}
        return {
            "answer": "85% mức lương.",
            "sources": [{"content": "Điều 26 quy định mức 85%."}],
        }

    rows = eval_pipeline.collect_evaluation_rows(
        pipeline, records, {"use_reranking": True}
    )

    assert rows == [
        {
            "id": "labor_001",
            "question": "Lương thử việc tối thiểu là bao nhiêu?",
            "answer": "85% mức lương.",
            "contexts": ["Điều 26 quy định mức 85%."],
            "ground_truth": "Ít nhất bằng 85% mức lương của công việc đó.",
            "ground_truth_context": "Điều 26 quy định tiền lương thử việc ít nhất bằng 85%.",
            "category": "thu_viec",
        }
    ]


def test_collect_evaluation_rows_checkpoints_successes_and_continues_after_error(
    tmp_path,
):
    records = [golden_record(i) for i in range(1, 4)]
    checkpoint = tmp_path / "rows.json"
    records[0]["question"] = "Q1"
    records[1]["question"] = "Q2"
    records[2]["question"] = "Q3"

    def pipeline(question, **_config):
        if question == "Q2":
            raise RuntimeError("temporary timeout")
        return {"answer": f"answer {question}", "contexts": [f"context {question}"]}

    failures = []
    rows = eval_pipeline.collect_evaluation_rows(
        pipeline,
        records,
        {"use_reranking": True},
        checkpoint_path=checkpoint,
        failed_items=failures,
    )

    assert [row["id"] for row in rows] == ["labor_001", "labor_003"]
    assert failures == [
        {
            "id": "labor_002",
            "question": "Q2",
            "error_type": "RuntimeError",
            "error": "temporary timeout",
        }
    ]
    persisted = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert persisted["rows"] == rows
    assert persisted["failed_items"] == failures


def test_collect_evaluation_rows_resumes_only_missing_or_failed_items(tmp_path):
    records = [golden_record(i) for i in range(1, 4)]
    for index, record in enumerate(records, 1):
        record["question"] = f"Q{index}"
    checkpoint = tmp_path / "rows.json"
    checkpoint.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "id": "labor_001",
                        "question": "Q1",
                        "answer": "cached",
                        "contexts": ["cached context"],
                        "ground_truth": records[0]["expected_answer"],
                        "ground_truth_context": records[0]["ground_truth_context"],
                        "category": records[0]["category"],
                    }
                ],
                "failed_items": [
                    {"id": "labor_002", "question": "Q2", "error": "old error"}
                ],
            }
        ),
        encoding="utf-8",
    )
    called = []

    def pipeline(question, **_config):
        called.append(question)
        return {"answer": f"new {question}", "contexts": [f"context {question}"]}

    failures = []
    rows = eval_pipeline.collect_evaluation_rows(
        pipeline,
        records,
        {},
        checkpoint_path=checkpoint,
        failed_items=failures,
    )

    assert called == ["Q2", "Q3"]
    assert [row["id"] for row in rows] == ["labor_001", "labor_002", "labor_003"]
    assert failures == []


def test_run_ab_evaluation_keeps_raw_rows_when_ragas_fails(tmp_path, monkeypatch):
    records = [golden_record()]
    monkeypatch.setattr(eval_pipeline, "RAW_RESULTS_DIR", tmp_path)

    def pipeline(_question, **_config):
        return {"answer": "answer", "contexts": ["context"]}

    monkeypatch.setattr(
        eval_pipeline,
        "evaluate_with_ragas",
        lambda _rows: (_ for _ in ()).throw(RuntimeError("rate limited")),
    )

    with pytest.raises(RuntimeError, match="rate limited"):
        eval_pipeline.run_ab_evaluation(pipeline, records)

    checkpoint = tmp_path / "dense_no_rerank_rows.json"
    persisted = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert persisted["rows"][0]["id"] == "labor_001"


def test_compare_configs_computes_delta_and_worst_performers():
    evaluations = {
        "dense_no_rerank": {
            "scores": {
                "faithfulness": 0.6,
                "answer_relevancy": 0.7,
                "context_recall": 0.5,
                "context_precision": 0.4,
            },
            "rows": [
                {"id": "q1", "question": "Q1", "scores": {"faithfulness": 0.2}},
                {"id": "q2", "question": "Q2", "scores": {"faithfulness": 0.8}},
            ],
        },
        "hybrid_with_rerank": {
            "scores": {
                "faithfulness": 0.8,
                "answer_relevancy": 0.75,
                "context_recall": 0.7,
                "context_precision": 0.65,
            },
            "rows": [
                {
                    "id": "q1",
                    "question": "Q1",
                    "scores": {
                        "faithfulness": 0.3,
                        "answer_relevancy": 0.4,
                        "context_recall": 0.2,
                        "context_precision": 0.1,
                    },
                },
                {
                    "id": "q2",
                    "question": "Q2",
                    "scores": {
                        "faithfulness": 0.9,
                        "answer_relevancy": 0.9,
                        "context_recall": 0.8,
                        "context_precision": 0.8,
                    },
                },
            ],
        },
    }

    comparison = eval_pipeline.compare_configs(evaluations)

    assert comparison["metrics"]["faithfulness"]["delta"] == pytest.approx(0.2)
    assert comparison["winner"] == "hybrid_with_rerank"
    assert comparison["worst_performers"][0]["id"] == "q1"


def test_render_results_marks_pending_scores_without_inventing_numbers():
    markdown = eval_pipeline.render_results({})

    assert "Chưa chạy" in markdown
    assert "dense_no_rerank" in markdown
    assert "hybrid_with_rerank" in markdown


def test_render_results_reports_coverage_and_failed_items():
    comparison = {
        "metrics": {},
        "coverage": {
            "dense_no_rerank": {"successful": 19, "failed": 1, "total": 20},
            "hybrid_with_rerank": {"successful": 20, "failed": 0, "total": 20},
        },
        "failed_items": {
            "dense_no_rerank": [
                {
                    "id": "labor_010",
                    "question": "Khi nào phải thanh toán?",
                    "error_type": "TimeoutError",
                    "error": "PageIndex timeout",
                }
            ],
            "hybrid_with_rerank": [],
        },
    }

    markdown = eval_pipeline.render_results(comparison)

    assert "19/20" in markdown
    assert "labor_010" in markdown
    assert "TimeoutError: PageIndex timeout" in markdown


def test_module_cli_runs_on_windows_cp1252_console():
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "cp1252"

    completed = subprocess.run(
        [sys.executable, "-m", "group_project.evaluation.eval_pipeline"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "24 golden test cases" in completed.stdout
