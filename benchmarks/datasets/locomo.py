"""LoCoMo-MC10 dataset loader for benchmarking."""

from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class LoCoMoQuestion:
    """A single multiple-choice question from LoCoMo-MC10."""

    question_id: str
    question: str
    choices: List[str]
    correct_choice_index: int
    answer: str
    question_type: str  # single_hop, multi_hop, temporal_reasoning, open_domain, adversarial
    haystack_sessions: List[Any]
    haystack_session_summaries: List[str]
    haystack_session_datetimes: List[str]
    num_sessions: int


class LoCoMoDataset:
    """
    Loader for LoCoMo-MC10 dataset from HuggingFace.

    Dataset: Percena/locomo-mc10
    Contains 1,986 multiple-choice questions for evaluating memory systems.
    """

    DATASET_NAME = "Percena/locomo-mc10"

    def __init__(
        self,
        split: str = "train",
        question_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ):
        """
        Initialize the dataset loader.

        Args:
            split: Dataset split to use (default: "train")
            question_types: Filter by question types (None = all)
            limit: Maximum number of questions to load (None = all)
        """
        self.split = split
        self.question_types = question_types
        self.limit = limit
        self._questions: List[LoCoMoQuestion] = []
        self._loaded = False

    def load(self) -> None:
        """Load the dataset from HuggingFace."""
        from datasets import load_dataset

        print(f"Loading LoCoMo-MC10 dataset (split: {self.split})...")
        try:
            # Try loading with trust_remote_code to handle custom dataset scripts
            dataset = load_dataset(
                self.DATASET_NAME,
                split=self.split,
                trust_remote_code=True,
            )
        except Exception as e:
            # If that fails, try loading only the main data file
            print(f"Initial load failed: {e}")
            print("Attempting to load with specific data file...")
            dataset = load_dataset(
                self.DATASET_NAME,
                split=self.split,
                data_files="data/locomo_mc10.json",
                trust_remote_code=True,
            )

        count = 0
        for idx, item in enumerate(dataset):
            # Check limit
            if self.limit and count >= self.limit:
                break

            # Filter by question type
            if self.question_types and item["question_type"] not in self.question_types:
                continue

            question = LoCoMoQuestion(
                question_id=f"q_{idx}",
                question=item["question"],
                choices=item["choices"],
                correct_choice_index=item["correct_choice_index"],
                answer=item["answer"],
                question_type=item["question_type"],
                haystack_sessions=item.get("haystack_sessions", []),
                haystack_session_summaries=item.get("haystack_session_summaries", []),
                haystack_session_datetimes=item.get("haystack_session_datetimes", []),
                num_sessions=item.get("num_sessions", 0),
            )
            self._questions.append(question)
            count += 1

        self._loaded = True
        print(f"Loaded {len(self._questions)} questions")

        # Print distribution by type
        type_counts: Dict[str, int] = {}
        for q in self._questions:
            type_counts[q.question_type] = type_counts.get(q.question_type, 0) + 1
        print("Question type distribution:")
        for qtype, count in sorted(type_counts.items()):
            print(f"  {qtype}: {count}")

    def __len__(self) -> int:
        """Return the number of questions."""
        return len(self._questions)

    def __iter__(self) -> Iterator[LoCoMoQuestion]:
        """Iterate over questions."""
        return iter(self._questions)

    def __getitem__(self, idx: int) -> LoCoMoQuestion:
        """Get a question by index."""
        return self._questions[idx]

    def format_sessions_as_conversations(self, question: LoCoMoQuestion) -> List[str]:
        """
        Format haystack sessions as conversation strings for ingestion.

        Args:
            question: Question containing haystack sessions

        Returns:
            List of conversation strings
        """
        conversations = []

        for session_idx, session in enumerate(question.haystack_sessions):
            turns = []

            # Handle different session formats
            if isinstance(session, list):
                for turn in session:
                    if isinstance(turn, dict):
                        speaker = turn.get("speaker", turn.get("role", "unknown"))
                        text = turn.get("text", turn.get("content", turn.get("utterance", "")))
                        if text:
                            turns.append(f"{speaker}: {text}")
                    elif isinstance(turn, str):
                        turns.append(turn)
            elif isinstance(session, dict):
                # Handle dict-style sessions
                if "turns" in session:
                    for turn in session["turns"]:
                        if isinstance(turn, dict):
                            speaker = turn.get("speaker", "unknown")
                            text = turn.get("text", turn.get("content", ""))
                            if text:
                                turns.append(f"{speaker}: {text}")

            if turns:
                # Add session metadata if available
                session_header = ""
                if session_idx < len(question.haystack_session_datetimes):
                    session_header = f"[Session {session_idx + 1} - {question.haystack_session_datetimes[session_idx]}]\n"

                conversation = session_header + "\n".join(turns)
                conversations.append(conversation)

        return conversations

    def get_session_summaries(self, question: LoCoMoQuestion) -> List[str]:
        """
        Get session summaries for a question.

        Args:
            question: Question containing session summaries

        Returns:
            List of summary strings
        """
        return question.haystack_session_summaries

    @property
    def question_type_counts(self) -> Dict[str, int]:
        """Get count of questions by type."""
        counts: Dict[str, int] = {}
        for q in self._questions:
            counts[q.question_type] = counts.get(q.question_type, 0) + 1
        return counts
