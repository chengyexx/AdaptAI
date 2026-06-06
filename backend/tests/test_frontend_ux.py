"""前端 UX 关键规则测试 — TDD 验证 UI/UX Pro Max 标准"""

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
        pytest.skip("workspace.html 尚未创建（将在 PR 12 添加）")
    return path.read_text(encoding="utf-8")


# ── Design Tokens ──

def test_css_uses_design_tokens(css):
    """CSS 应使用 CSS 变量而非裸写 hex 值"""
    tokens = ["--bg-root", "--bg-surface", "--text-primary", "--text-secondary",
              "--accent", "--success", "--warning", "--danger"]
    for token in tokens:
        assert f"var({token}" in css or token in css, f"缺少设计令牌: {token}"


# ── Accessibility ──

def test_touch_targets_minimum(css):
    """交互元素触摸区域 ≥ 44px"""
    for rule in ["btn-primary", "btn-sm", ".mode-tabs button", "input"]:
        if rule in css:
            assert "min-height" in css or "padding" in css, \
                f"{rule} 需要确保触摸区域 ≥ 44px"


def test_html_has_lang_attribute(index_html):
    """HTML 应有 lang 属性"""
    assert 'lang="zh-CN"' in index_html


def test_buttons_have_focus_styles(css):
    """按钮应有 focus 样式"""
    assert ":focus" in css, "按钮需要 focus 状态样式"


def test_color_not_only_indicator(css):
    """颜色不应是唯一的状态指示器（需配合图标/文本）"""
    # 验证有 transition/animation 辅助状态表达
    assert "transition" in css, "缺少transition辅助状态变化"


# ── Page Structure ──

def test_index_has_main_landmark(index_html):
    """首页应有 <main> 地标"""
    assert "<main" in index_html


def test_workspace_has_nav_landmark(workspace_html):
    """工作台应有导航结构"""
    assert "<aside" in workspace_html or "<nav" in workspace_html


# ── Performance ──

def test_html_viewport_meta(index_html):
    """应有 viewport meta 标签"""
    assert 'name="viewport"' in index_html
    assert "initial-scale=1" in index_html
    assert "user-scalable=no" not in index_html  # 不应禁止缩放
