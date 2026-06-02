from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

import src.sourcing_agent.llm_backend as lb

_VALID_JSON = json.dumps(
    {
        "primary_section": "S4a:navigation",
        "secondary_sections": [],
        "kunze_dimension": "D1",
        "technique_cluster": "visual_odometry",
        "cluster_assignment_confidence": "high",
        "source_type": "primary_research",
        "section_fit_score": 8.0,
        "contribution_score": 7.0,
        "recency_score": 9.0,
        "is_historical": False,
        "space_heritage": False,
        "deployment_constraints_discussed": False,
        "compute_requirements_noted": False,
        "radiation_robustness_discussed": False,
        "operational_description_present": False,
        "alignment_paper": False,
        "compositional_alignment": False,
        "general_alignment_robotics_context": False,
        "mission_or_system_name": None,
        "agent_notes": "Test result",
    }
)


@pytest.fixture(autouse=True)
def reset_ollama_cache():
    lb._ollama_available_cache = None
    yield
    lb._ollama_available_cache = None


class TestCallScorer:
    @pytest.mark.asyncio
    async def test_uses_ollama_when_backend_is_ollama(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "ollama")

        with (
            patch.object(
                lb, "_check_ollama_available", new=AsyncMock(return_value=True)
            ),
            patch.object(
                lb, "_call_ollama", new=AsyncMock(return_value=_VALID_JSON)
            ) as mock_ollama,
        ):
            result = await lb.call_scorer("test prompt")

        mock_ollama.assert_called_once()
        assert json.loads(result)["primary_section"] == "S4a:navigation"

    @pytest.mark.asyncio
    async def test_falls_back_to_groq_on_double_json_failure(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "ollama")
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

        with (
            patch.object(
                lb, "_check_ollama_available", new=AsyncMock(return_value=True)
            ),
            patch.object(
                lb, "_call_ollama", new=AsyncMock(return_value="not valid json {{{")
            ) as mock_ollama,
            patch.object(
                lb, "_call_groq", new=AsyncMock(return_value=_VALID_JSON)
            ) as mock_groq,
        ):
            result = await lb.call_scorer("test prompt")

        assert mock_ollama.call_count == 2  # tried twice before escalating
        mock_groq.assert_called_once()
        assert result == _VALID_JSON

    @pytest.mark.asyncio
    async def test_uses_groq_directly_when_backend_is_groq(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

        with (
            patch.object(
                lb, "_call_groq", new=AsyncMock(return_value=_VALID_JSON)
            ) as mock_groq,
            patch.object(lb, "_call_ollama", new=AsyncMock()) as mock_ollama,
        ):
            result = await lb.call_scorer("test prompt")

        mock_groq.assert_called_once()
        mock_ollama.assert_not_called()
        assert result == _VALID_JSON

    @pytest.mark.asyncio
    async def test_uses_anthropic_when_backend_is_anthropic(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with (
            patch.object(
                lb, "_call_anthropic", new=AsyncMock(return_value=_VALID_JSON)
            ) as mock_anthropic,
            patch.object(lb, "_call_ollama", new=AsyncMock()) as mock_ollama,
            patch.object(lb, "_call_groq", new=AsyncMock()) as mock_groq,
        ):
            result = await lb.call_scorer("test prompt")

        mock_anthropic.assert_called_once()
        mock_ollama.assert_not_called()
        mock_groq.assert_not_called()
        assert result == _VALID_JSON

    @pytest.mark.asyncio
    async def test_falls_back_to_groq_when_ollama_unavailable(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "ollama")
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

        with (
            patch.object(
                lb, "_check_ollama_available", new=AsyncMock(return_value=False)
            ),
            patch.object(
                lb, "_call_groq", new=AsyncMock(return_value=_VALID_JSON)
            ) as mock_groq,
            patch.object(lb, "_call_ollama", new=AsyncMock()) as mock_ollama,
        ):
            result = await lb.call_scorer("test prompt")

        mock_ollama.assert_not_called()
        mock_groq.assert_called_once()
        assert result == _VALID_JSON

    @pytest.mark.asyncio
    async def test_raises_scoring_backend_error_when_all_fail(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "ollama")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        with (
            patch.object(
                lb, "_check_ollama_available", new=AsyncMock(return_value=True)
            ),
            patch.object(
                lb, "_call_ollama", new=AsyncMock(return_value="invalid json")
            ),
            patch.object(
                lb, "_call_groq", new=AsyncMock(side_effect=Exception("Groq API down"))
            ),
        ):
            with pytest.raises(lb.ScoringBackendError):
                await lb.call_scorer("test prompt")

    @pytest.mark.asyncio
    async def test_raises_when_ollama_unavailable_and_no_groq_key(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "ollama")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        with patch.object(
            lb, "_check_ollama_available", new=AsyncMock(return_value=False)
        ):
            with pytest.raises(lb.ScoringBackendError):
                await lb.call_scorer("test prompt")


class TestCallAnalysis:
    @pytest.mark.asyncio
    async def test_always_uses_groq_regardless_of_scorer_backend(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "ollama")
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

        with (
            patch.object(
                lb, "_call_groq", new=AsyncMock(return_value=_VALID_JSON)
            ) as mock_groq,
            patch.object(lb, "_call_ollama", new=AsyncMock()) as mock_ollama,
        ):
            result = await lb.call_analysis("test prompt", "test system")

        mock_groq.assert_called_once()
        mock_ollama.assert_not_called()
        assert result == _VALID_JSON

    @pytest.mark.asyncio
    async def test_uses_groq_even_when_scorer_backend_is_anthropic(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "anthropic")
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

        with (
            patch.object(
                lb, "_call_groq", new=AsyncMock(return_value=_VALID_JSON)
            ) as mock_groq,
            patch.object(lb, "_call_anthropic", new=AsyncMock()) as mock_anthropic,
        ):
            await lb.call_analysis("test prompt", "system prompt")

        mock_groq.assert_called_once()
        mock_anthropic.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_ollama_when_no_groq_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        with (
            patch.object(
                lb, "_check_ollama_available", new=AsyncMock(return_value=True)
            ),
            patch.object(
                lb, "_call_ollama", new=AsyncMock(return_value=_VALID_JSON)
            ) as mock_ollama,
        ):
            result = await lb.call_analysis("test prompt", "test system")

        mock_ollama.assert_called_once()
        assert result == _VALID_JSON

    @pytest.mark.asyncio
    async def test_raises_analysis_backend_error_when_no_backend(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        with patch.object(
            lb, "_check_ollama_available", new=AsyncMock(return_value=False)
        ):
            with pytest.raises(lb.AnalysisBackendError):
                await lb.call_analysis("test prompt", "test system")


class TestGetBackendInfo:
    def test_ollama_backend_by_default(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "ollama")
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
        monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "4")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch.object(lb, "_check_ollama_sync", return_value=True):
            info = lb.get_backend_info()

        assert info["scorer_backend"] == "ollama"
        assert info["scorer_model"] == "qwen2.5:7b"
        assert info["scorer_parallel"] == 4
        assert info["ollama_available"] is True
        assert info["groq_available"] is False
        assert info["anthropic_available"] is False
        assert info["analysis_backend"] == "ollama"

    def test_groq_available_when_key_set(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "ollama")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch.object(lb, "_check_ollama_sync", return_value=False):
            info = lb.get_backend_info()

        assert info["ollama_available"] is False
        assert info["groq_available"] is True
        assert info["analysis_backend"] == "groq"
        assert info["analysis_model"] == lb._GROQ_ANALYSIS_MODEL

    def test_anthropic_backend_config(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        with patch.object(lb, "_check_ollama_sync", return_value=False):
            info = lb.get_backend_info()

        assert info["scorer_backend"] == "anthropic"
        assert info["scorer_model"] == lb._ANTHROPIC_MODEL
        assert info["anthropic_available"] is True

    def test_custom_parallel_count(self, monkeypatch):
        monkeypatch.setenv("SCORER_BACKEND", "ollama")
        monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "2")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch.object(lb, "_check_ollama_sync", return_value=False):
            info = lb.get_backend_info()

        assert info["scorer_parallel"] == 2
