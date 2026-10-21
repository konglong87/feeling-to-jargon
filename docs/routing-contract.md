# CLI、场景交付与宿主 LLM 的边界

## 调用

```bash
python3 scripts/query-index.py "我想做一个有质感的网站"
python3 scripts/query-index.py "删除后可以反悔" --max-leaves 1
python3 scripts/query-index.py "工业分区布局" --max-entries 1 --max-chars 12000
python3 scripts/query-index.py "我想做一个有质感的网站" --no-fast-path
```

不调用外部模型/服务/向量库。`--no-fast-path` 只关闭路由短路，仍使用相同知识组合、场景交付与验收协议，以便公平比较。新增字段向后兼容 `query / strategy / matches / trace / network_search`；排序可能因消除误召回变化。

## 输出的使用顺序

1. `status / coverage`：`ready`（可组织方案）、`needs_clarification`、`partial_coverage`、`coverage_insufficient`、`needs_verification`、`needs_staging`。
2. `explanations`：具体匹配表达、来源字段与来源路径，`explicit` 或 `suggestion`。共享词不能替代需求证据；排序分数不代表语义概率。
3. `delivery.scenario_plans`：触发后的流程、已提供/仍需的信息、输出字段与验收。明确命中可直接复用组合，部分命中只补改变方案的问题。
4. `matches / dependencies`：正文与共享协议。正文的检索规则不重复送入输出；关键状态/性能/降级/减少动态/平台约束完整保留。`delivery.acceptance_sources` 指向原约束，不复制另一份事实。
5. `composition.conflicts / deferred`：互斥项只做选项；必要依赖放不下则原子组合不交付。分阶段是显式的未完成部分，不是成功的缩水结果。

预算针对 `matches + dependencies` 的紧凑 JSON 字符数，不是 token 或整个 JSON 响应。`trace.context_chars` 计数该部分（空知识包为 0）；完整输出另有解释、来源、澄清和交付开销，评测统计 `output_chars`。`internal_read_paths / internal_index_chars` 是程序内部读取；不表示这些索引已送入 LLM。

## 四个场景的维护

`templates/scenarios.json` 唯一维护流程元数据：触发/不适用条件、条目归属、需要的信息读取规则、输出结构、验收。正文仍在 `terms/`。新增白话组合仅在对应条目的 `retrieval.rules` 维护；复用原 `aliases / plain_language / when_to_use` 生成 `index/retrieval.json`。共享来源短语不能作为强入口；精确条目/显式组合优先于同叶子宽泛描述。

`composition.required` 是必需引用；`conditional` 只在显式条件命中时进入同一原子依赖闭包；`exclusive_group` 表示不可直接合并的主布局。`contract_ref` 继续沿用，Dashboard 只投影共享协议，不输出十套审美示例。松散 `related` 不自动展开。例子中的配色、栅格与时间不等于本次用户选值。

## 可选宿主输入（本轮只做协议模拟测试）

宿主可能比 CLI 更理解隐喻，但需要保留原话与证据，而不是假装 CLI 自带语义能力。宿主可将明确的既有上下文和解释写入 JSON，通过 `--context` 传入：

```json
{
  "providers": [],
  "answers": {"primary_task": "让用户一眼找到当前订单状态"},
  "candidates": [
    {
      "leaf_id": "composition-patterns",
      "entry_id": "composition-patterns",
      "evidence_text": "有呼吸感",
      "role": "suggestion"
    }
  ]
}
```

```bash
python3 scripts/query-index.py "网页需要更有呼吸感" --context context.json
```

- 只接受 `providers / answers / candidates`；候选最多 12 个，ID 必须存在，证据必须是原始输入的非空片段，角色必须明确。
- `answers` 的 slot ID 来自条目 `retrieval.questions` 或返回的来源澄清 ID；不能用未知字段假装已回答。直接读出的数值与 context 冲突时拒绝，不覆盖用户原话。
- `providers` 必须是既有供应商，并来源于用户明确提供的项目依赖；原话的排除条件优先，例如“不用 GSAP”覆盖项目上下文。
- 这只是结构/引用/证据范围验证，**不能证明宿主语义判断正确**。宿主证据标记 `host_interpretation_unverified`；`host_llm_workflow_verified` 保持 false。
- 解析或引用无效时 CLI 非零退出，宿主解释错误后去掉 context 重跑原话。仍无覆盖就承认，必要时请求资料；不通过反复改写制造命中。

## 验证边界

本轮实际运行原始 CLI、关闭快路径的对照、依赖/预算端到端与模拟 host JSON。没有运行真实宿主 LLM 的完整多轮工作流，也没有实现四种场景的真实网站/后端产品，因此不声称完成 Agent 或最终产品验收。GitHub 文档截图只验证发布后的说明，不替代 CLI 与业务验收。
