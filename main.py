"""Three-stage public pipeline: prepare -> generate -> select.

Run from the repository root; no dataset is bundled with this project.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from concept_distractors.generation import CandidateGenerator
from concept_distractors.graph import KnowledgeGraph
from concept_distractors.prior import prepare_item
from concept_distractors.ranking import HybridSimilarity, QualityConfig, rank_item
from concept_distractors.utils import read_items, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Knowledge-graph / confusion-prior distractor generation")
    commands = parser.add_subparsers(dest="stage", required=True)
    prepare = commands.add_parser("prepare", help="构建混淆先验与局部图谱上下文")
    prepare.add_argument("--input", required=True, help="原始问题 JSON 数组")
    prepare.add_argument("--nodes", required=True, help="知识图谱节点 CSV")
    prepare.add_argument("--edges", required=True, help="知识图谱关系 CSV")
    prepare.add_argument("--hop", type=int, default=2, choices=(1, 2, 3, 4))
    prepare.add_argument("--output", required=True)

    generate = commands.add_parser("generate", help="基于完整约束提示词过生成候选项")
    generate.add_argument("--input", required=True)
    generate.add_argument("--output", required=True)
    generate.add_argument("--model", required=True, help="你已获授权调用的模型标识")
    generate.add_argument("--temperature", type=float, default=0.3)
    generate.add_argument("--candidate-count", type=int, default=12)
    generate.add_argument("--rounds", type=int, default=2)

    select = commands.add_parser("select", help="四维评分 + 动态门控 + Top-3 去冗余")
    select.add_argument("--input", required=True)
    select.add_argument("--output", required=True)
    select.add_argument("--gate-percentile", type=float, default=20.0)
    select.add_argument("--local-embedding-model", help="可选：本地模型文件夹，不自动下载")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    records = read_items(args.input)
    if args.stage == "prepare":
        graph = KnowledgeGraph.load(args.nodes, args.edges)
        result = [prepare_item(item, graph, hop=args.hop) for item in records]
    elif args.stage == "generate":
        if not 1 <= args.candidate_count <= 32 or not 1 <= args.rounds <= 5:
            raise ValueError("候选数量需在 1~32，生成轮数需在 1~5。")
        generator = CandidateGenerator(args.model, args.temperature, max_rounds=args.rounds)
        result = [generator.generate(item, target=args.candidate_count) for item in records]
    else:
        similarity = HybridSimilarity(local_embedding_model=args.local_embedding_model)
        cfg = QualityConfig(gate_percentile=args.gate_percentile)
        result = [rank_item(item, similarity, config=cfg) for item in records]
    write_json(args.output, result)
    print(f"{args.stage}: processed {len(result)} items. Output written to {args.output}")


if __name__ == "__main__":
    main()
