---
name: feeling-to-jargon
description: 把用户模糊的白话需求匹配到专业术语，并按需扩写成更具体的提示词。
---

# Feeling to Jargon

Feeling to Jargon 帮助用户把模糊感受翻译成专业术语，再按需补全成可执行的提示词。

## 渐进式加载协议

索引必须按以下顺序逐级收窄：

```text
根领域 → 专业子域 → 用户意图 → 叶子包 → 单条术语/技巧/模板
```

1. 读取 `index/root.json`，只判断候选根领域和加载上限。
2. 读取对应的 `index/domains/<domain_id>.json`，最多选择 `max_subdomains` 个子域。
3. 读取子域的 `index/intents/<domain_id>/<subdomain_id>.json`，最多选择 `max_intents` 个意图。
4. 读取 `index/runtime.json` 做关键词/语义路由，只加载命中的叶子路径。
5. 每个叶子最多取 `max_entries_per_leaf` 条，优先取与用户表达最接近的条目。复杂交互优先读取同一叶子中的 `state_machine`、阈值、取消路径和 `acceptance`，不要只拿一段视觉描述。
6. 用语义匹配识别术语、同义词、相关维度和缺失参数。
7. 把匹配结果翻译成用户能看懂的解释，输出 3～6 个可执行方向。
8. 只询问会改变方案的问题；用户确认后再生成最终增强提示词。

运行时查询示例：

```bash
python3 scripts/query-index.py "删除列表项，5 秒内撤销并支持键盘"
```

不要直接读取 `terms/` 全目录，也不要把所有叶子包一次性塞进上下文。没有命中时，先说明覆盖不足；只有用户允许时才进行网络搜索。

## 知识类型

叶子包用 `knowledge_type` 区分：

- `term`：专业术语和白话解释
- `pattern`：可复用的设计/架构模式
- `technique`：实现技巧和参数锚点
- `guideline`：可访问性、质量和边界规范
- `parameter`：设计或运行参数
- `template`：可直接投喂给 AI 的提示词模板
- `platform-research`：平台专属研究，必须标注范围和核验状态

没有匹配到术语包时，说明覆盖不足；只有在用户允许时才进行网络搜索。搜索结果是本次临时参考，不写回术语列表。

## AIGC IP 模板

当请求涉及同一角色的多种材质、动作、表情或周边时，先读取 `templates/aigc/base-ip.json`，再按场景读取一个 `templates/aigc/*.json`。合并基础 IP、一致性约束、场景模块和目标工具参数；不要把七个场景全部加载到同一次请求中。中文文字建议预留排版区域，由后期工具叠加。

`terms/character-ip/character-ip.json` 只负责角色一致性和场景路由；镜头、构图、运动、负面约束和工具适配分别从对应子域加载。

## 交互、视觉效果与工具适配

连续交互和高级手势一次只加载一个模式。先读状态机、触发阈值、取消/回退路径，再读参数和验收标准；不要把整组交互一次性塞入上下文。默认要求动画可中断、键盘和触摸结果一致，并遵守 `prefers-reduced-motion`。

视觉效果必须和性能一起加载。液态玻璃、景深、圆柱卷收、取色光晕和液态粘连都要同时读取 `performance_budget`、`fallback`、`mobile_degradation` 和 `reduced_motion` 字段；如果设备能力不足，先降级表现再保证主任务可用。

GSAP 适配只在用户明确指定 GSAP，或项目已经依赖 GSAP 时加载。优先使用工具对应叶子的生命周期、SSR 边界、`ctx.revert()`/销毁规则和 transform 性能约束；未指定 GSAP 时不要主动引入它。

设计系统预览优先加载 `living-style-guide-preview`，用 Light/Dark、token、组件状态和视觉验收清单指导实现。外部预览站、厂商文档和示例仓库必须保留 `verification_required`，未核验时只能作为参考线索。

## 平台研究边界

`platform-research` 叶子包只记录指定供应商或项目的研究信息。若 `verified_at` 为空，必须把内容说成待核验信息，不得推广为所有 GPU UI 框架或所有平台的通用事实。
