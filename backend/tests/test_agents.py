"""
Agent unit tests.
Run with: pytest tests/test_agents.py -v
"""

from unittest.mock import patch


# ---------------------------------------------------------------------------
# Reasoning-model guard tests
# ---------------------------------------------------------------------------

def test_is_reasoning_model_opus_47():
    """claude-opus-4-7 (and OpenRouter-prefixed variants) should be detected."""
    from app.config import is_reasoning_model

    assert is_reasoning_model("claude-opus-4-7") is True
    assert is_reasoning_model("anthropic/claude-opus-4-7") is True


def test_is_reasoning_model_non_reasoning():
    """Sonnet and older models should NOT be flagged as reasoning models."""
    from app.config import is_reasoning_model

    assert is_reasoning_model("claude-sonnet-4-6") is False
    assert is_reasoning_model("anthropic/claude-sonnet-4-6") is False
    assert is_reasoning_model("claude-opus-4-6") is False


def test_opus_llm_omits_temperature():
    """build_llm() for Opus 4.7 should NOT pass temperature to ChatAnthropic."""
    from app.config import Settings
    from unittest.mock import MagicMock
    import app.agents.personas.operationalizer as op_mod

    mock_settings = Settings(
        anthropic_api_key="sk-ant-test",
        opus_model="claude-opus-4-7",
        llm_temperature=0.7,
    )

    with patch.object(op_mod, "get_settings", return_value=mock_settings), \
         patch.object(op_mod, "ChatAnthropic") as MockChat:
        op_mod.build_llm()
        call_kwargs = MockChat.call_args[1]
        assert "temperature" not in call_kwargs, \
            f"temperature should be omitted for reasoning models, got {call_kwargs}"


def test_sonnet_llm_includes_temperature():
    """get_sonnet_llm() for non-reasoning models should pass temperature."""
    from app.config import Settings
    from langchain_anthropic import ChatAnthropic

    mock_settings = Settings(
        anthropic_api_key="sk-ant-test",
        sonnet_model="claude-sonnet-4-6",
        llm_temperature=0.7,
    )

    with patch("app.agents.personas._llm_factory.get_settings", return_value=mock_settings):
        from app.agents.personas._llm_factory import get_sonnet_llm

        llm = get_sonnet_llm()
        assert isinstance(llm, ChatAnthropic)
        # ChatAnthropic stores temperature on the instance
        assert llm.temperature == 0.7


# ---------------------------------------------------------------------------
# LLM factory tests
# ---------------------------------------------------------------------------

def test_sonnet_llm_uses_anthropic_api():
    """get_sonnet_llm() should return a ChatAnthropic instance using the Claude API."""
    from app.config import Settings
    from langchain_anthropic import ChatAnthropic

    mock_settings = Settings(
        anthropic_api_key="sk-ant-test",
        sonnet_model="claude-sonnet-4-6",
    )

    with patch("app.agents.personas._llm_factory.get_settings", return_value=mock_settings):
        from app.agents.personas._llm_factory import get_sonnet_llm

        llm = get_sonnet_llm()
        assert isinstance(llm, ChatAnthropic)
        assert llm.model == "claude-sonnet-4-6"


def test_sonnet_llm_uses_configured_model():
    """The model identifier should come from settings.sonnet_model."""
    from app.config import Settings
    from langchain_anthropic import ChatAnthropic

    mock_settings = Settings(
        anthropic_api_key="sk-ant-test",
        sonnet_model="claude-sonnet-4-6",
    )

    with patch("app.agents.personas._llm_factory.get_settings", return_value=mock_settings):
        from app.agents.personas._llm_factory import get_sonnet_llm

        llm = get_sonnet_llm()
        assert isinstance(llm, ChatAnthropic)


# ---------------------------------------------------------------------------
# Graph structure tests (no LLM calls)
# ---------------------------------------------------------------------------

def test_graph_builds_without_error():
    """The LangGraph StateGraph should compile without raising exceptions."""
    from app.agents.graph import build_graph
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_graph(MemorySaver())
    assert graph is not None


def test_graph_nodes_present():
    """Graph should contain the expected Ask + Think node names."""
    from app.agents.graph import build_graph
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_graph(MemorySaver())
    node_names = set(graph.nodes.keys())
    expected = {"operationalizer", "critic", "wait_for_selection", "decompose", "market_match"}
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"
    # Synthesizer (James) is deferred to Show and must NOT be wired into the graph.
    assert "synthesizer" not in node_names


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

def test_forecast_session_serializes():
    """ForecastSession should serialize to/from JSON without loss."""
    from app.models.schemas import ForecastSession, QuestionInput
    from datetime import datetime, timezone

    session = ForecastSession(
        id="abc",
        thread_id="abc",
        created_at=datetime.now(timezone.utc),
        original_question=QuestionInput(raw_question="Test question?"),
        status="intake",
    )
    dumped = session.model_dump_json()
    restored = ForecastSession.model_validate_json(dumped)
    assert restored.id == session.id
    assert restored.status == "intake"


