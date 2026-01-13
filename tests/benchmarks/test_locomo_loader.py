"""Unit tests for LoCoMo dataset loader."""

import pytest
from unittest.mock import MagicMock, patch
import sys

from benchmarks.datasets.locomo import LoCoMoDataset, LoCoMoQuestion


class TestLoCoMoQuestion:
    """Test LoCoMoQuestion dataclass."""

    def test_question_creation(self):
        """Test creating a question dataclass."""
        question = LoCoMoQuestion(
            question_id="q_1",
            question="What is the capital of France?",
            choices=["London", "Paris", "Berlin", "Madrid"],
            correct_choice_index=1,
            answer="Paris",
            question_type="single_hop",
            haystack_sessions=[],
            haystack_session_summaries=["Summary 1"],
            haystack_session_datetimes=["2024-01-01"],
            num_sessions=1,
        )

        assert question.question_id == "q_1"
        assert question.question == "What is the capital of France?"
        assert question.choices[1] == "Paris"
        assert question.correct_choice_index == 1
        assert question.answer == "Paris"
        assert question.question_type == "single_hop"


class TestLoCoMoDataset:
    """Test LoCoMoDataset loader."""

    def test_dataset_initialization(self):
        """Test dataset initialization with defaults."""
        dataset = LoCoMoDataset()
        assert dataset.split == "train"
        assert dataset.question_types is None
        assert dataset.limit is None

    def test_dataset_with_filters(self):
        """Test dataset initialization with filters."""
        dataset = LoCoMoDataset(
            split="test",
            question_types=["single_hop", "multi_hop"],
            limit=100,
        )
        assert dataset.split == "test"
        assert dataset.question_types == ["single_hop", "multi_hop"]
        assert dataset.limit == 100

    def test_load_dataset(self):
        """Test loading dataset from HuggingFace."""
        datasets = pytest.importorskip("datasets")
        with patch.object(datasets, "load_dataset") as mock_load_dataset:
            mock_item = {
                "question": "Test question?",
                "choices": ["A", "B", "C", "D"],
                "correct_choice_index": 0,
                "answer": "A",
                "question_type": "single_hop",
                "haystack_sessions": [],
                "haystack_session_summaries": [],
                "haystack_session_datetimes": [],
                "num_sessions": 0,
            }
            mock_load_dataset.return_value = [mock_item]

            dataset = LoCoMoDataset(limit=1)
            dataset.load()

            assert len(dataset) == 1
            mock_load_dataset.assert_called_once_with("Percena/locomo-mc10", split="train")

    def test_load_with_question_type_filter(self):
        """Test loading with question type filter."""
        datasets = pytest.importorskip("datasets")
        with patch.object(datasets, "load_dataset") as mock_load_dataset:
            mock_items = [
                {
                    "question": "Single hop question?",
                    "choices": ["A", "B", "C", "D"],
                    "correct_choice_index": 0,
                    "answer": "A",
                    "question_type": "single_hop",
                    "haystack_sessions": [],
                    "haystack_session_summaries": [],
                    "haystack_session_datetimes": [],
                    "num_sessions": 0,
                },
                {
                    "question": "Multi hop question?",
                    "choices": ["A", "B", "C", "D"],
                    "correct_choice_index": 1,
                    "answer": "B",
                    "question_type": "multi_hop",
                    "haystack_sessions": [],
                    "haystack_session_summaries": [],
                    "haystack_session_datetimes": [],
                    "num_sessions": 0,
                },
            ]
            mock_load_dataset.return_value = mock_items

            dataset = LoCoMoDataset(question_types=["single_hop"])
            dataset.load()

            assert len(dataset) == 1
            assert dataset[0].question_type == "single_hop"

    def test_load_with_limit(self):
        """Test loading with limit."""
        datasets = pytest.importorskip("datasets")
        with patch.object(datasets, "load_dataset") as mock_load_dataset:
            mock_items = [
                {
                    "question": f"Question {i}?",
                    "choices": ["A", "B", "C", "D"],
                    "correct_choice_index": 0,
                    "answer": "A",
                    "question_type": "single_hop",
                    "haystack_sessions": [],
                    "haystack_session_summaries": [],
                    "haystack_session_datetimes": [],
                    "num_sessions": 0,
                }
                for i in range(10)
            ]
            mock_load_dataset.return_value = mock_items

            dataset = LoCoMoDataset(limit=5)
            dataset.load()

            assert len(dataset) == 5

    def test_iteration(self):
        """Test iterating over dataset."""
        datasets = pytest.importorskip("datasets")
        with patch.object(datasets, "load_dataset") as mock_load_dataset:
            mock_items = [
                {
                    "question": f"Question {i}?",
                    "choices": ["A", "B", "C", "D"],
                    "correct_choice_index": i % 4,
                    "answer": ["A", "B", "C", "D"][i % 4],
                    "question_type": "single_hop",
                    "haystack_sessions": [],
                    "haystack_session_summaries": [],
                    "haystack_session_datetimes": [],
                    "num_sessions": 0,
                }
                for i in range(3)
            ]
            mock_load_dataset.return_value = mock_items

            dataset = LoCoMoDataset()
            dataset.load()

            questions = list(dataset)
            assert len(questions) == 3
            assert questions[0].question == "Question 0?"
            assert questions[2].question == "Question 2?"

    def test_indexing(self):
        """Test indexing into dataset."""
        datasets = pytest.importorskip("datasets")
        with patch.object(datasets, "load_dataset") as mock_load_dataset:
            mock_items = [
                {
                    "question": f"Question {i}?",
                    "choices": ["A", "B", "C", "D"],
                    "correct_choice_index": 0,
                    "answer": "A",
                    "question_type": "single_hop",
                    "haystack_sessions": [],
                    "haystack_session_summaries": [],
                    "haystack_session_datetimes": [],
                    "num_sessions": 0,
                }
                for i in range(5)
            ]
            mock_load_dataset.return_value = mock_items

            dataset = LoCoMoDataset()
            dataset.load()

            assert dataset[0].question == "Question 0?"
            assert dataset[4].question == "Question 4?"


