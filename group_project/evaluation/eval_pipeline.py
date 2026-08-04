"""RAGAS evaluation and A/B comparison for the labor-law RAG pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any, Callable

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"
RAW_RESULTS_DIR = Path(__file__).parent / "artifacts"
METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_recall",
    "context_precision",
)
CONFIGS = {
    "dense_no_rerank": {"use_reranking": False},
    "hybrid_with_rerank": {"use_reranking": True},
}
REQUIRED_FIELDS = {
    "id",
    "question",
    "expected_answer",
    "ground_truth_context",
    "sources",
    "category",
    "difficulty",
}


def load_golden_dataset(
    path: str | Path = GOLDEN_DATASET_PATH, minimum_size: int = 15
) -> list[dict]:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Golden dataset phải là một JSON array")
    if len(records) < minimum_size:
        raise ValueError(f"Golden dataset cần ít nhất {minimum_size} bản ghi")
    seen_ids: set[str] = set()
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise ValueError(f"Bản ghi {index} phải là object")
        missing = REQUIRED_FIELDS - record.keys()
        if missing:
            raise ValueError(f"Bản ghi {index} thiếu: {', '.join(sorted(missing))}")
        if not all(str(record[field]).strip() for field in REQUIRED_FIELDS - {"sources"}):
            raise ValueError(f"Bản ghi {index} có trường bắt buộc rỗng")
        if not isinstance(record["sources"], list) or not record["sources"]:
            raise ValueError(f"Bản ghi {index} phải có ít nhất một source")
        if record["id"] in seen_ids:
            raise ValueError(f"ID bị trùng: {record['id']}")
        seen_ids.add(record["id"])
    return records


def _extract_contexts(result: dict) -> list[str]:
    contexts = result.get("contexts")
    if contexts is None:
        contexts = result.get("sources", [])
    normalized = []
    for context in contexts:
        text = context.get("content", "") if isinstance(context, dict) else str(context)
        if text.strip():
            normalized.append(text.strip())
    return normalized


def collect_evaluation_rows(
    pipeline: Callable[..., dict],
    golden_dataset: list[dict],
    config: dict,
    checkpoint_path: str | Path | None = None,
    failed_items: list[dict] | None = None,
) -> list[dict]:
    checkpoint = Path(checkpoint_path) if checkpoint_path else None
    cached = {"rows": [], "failed_items": []}
    if checkpoint and checkpoint.exists():
        cached = json.loads(checkpoint.read_text(encoding="utf-8"))
    rows_by_id = {row["id"]: row for row in cached.get("rows", [])}
    failures_by_id = {
        failure["id"]: failure for failure in cached.get("failed_items", [])
    }

    def persist() -> None:
        if not checkpoint:
            return
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rows": list(rows_by_id.values()),
            "failed_items": list(failures_by_id.values()),
        }
        temporary = checkpoint.with_suffix(checkpoint.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(checkpoint)

    for item in golden_dataset:
        if item["id"] in rows_by_id:
            continue
        try:
            result = pipeline(item["question"], **config)
            if not isinstance(result, dict) or not str(result.get("answer", "")).strip():
                raise ValueError("Pipeline phải trả dict có trường answer không rỗng")
            contexts = _extract_contexts(result)
            if not contexts:
                raise ValueError("Pipeline phải trả contexts hoặc sources có content")
            rows_by_id[item["id"]] = {
                "id": item["id"],
                "question": item["question"],
                "answer": result["answer"],
                "contexts": contexts,
                "ground_truth": item["expected_answer"],
                "ground_truth_context": item["ground_truth_context"],
                "category": item["category"],
            }
            failures_by_id.pop(item["id"], None)
        except Exception as error:
            failures_by_id[item["id"]] = {
                "id": item["id"],
                "question": item["question"],
                "error_type": type(error).__name__,
                "error": str(error),
            }
        persist()

    if failed_items is not None:
        failed_items[:] = list(failures_by_id.values())
    ordered_ids = [item["id"] for item in golden_dataset]
    return [rows_by_id[item_id] for item_id in ordered_ids if item_id in rows_by_id]


def evaluate_with_ragas(rows: list[dict]) -> dict:
    """Run four RAGAS 0.1.x metrics and retain aggregate and per-row scores."""
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    dataset = Dataset.from_dict(
        {
            "question": [row["question"] for row in rows],
            "answer": [row["answer"] for row in rows],
            "contexts": [row["contexts"] for row in rows],
            "ground_truth": [row["ground_truth"] for row in rows],
        }
    )
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
    )
    frame = result.to_pandas()
    scored_rows = []
    for source_row, (_, measured) in zip(rows, frame.iterrows()):
        scored = dict(source_row)
        scored["scores"] = {
            metric: float(measured[metric]) for metric in METRICS
        }
        scored_rows.append(scored)
    return {
        "scores": {metric: float(frame[metric].mean()) for metric in METRICS},
        "rows": scored_rows,
    }


def run_ab_evaluation(
    pipeline: Callable[..., dict], golden_dataset: list[dict]
) -> dict:
    evaluations = {}
    for name, config in CONFIGS.items():
        failed_items: list[dict] = []
        checkpoint = RAW_RESULTS_DIR / f"{name}_rows.json"
        rows = collect_evaluation_rows(
            pipeline,
            golden_dataset,
            config,
            checkpoint_path=checkpoint,
            failed_items=failed_items,
        )
        if not rows:
            raise RuntimeError(f"Cấu hình {name} không thu thập được câu trả lời nào")
        evaluation = evaluate_with_ragas(rows)
        evaluation["failed_items"] = failed_items
        evaluation["coverage"] = {
            "successful": len(rows),
            "failed": len(failed_items),
            "total": len(golden_dataset),
        }
        evaluations[name] = evaluation
    return evaluations


def _row_average(row: dict) -> float:
    values = [float(row.get("scores", {}).get(metric, 0.0)) for metric in METRICS]
    return mean(values)


def compare_configs(evaluations: dict) -> dict:
    if not evaluations:
        return {}
    names = list(CONFIGS)
    if any(name not in evaluations for name in names):
        raise ValueError(f"Cần kết quả cho hai cấu hình: {', '.join(names)}")
    baseline, candidate = names
    metrics = {}
    for metric in METRICS:
        score_a = float(evaluations[baseline]["scores"][metric])
        score_b = float(evaluations[candidate]["scores"][metric])
        metrics[metric] = {baseline: score_a, candidate: score_b, "delta": score_b - score_a}
    averages = {
        name: mean(float(evaluations[name]["scores"][metric]) for metric in METRICS)
        for name in names
    }
    worst = sorted(evaluations[candidate].get("rows", []), key=_row_average)[:3]
    return {
        "metrics": metrics,
        "averages": averages,
        "winner": max(averages, key=averages.get),
        "worst_performers": worst,
        "coverage": {name: evaluations[name].get("coverage", {}) for name in names},
        "failed_items": {
            name: evaluations[name].get("failed_items", []) for name in names
        },
    }


def render_results(comparison: dict) -> str:
    lines = [
        "# RAG Evaluation Results",
        "",
        "## Trạng thái",
        "",
        "Chưa chạy evaluation thật; bảng dưới đây sẽ được cập nhật sau khi Task 9/10 trả `answer` và `contexts`.",
        "",
        "## Cấu hình A/B",
        "",
        "- `dense_no_rerank`: Dense-only retrieval, không RRF reranking.",
        "- `hybrid_with_rerank`: Dense + sparse retrieval, hợp nhất bằng RRF.",
        "",
        "## Overall Scores",
        "",
        "| Metric | dense_no_rerank | hybrid_with_rerank | Δ |",
        "|---|---:|---:|---:|",
    ]
    metric_data = comparison.get("metrics", {})
    for metric in METRICS:
        values = metric_data.get(metric)
        if values:
            lines.append(
                f"| {metric} | {values['dense_no_rerank']:.4f} | "
                f"{values['hybrid_with_rerank']:.4f} | {values['delta']:+.4f} |"
            )
        else:
            lines.append(f"| {metric} | Chưa chạy | Chưa chạy | Chưa chạy |")
    lines.extend(["", "## Coverage và lỗi thu thập", ""])
    coverage = comparison.get("coverage", {})
    failed_by_config = comparison.get("failed_items", {})
    if not coverage:
        lines.append("Chưa có dữ liệu coverage.")
    else:
        lines.extend(
            [
                "| Config | Thành công | Lỗi | Tổng |",
                "|---|---:|---:|---:|",
            ]
        )
        for name in CONFIGS:
            values = coverage.get(name, {})
            successful = values.get("successful", 0)
            failed = values.get("failed", 0)
            total = values.get("total", successful + failed)
            lines.append(f"| {name} | {successful}/{total} | {failed} | {total} |")
    all_failures = [
        (name, failure)
        for name, failures in failed_by_config.items()
        for failure in failures
    ]
    if all_failures:
        lines.extend(
            [
                "",
                "| Config | ID | Question | Error |",
                "|---|---|---|---|",
            ]
        )
        for name, failure in all_failures:
            question = str(failure.get("question", "")).replace("|", "\\|")
            error = (
                f"{failure.get('error_type', 'Error')}: {failure.get('error', '')}"
            ).replace("|", "\\|")
            lines.append(
                f"| {name} | {failure.get('id', '')} | {question} | {error} |"
            )
    lines.extend(["", "## Worst Performers", ""])
    worst = comparison.get("worst_performers", [])
    if not worst:
        lines.append("Chưa có dữ liệu. Không sử dụng số liệu giả.")
    else:
        lines.extend(["| ID | Question | Average |", "|---|---|---:|"])
        for row in worst:
            lines.append(f"| {row['id']} | {row['question']} | {_row_average(row):.4f} |")
    lines.extend(
        [
            "",
            "## Phân tích cần hoàn thiện sau khi chạy",
            "",
            "Với từng câu thuộc bottom 3, đối chiếu context truy xuất với ground-truth context để phân loại lỗi retrieval, reranking hoặc generation.",
            "",
        ]
    )
    return "\n".join(lines)


def export_results(comparison: dict, path: str | Path = RESULTS_PATH) -> Path:
    output = Path(path)
    output.write_text(render_results(comparison), encoding="utf-8")
    return output


if __name__ == "__main__":
    records = load_golden_dataset()
    # Keep CLI status ASCII-safe for the default Windows CP1252 console.
    print(f"Validated {len(records)} golden test cases.")
    print("Pass a Task 9/10 adapter to run_ab_evaluation() to measure scores.")
