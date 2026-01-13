"""Accuracy metrics for benchmarking."""

from collections import defaultdict
from typing import Dict, List, Optional


class AccuracyMetrics:
    """Collects and computes accuracy metrics."""

    def __init__(self):
        self.total: int = 0
        self.correct: int = 0
        self.by_type: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "correct": 0}
        )
        self.ranks: List[Optional[int]] = []

    def add_result(
        self,
        correct: bool,
        question_type: str,
        rank: Optional[int] = None,
    ) -> None:
        """
        Add a result to the metrics.

        Args:
            correct: Whether the answer was correct (found at rank 1)
            question_type: Type of question (single_hop, multi_hop, etc.)
            rank: Rank at which correct answer was found (None if not found)
        """
        self.total += 1
        if correct:
            self.correct += 1

        self.by_type[question_type]["total"] += 1
        if correct:
            self.by_type[question_type]["correct"] += 1

        self.ranks.append(rank)

    def get_accuracy(self) -> float:
        """Get overall accuracy (proportion correct at rank 1)."""
        if self.total == 0:
            return 0.0
        return self.correct / self.total

    def get_accuracy_by_type(self) -> Dict[str, float]:
        """Get accuracy broken down by question type."""
        result = {}
        for qtype, counts in self.by_type.items():
            if counts["total"] > 0:
                result[qtype] = counts["correct"] / counts["total"]
            else:
                result[qtype] = 0.0
        return result

    def get_mrr(self) -> float:
        """
        Calculate Mean Reciprocal Rank.

        MRR = (1/|Q|) * sum(1/rank_i) for all queries where answer was found
        """
        if not self.ranks:
            return 0.0

        reciprocal_ranks = []
        for rank in self.ranks:
            if rank is not None and rank > 0:
                reciprocal_ranks.append(1.0 / rank)
            else:
                reciprocal_ranks.append(0.0)

        return sum(reciprocal_ranks) / len(reciprocal_ranks)

    def get_recall_at_k(self, k: int) -> float:
        """
        Calculate Recall@k.

        Proportion of queries where correct answer was found within top k results.
        """
        if not self.ranks:
            return 0.0

        found_within_k = sum(1 for rank in self.ranks if rank is not None and rank <= k)
        return found_within_k / len(self.ranks)

    def get_summary(self) -> Dict[str, any]:
        """Get a summary of all accuracy metrics."""
        return {
            "total_questions": self.total,
            "correct_at_1": self.correct,
            "accuracy": self.get_accuracy(),
            "accuracy_by_type": self.get_accuracy_by_type(),
            "mrr": self.get_mrr(),
            "recall_at_1": self.get_recall_at_k(1),
            "recall_at_3": self.get_recall_at_k(3),
            "recall_at_5": self.get_recall_at_k(5),
            "recall_at_10": self.get_recall_at_k(10),
        }