class TestFormatSessions:
    """Test session formatting methods."""

    def test_format_sessions_list_format(self):
        """Test formatting sessions in list format."""
        question = LoCoMoQuestion(
            question_id="q_1",
            question="Test?",
            choices=["A", "B"],
            correct_choice_index=0,
            answer="A",
            question_type="single_hop",
            haystack_sessions=[
                [
                    {"speaker": "Alice", "text": "Hello!"},
                    {"speaker": "Bob", "text": "Hi there!"},
                ]
            ],
            haystack_session_summaries=[],
            haystack_session_datetimes=["2024-01-01"],
            num_sessions=1,
        )

        dataset = LoCoMoDataset()
        conversations = dataset.format_sessions_as_conversations(question)

        assert len(conversations) == 1
        assert "Alice: Hello!" in conversations[0]
        assert "Bob: Hi there!" in conversations[0]
        assert "2024-01-01" in conversations[0]

    def test_format_sessions_dict_format(self):
        """Test formatting sessions in dict format with turns."""
        question = LoCoMoQuestion(
            question_id="q_1",
            question="Test?",
            choices=["A", "B"],
            correct_choice_index=0,
            answer="A",
            question_type="single_hop",
            haystack_sessions=[
                {
                    "turns": [
                        {"speaker": "Alice", "text": "Good morning!"},
                        {"speaker": "Bob", "text": "Good morning to you!"},
                    ]
                }
            ],
            haystack_session_summaries=[],
            haystack_session_datetimes=[],
            num_sessions=1,
        )

        dataset = LoCoMoDataset()
        conversations = dataset.format_sessions_as_conversations(question)

        assert len(conversations) == 1
        assert "Alice: Good morning!" in conversations[0]

    def test_format_empty_sessions(self):
        """Test formatting with no sessions."""
        question = LoCoMoQuestion(
            question_id="q_1",
            question="Test?",
            choices=["A", "B"],
            correct_choice_index=0,
            answer="A",
            question_type="single_hop",
            haystack_sessions=[],
            haystack_session_summaries=[],
            haystack_session_datetimes=[],
            num_sessions=0,
        )

        dataset = LoCoMoDataset()
        conversations = dataset.format_sessions_as_conversations(question)

        assert len(conversations) == 0

    def test_get_session_summaries(self):
        """Test getting session summaries."""
        question = LoCoMoQuestion(
            question_id="q_1",
            question="Test?",
            choices=["A", "B"],
            correct_choice_index=0,
            answer="A",
            question_type="single_hop",
            haystack_sessions=[],
            haystack_session_summaries=["Summary 1", "Summary 2"],
            haystack_session_datetimes=[],
            num_sessions=2,
        )

        dataset = LoCoMoDataset()
        summaries = dataset.get_session_summaries(question)

        assert len(summaries) == 2
        assert summaries[0] == "Summary 1"


class TestQuestionTypeCounts:
    """Test question type counting."""

    def test_question_type_counts(self):
        """Test counting questions by type."""
        datasets = pytest.importorskip("datasets")
        with patch.object(datasets, "load_dataset") as mock_load_dataset:
            mock_items = [
                {
                    "question": "Q1?",
                    "choices": ["A"],
                    "correct_choice_index": 0,
                    "answer": "A",
                    "question_type": "single_hop",
                    "haystack_sessions": [],
                    "haystack_session_summaries": [],
                    "haystack_session_datetimes": [],
                    "num_sessions": 0,
                },
                {
                    "question": "Q2?",
                    "choices": ["A"],
                    "correct_choice_index": 0,
                    "answer": "A",
                    "question_type": "single_hop",
                    "haystack_sessions": [],
                    "haystack_session_summaries": [],
                    "haystack_session_datetimes": [],
                    "num_sessions": 0,
                },
                {
                    "question": "Q3?",
                    "choices": ["A"],
                    "correct_choice_index": 0,
                    "answer": "A",
                    "question_type": "multi_hop",
                    "haystack_sessions": [],
                    "haystack_session_summaries": [],
                    "haystack_session_datetimes": [],
                    "num_sessions": 0,
                },
            ]
            mock_load_dataset.return_value = mock_items

            dataset = LoCoMoDataset()
            dataset.load()

            counts = dataset.question_type_counts
            assert counts["single_hop"] == 2
            assert counts["multi_hop"] == 1