def test_operationalized_question_deadline_coercion():
    """OperationalizedQuestion should parse ISO strings as datetime."""
    from app.models.schemas import OperationalizedQuestion

    oq = OperationalizedQuestion(
        id="test",
        text="Will X happen?",
        resolution_criteria="Criteria",
        resolution_source="Source",
        deadline="2026-12-31T23:59:59Z",
        outcome_options=["Yes", "No"],
        void_conditions="None",
    )
    from datetime import datetime
    assert isinstance(oq.deadline, datetime)
    assert oq.outcome_type == "binary"
    assert oq.outcome_unit is None


def test_operationalized_question_outcome_types():
    """OperationalizedQuestion should accept all four outcome types."""
    from app.models.schemas import OperationalizedQuestion

    for ot in ("binary", "categorical", "date", "numeric"):
        oq = OperationalizedQuestion(
            id="t",
            text="?",
            resolution_criteria="c",
            resolution_source="s",
            deadline="2026-12-31T23:59:59Z",
            outcome_type=ot,
            outcome_options=[] if ot in ("date", "numeric") else ["A", "B"],
            outcome_unit="USD" if ot == "numeric" else None,
            void_conditions="v",
        )
        assert oq.outcome_type == ot


def test_selection_input_accepts_user_feedback():
    from app.models.schemas import SelectionInput, OperationalizedQuestion

    oq = OperationalizedQuestion(
        id="t",
        text="?",
        resolution_criteria="c",
        resolution_source="s",
        deadline="2026-12-31T23:59:59Z",
        outcome_options=["Yes", "No"],
        void_conditions="v",
    )
    sel = SelectionInput(operationalized_question=oq, user_feedback="focus on X")
    assert sel.user_feedback == "focus on X"
    sel2 = SelectionInput(operationalized_question=oq)
    assert sel2.user_feedback is None


# ---------------------------------------------------------------------------
# Critic ranked_order validation
# ---------------------------------------------------------------------------


def test_validate_order_accepts_permutation():
    from app.agents.personas.critic import _validate_order

    assert _validate_order([2, 0, 1], 3) == [2, 0, 1]
    assert _validate_order([0, 1, 2], 3) == [0, 1, 2]


def test_validate_order_falls_back_on_invalid():
    from app.agents.personas.critic import _validate_order

    assert _validate_order([0, 0, 1], 3) == [0, 1, 2]   # duplicate
    assert _validate_order([0, 1], 3) == [0, 1, 2]       # wrong length
    assert _validate_order([0, 1, 5], 3) == [0, 1, 2]    # out of range
    assert _validate_order(None, 3) == [0, 1, 2]         # missing


# ---------------------------------------------------------------------------
# Route reorder helper
# ---------------------------------------------------------------------------


def test_route_reorder_applies_candidate_order():
    from app.routes.questions import _reorder
    from app.models.schemas import OperationalizedQuestion

    def make(i):
        return OperationalizedQuestion(
            id=str(i),
            text=f"#{i}",
            resolution_criteria="c",
            resolution_source="s",
            deadline="2026-12-31T23:59:59Z",
            outcome_options=["Yes", "No"],
            void_conditions="v",
        )

    options = [make(0), make(1), make(2)]
    out = _reorder(options, [2, 0, 1])
    assert [o.text for o in out] == ["#2", "#0", "#1"]


def test_route_reorder_falls_back_on_invalid_order():
    from app.routes.questions import _reorder
    from app.models.schemas import OperationalizedQuestion

    options = [
        OperationalizedQuestion(
            id="x", text="x", resolution_criteria="c", resolution_source="s",
            deadline="2026-12-31T23:59:59Z", outcome_options=["Yes", "No"], void_conditions="v",
        )
    ]
    assert _reorder(options, None) is options
    assert _reorder(options, [0, 1]) is options  # length mismatch → fallback


# ---------------------------------------------------------------------------
# TEST mode tests
# ---------------------------------------------------------------------------


def test_is_test_question_predicate():
    from app.agents.personas._test_mode import is_test_question

    assert is_test_question("TEST") is True
    assert is_test_question("test") is True
    assert is_test_question("  Test  ") is True
    assert is_test_question("tEsT") is True
    assert is_test_question(None) is False
    assert is_test_question("") is False
    assert is_test_question("   ") is False
    assert is_test_question("Will the Fed cut rates?") is False
    assert is_test_question("test the waters") is False


def test_build_test_llm_config():
    """build_test_llm should request reasoning mode at minimum budget, no temperature."""
    from app.config import Settings
    import app.agents.personas._test_mode as tm

    mock_settings = Settings(anthropic_api_key="sk-ant-test", opus_model="claude-opus-4-7")

    with patch.object(tm, "get_settings", return_value=mock_settings), \
         patch.object(tm, "ChatAnthropic") as MockChat:
        tm.build_test_llm("claude-opus-4-7")
        call_kwargs = MockChat.call_args[1]
        assert call_kwargs["model"] == "claude-opus-4-7"
        assert call_kwargs["max_tokens"] == 1500
        assert call_kwargs["thinking"] == {"type": "adaptive"}
        assert call_kwargs["output_config"] == {"effort": "low"}
        assert "temperature" not in call_kwargs


