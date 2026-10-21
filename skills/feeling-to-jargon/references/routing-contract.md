<!-- Generated from docs/routing-contract.md; do not hand-edit. -->
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

## 可选宿主输入（结构校验；真实宿主结果见复审报告）

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

初版优化运行了原始 CLI、关闭快路径对照、依赖/预算端到端与模拟 host JSON。后续复审增加了实际安装后的真实 Codex 宿主、原话回退与确认后的多轮交付，记录在 `docs/evaluation/review/report.md`；这不等于所有宿主或最终网站/后端产品均通过验收。CLI 不自行认证宿主语义；GitHub 文档截图只验证发布后的说明。

## 安装入口与紧凑交付（复审补充）

安装包是完整 Skill，而不是要求用户保留源码仓库。以 SKILL.md 的实际目录作为 `SKILL_DIR`，在任意消费项目调用：

```bash
python3 <SKILL_DIR>/scripts/query.py "网站像赶集，眼睛没地方落" --format agent
python3 <SKILL_DIR>/scripts/query.py --catalog "信息 留白"
python3 <SKILL_DIR>/scripts/query.py --resource templates/aigc/base-ip.json --format agent
```

`--format full` 保留原兼容 JSON 和诊断信息；`--format agent` 使用紧凑序列化，删除重复诊断/场景外壳，不裁剪 `matches / dependencies` 的正文与关键约束。`--catalog` 只返回有限数量的已有 ID 和名称，不是语义判断；`--resource` 只读取一个明确的逻辑 JSON 引用，禁止拿整个索引代替按需加载。

宿主需要补充候选或确认信息时，从 stdin 传 JSON，避免临时上下文文件：

```bash
printf '%s' '{"candidates":[{"leaf_id":"composition-patterns","entry_id":"composition-patterns","evidence_text":"网站像赶集","role":"suggestion"}]}' |
  python3 <SKILL_DIR>/scripts/query.py "网站像赶集，眼睛没地方落" --context - --format agent
```

`choose:<exclusive_group>` 回答必须是该组的实际条目 ID，例如 `choose:dashboard-primary-layout = industrial-zones-dashboard`，组合器只加载已选方案；`source:*` 只接受真正存在的来源澄清项，不能用任意 entry ID 伪造已确认状态。

源码正文仍只有一份；`scripts/build-skill.py` 生成运行 ZIP 与随包契约，`--check` 校验派生包是否过期。启动器校验内容哈希、安全路径和资源总大小，直接从只读 ZIP 内导入 Python 并按需读取 JSON，不临时解包、不创建知识缓存或新数据库。


## Feeling-first terminology previews (2026-10-21)

`candidate_terms` is the user-facing terminology surface, not a mandate to load more leaves. `terms` are verbatim source-backed selections, with literal user expressions, applicability, role and source ID. `knowledge_loaded=false` explicitly means implementation constraints have NOT been loaded. Offer conditional explanations first, then ask only a scope question; do not turn source example numbers/materials into defaults.

Author optional `retrieval.feelings` beside the owning entry. Prefer `rule_ref` to reuse an existing scoped rule: the generator derives feeling groups from its non-subject groups and applicability from its subject group; do not maintain a second copy of the same cue list. Reuse conjunctive `all`, `scope_any`, `exclude_any` and the evidence matcher. `terms` must quote existing canonical name/definition/parameters (validator enforced); the generator projects them, no independent thesaurus. Short cue-only inputs may preview directions without a domain; named nonmatching objects are not silently treated as UI/services. An explicit same-clause matching scope seeds normal routing/composition. `context.answers.feeling_scope` accepts only an authored scope (e.g. 页面/按钮/后端), then uses the original feeling to load the chosen domain through the same composer. Provider-specific knowledge is never activated by feelings alone.

Preview limits are centralized in `routing_policy.py`: at most four unloaded directions, four terms per direction, definition capped at 120 characters. Loaded entries remain represented even if they exceed the optional preview count; their existing body limits still apply. `omitted_directions` reports optional preview clipping. Required constraints are not preview text and remain atomic under the body budget.

`output_cost` reports compact JSON Unicode character counts before adding its own cost object, plus terminology, explanations and knowledge component sizes. This is not tokens or billing. Actual printed full/compact lengths and real-host tool-output counts are measured separately in evaluation; index reads are not model-context payloads.

Feeling previews keep the original clause around modifiers such as 再稳一点; they must not strip a named object by treating 再 as a topic break. Bare ambiguous 后台 does not select Dashboard styles without design evidence; the routing policy centralizes this gate. Preview terms do not turn an uncovered second request into a covered one, and preview-only output never claims knowledge bundles have been assembled.
