import pytest

from app.services.learning import LearningEngine
from app.services.vector_store import RetrievedChunk


class FakeVectorStore:
    async def list_subject(self, subject_id: str, *, limit: int = 100) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                id="chunk-1",
                text="Addition combines two numbers into a sum.",
                score=1.0,
                metadata={"chunk_index": 0, "material_name": "notes.pdf", "page_number": 1},
            )
        ]

    async def query(self, embedding, *, subject_id: str, limit: int = 8):
        return []

    async def upsert(self, documents) -> None:
        return None

    async def delete_material(self, material_id: str) -> None:
        return None

    async def delete_subject(self, subject_id: str) -> None:
        return None


def _fake_level(order: int, level_type: str = "lesson") -> dict:
    return {
        "order": order,
        "chapter": "Foundations",
        "title": f"Level {order}",
        "description": f"Covers concept {order}.",
        "type": level_type,
        "estimated_minutes": 8,
        "objectives": ["Understand the concept"],
        "blocks": [
            {"type": "explanation", "text": "Numbers combine through addition."},
            {"type": "example", "text": "2 + 3 = 5"},
            {
                "type": "mini_quiz",
                "questions": [
                    {
                        "prompt": "What is 2 + 2?",
                        "choices": ["3", "4", "5", "6"],
                        "correct_index": 1,
                        "explanation": "2 + 2 equals 4.",
                    }
                ],
            },
            {"type": "not_a_real_block_type", "text": "should be dropped"},
        ],
        "source_ids": ["S1"],
    }


class FakeAI:
    generation_model = "fake-model"

    def __init__(self, level_count: int) -> None:
        self.level_count = level_count
        self.last_prompt: str | None = None

    async def generate_json(self, prompt: str, **kwargs) -> dict:
        self.last_prompt = prompt
        levels = [_fake_level(i) for i in range(1, self.level_count + 1)]
        return {
            "title": "Numbers to Algebra",
            "summary": "From counting to equations.",
            "levels": levels,
        }


@pytest.mark.asyncio
async def test_generate_learning_path_lets_ai_choose_level_count() -> None:
    ai = FakeAI(level_count=17)
    engine = LearningEngine(ai=ai, vector_store=FakeVectorStore())

    result = await engine.generate_learning_path(subject_id="subject-1", subject_name="Math")

    assert len(result["levels"]) == 17
    assert [level["order"] for level in result["levels"]] == list(range(1, 18))
    assert result["levels"][-1]["type"] == "boss"
    assert "levels" in ai.last_prompt.lower()
    assert "slide" not in ai.last_prompt.lower()


@pytest.mark.asyncio
async def test_generate_learning_path_caps_runaway_level_count() -> None:
    ai = FakeAI(level_count=500)
    engine = LearningEngine(ai=ai, vector_store=FakeVectorStore())

    result = await engine.generate_learning_path(subject_id="subject-1", subject_name="Math")

    assert len(result["levels"]) == 60


@pytest.mark.asyncio
async def test_generate_learning_path_parses_and_filters_blocks() -> None:
    ai = FakeAI(level_count=6)
    engine = LearningEngine(ai=ai, vector_store=FakeVectorStore())

    result = await engine.generate_learning_path(subject_id="subject-1", subject_name="Math")

    blocks = result["levels"][0]["blocks"]
    block_types = [block["type"] for block in blocks]
    assert "not_a_real_block_type" not in block_types
    assert "explanation" in block_types
    assert "mini_quiz" in block_types
    mini_quiz = next(block for block in blocks if block["type"] == "mini_quiz")
    assert len(mini_quiz["questions"]) == 1
    assert mini_quiz["questions"][0]["correct_index"] == 1
