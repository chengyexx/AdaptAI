# AdaptAI — Design System

## 产品分析
- **类型**: Tool (AI converter/editor) — 文学创作工具
- **用户**: 小说作者、编剧，长时间阅读/编辑文本
- **风格**: Minimalism + Dark Mode, content-first, literary
- **技术栈**: HTML/CSS + Alpine.js + htmx

## 设计令牌 (Design Tokens)

### Colors (WCAG AA 4.5:1 contrast verified)
| Token | Hex | Usage |
|--------|-----|-------|
| `--bg-root` | `#0d1117` | 页面根背景 |
| `--bg-surface` | `#161b22` | 卡片/面板/输入框 |
| `--bg-elevated` | `#1c2129` | Hover/弹层 |
| `--border-default` | `#30363d` | 默认边框 |
| `--border-muted` | `#21262d` | 弱边框 |
| `--text-primary` | `#e6edf3` | 主文本 (contrast 14.5:1 on bg-root) |
| `--text-secondary` | `#8b949e` | 次文本 (contrast 5.2:1) |
| `--text-tertiary` | `#6e7681` | 辅助文本 |
| `--accent` | `#58a6ff` | 主强调色 (蓝) |
| `--accent-hover` | `#79c0ff` | 强调悬停 |
| `--success` | `#3fb950` | 完成/成功 |
| `--warning` | `#d29922` | HITL/警告 |
| `--danger` | `#f85149` | 错误/危险 |
| `--accent-literary` | `#c9a96e` | 文学金色点缀 |

### Typography
| Token | Value | Usage |
|--------|-------|-------|
| Font stack | `-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif` | UI 全局 |
| `--text-xs` | 0.75rem (12px) | 标签/徽章 |
| `--text-sm` | 0.875rem (14px) | 辅助文本 |
| `--text-base` | 1rem (16px) | 正文 (最小16px防iOS缩放) |
| `--text-lg` | 1.125rem (18px) | 子标题 |
| `--text-xl` | 1.5rem (24px) | 标题 |
| `--text-2xl` | 2rem (32px) | 页面标题 |
| Line-height body | 1.6 | 正文 |
| Line-height heading | 1.3 | 标题 |

### Spacing (4pt/8dp system)
| Token | Value |
|--------|-------|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-6` | 24px |
| `--space-8` | 32px |
| `--space-12` | 48px |

### Touch Targets (CRITICAL)
- All interactive elements: min 44×44px
- Spacing between touch targets: min 8px

### Animation
- Duration: 150-300ms micro-interactions
- Easing: ease-out for enter, ease-in for exit
- Respect prefers-reduced-motion

### Breakpoints (Mobile-first)
- Mobile: 375px+
- Tablet: 768px+
- Desktop: 1024px+
