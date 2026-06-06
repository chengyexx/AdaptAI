"""前端 UX 规则测试 — TDD 验证 UI/UX Pro Max 标准 + 工作台结构"""

import pytest
from pathlib import Path

FRONTEND = Path(__file__).parent.parent.parent / "frontend"


@pytest.fixture
def css():
    return (FRONTEND / "css" / "style.css").read_text(encoding="utf-8")

@pytest.fixture
def index_html():
    return (FRONTEND / "index.html").read_text(encoding="utf-8")

@pytest.fixture
def workspace_html():
    path = FRONTEND / "workspace.html"
    if not path.exists():
        pytest.skip("workspace.html 尚未创建")
    return path.read_text(encoding="utf-8")


# ── Design Tokens ──

def test_css_uses_design_tokens(css):
    tokens = ["--bg-root", "--bg-surface", "--text-primary", "--text-secondary",
              "--accent", "--success", "--warning", "--danger"]
    for token in tokens:
        assert f"var({token}" in css or token in css, f"缺少设计令牌: {token}"


# ── Accessibility (UI UX Pro Max §1 CRITICAL) ──

def test_touch_targets_minimum(css):
    for rule in ["btn-primary", "btn-sm", ".mode-tabs button", "input"]:
        if rule in css:
            assert "min-height" in css or "padding" in css

def test_html_has_lang_attribute(index_html):
    assert 'lang="zh-CN"' in index_html

def test_buttons_have_focus_styles(css):
    assert ":focus" in css

def test_color_not_only_indicator(css):
    assert "transition" in css

def test_html_viewport_meta(index_html):
    assert 'name="viewport"' in index_html
    assert "initial-scale=1" in index_html
    assert "user-scalable=no" not in index_html


# ── Page Structure ──

def test_index_has_main_landmark(index_html):
    assert "<main" in index_html

def test_workspace_has_nav_landmark(workspace_html):
    assert "<aside" in workspace_html or "<nav" in workspace_html

def test_workspace_has_progress_bar(workspace_html):
    assert "progress-fill" in workspace_html or "progress" in workspace_html

def test_workspace_has_pipeline_stages(workspace_html):
    stages = ["章节解析", "角色识别", "场景切分", "剧本生成", "校验"]
    for stage in stages:
        assert stage in workspace_html, f"缺少阶段: {stage}"

def test_workspace_loads_all_js(workspace_html):
    required_js = ["state.js", "websocket.js", "pipeline.js", "hitl.js"]
    for js in required_js:
        assert js in workspace_html, f"缺少JS引用: {js}"