def test_extract_text_flattens_thinking_blocks():
    """_extract_text must skip thinking blocks and concatenate text blocks."""
    from app.agents.personas._test_mode import _extract_text

    class FakeResp:
        def __init__(self, content):
            self.content = content

    assert _extract_text(FakeResp("plain string  ")) == "plain string"
    assert _extract_text(FakeResp([
        {"type": "thinking", "thinking": "internal CoT"},
        {"type": "text", "text": "Hello world."},
    ])) == "Hello world."
    assert _extract_text(FakeResp([
        {"type": "text", "text": "Part A "},
        {"type": "thinking", "thinking": "skip me"},
        {"type": "text", "text": "Part B"},
    ])) == "Part A Part B"


def _minimal_test_state(extra: dict | None = None) -> dict:
    base = {
        "raw_question": "test",
        "deadline": None,
        "outcome_description": None,
        "operationalized_options": [],
        "candidate_order": [],
        "critic_feedback": None,
        "critic_approved": False,
        "revision_count": 0,
        "selected_option": None,
        "user_feedback": None,
        "modular_sub_questions": [],
        "final_summary": None,
        "messages": [],
    }
    if extra:
        base.update(extra)
    return base


def test_operationalizer_test_mode_returns_canned_options():
    import app.agents.personas.operationalizer as op_mod

    with patch.object(op_mod, "run_test_intro", return_value="Message received. I'm Dr. Mira Chen; my focus is operationalizing.") as mock_intro, \
         patch.object(op_mod, "build_llm") as mock_build:
        result = op_mod.operationalizer_node(_minimal_test_state())

    mock_intro.assert_called_once()
    mock_build.assert_not_called()
    assert "operationalized_options" in result
    assert len(result["operationalized_options"]) == 3
    assert result["operationalized_options"][0]["text"].startswith("TEST — Message received.")
    assert result["messages"] == []


def test_critic_test_mode_auto_approves():
    import app.agents.personas.critic as critic_mod

    state = _minimal_test_state({
        "revision_count": 0,
        "operationalized_options": [
            {"text": "a"}, {"text": "b"}, {"text": "c"},
        ],
    })
    with patch.object(critic_mod, "run_test_intro", return_value="Message received. I'm Marcus Webb; my focus is vetoing.") as mock_intro, \
         patch.object(critic_mod, "get_sonnet_llm") as mock_factory:
        result = critic_mod.critic_node(state)

    mock_intro.assert_called_once()
    mock_factory.assert_not_called()
    assert result["critic_approved"] is True
    assert result["critic_feedback"].startswith("TEST MODE — Message received.")
    assert result["revision_count"] == 1
    assert result["candidate_order"] == [0, 1, 2]
    assert result["messages"] == []


def test_decompose_test_mode_returns_proposed_tree():
    import app.agents.personas.modularizer as mod_mod

    with patch.object(mod_mod, "run_test_intro", return_value="Message received. I'm Dr. Anika Patel; my focus is decomposing.") as mock_intro, \
         patch.object(mod_mod, "get_sonnet_llm") as mock_factory:
        result = mod_mod.decompose_node(_minimal_test_state())

    mock_intro.assert_called_once()
    mock_factory.assert_not_called()
    tree = result["proposed_tree"]
    assert len(tree) == 2
    # First major is a rollup with ideal sub-questions; second is atomic.
    assert tree[0]["is_atomic"] is False and len(tree[0]["ideal_subquestions"]) == 2
    assert tree[1]["is_atomic"] is True and tree[1]["ideal_subquestions"] == []
    assert tree[0]["component"].startswith("TEST — Message received.")
    assert result["messages"] == []


def test_synthesizer_test_mode_returns_canned_summary():
    import app.agents.personas.synthesizer as synth_mod

    with patch.object(synth_mod, "run_test_intro", return_value="Message received. I'm James Harrington; my focus is synthesizing.") as mock_intro, \
         patch.object(synth_mod, "get_sonnet_llm") as mock_factory:
        result = synth_mod.synthesizer_node(_minimal_test_state())

    mock_intro.assert_called_once()
    mock_factory.assert_not_called()
    assert result["final_summary"].startswith("TEST MODE — Message received.")
    assert result["messages"] == []


def test_non_test_question_skips_test_mode():
    """A normal question must NOT trigger the test-mode short-circuit."""
    import app.agents.personas.operationalizer as op_mod

    with patch.object(op_mod, "run_test_intro") as mock_intro, \
         patch.object(op_mod, "build_llm") as mock_build:
        mock_build.return_value.with_structured_output.return_value.invoke.side_effect = RuntimeError("would hit real LLM")
        try:
            op_mod.operationalizer_node(_minimal_test_state({"raw_question": "Will the Fed cut rates?"}))
        except RuntimeError:
            pass  # expected — we hit the real LLM path

    mock_intro.assert_not_called()
    mock_build.assert_called_once()
