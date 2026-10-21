# 自然语言、真实宿主与输出成本复审

## 结论

基线 `c42dd4a`，先 pull、审计并冻结新用例，再修复。**不是“已有测试全绿就没问题”：这次真实安装和宿主调用额外暴露了分发、只读运行、证据作用域与目录可解释性的问题。** 已修复本轮可复现的代码问题；原始 CLI 仍有自然语言覆盖边界，宿主遵守调用预算也不能仅靠提示文本获得硬保证。

知识规模保持 **19 个领域、105 个叶子、120 个条目**。没有新建分类或知识叶子，没有引入向量库、外部检索服务、运行时模型调用或持久缓存。

## 修复的主要问题

| 级别 | 已复现的问题 | 修复与证据 |
| --- | --- | --- |
| P1 | 实际安装只复制 SKILL.md；资源依赖仓库路径，任意项目无法调用 | 生成完整分发包、绝对 Skill 入口；实际 `skills@1.7.4 --copy` 安装后验证 |
| P1 | 第一版分发启动器临时解包，被真实只读宿主拒绝 | 改为 ZIP 内导入与只读 JSON 加载，无解包写盘；保留失败后重跑成功 |
| P1 | 否定范围错误、跨对象拼证据、快路径漏掉第二项请求 | 正负分句、局部动作/对象证据、主题边界与非场景守卫；30 个冻结复审输入验证 |
| P1 | 回答布局选择后无法回填；虚构 source slot 可被接受；多分句宿主证据被误判未覆盖 | slot 校验与往返、来源问题按场景归属、完整原话证据可覆盖所属分句，仍标明宿主判断未由 CLI 语义认证 |
| P2 | JSON 解释重复、目录只显示名称，宿主反复搜索甚至漏掉状态复用 | 新增紧凑输出、有限 catalog 与来源摘要/领域/可复用字段；保留知识正文、依赖、流程、范围与验收 |

词法证据修复不是通用中文语义系统；少量新增动作表达仍在原条目的检索元数据中维护，没有把完整测试句子写进词库。正文事实与示例参数未被改写。

## CLI 盲测与回归

修改前冻结的新增 30 条输入，包含否定、跨分句、非软件对象、多意图、覆盖不足、模糊词、同族条目。预期在 `tests/fixtures/review-blind.json`，前后输出在 `before.json / after.json`。

| 指标 | 复审前 | 修复后 |
| --- | ---: | ---: |
| 30 条中缺少预期候选的用例 | 8 | 0 |
| 30 条中出现指定禁止项的用例 | 8 | 0 |
| 指定状态判断不符 | 2 | 0 |
| 既有 30 条输入中缺少必需候选 | 0 | 0 |
| 既有 30 条输入中出现禁止项 | 0 | 0 |

这 30 条经修复后已成为回归集，不能继续冒充未经适配的开放域盲测准确率。典型变化：

| 原话 | 复审前 | 修复后 |
| --- | --- | --- |
| 不用 GSAP，要让网页有质感 | 空；`coverage_insufficient` | token-system；`needs_clarification` |
| 不是 GPUIX，只是普通网页 | gpui-desktop-web, gpui-mobile；`partial_coverage` | 无候选；`coverage_insufficient` |
| 页面不要暗色玻璃，只想层次清楚 | 空；`coverage_insufficient` | composition-patterns；`needs_clarification` |
| 后端的文档在这里，我的椅子不稳定 | availability-patterns；`needs_clarification` | 无候选；`coverage_insufficient` |
| 很多人同时用这个洗衣间也别挤 | capacity-model；`needs_clarification` | 无候选；`coverage_insufficient` |
| 网站看着廉价，能不能做得更专业 | 空；`coverage_insufficient` | token-system；`needs_clarification` |
| 付款按钮多按几回，别扣好几笔 | 空；`coverage_insufficient` | idempotency-contract；`partial_coverage` |
| 这篇小说的提交情节重复太多 | idempotency-contract；`needs_clarification` | 无候选；`coverage_insufficient` |
| 手滑删错了还能撤回吗 | 空；`coverage_insufficient` | undo-window, motion-accessibility, reverse-animation；`needs_clarification` |
| 需要的是页面显得讲究些，不是暗色发光 | 空；`coverage_insufficient` | token-system；`needs_clarification` |
| 我想做一个有质感的网站，还要毛绒玩偶 | token-system；`partial_coverage` | token-system, character-ip；`needs_clarification` |
| 做工业分区布局再证明黎曼猜想 | layout-patterns；`needs_clarification` | layout-patterns；`partial_coverage` |
| 想要舒服又高级 | 空；`coverage_insufficient` | 无候选；`needs_clarification` |
| 在线服务断了也别影响大家继续操作 | 空；`coverage_insufficient` | availability-patterns；`needs_clarification` |
| 论文的页面看着乱，需要理清论证而非网站设计 | composition-patterns；`needs_clarification` | 无候选；`coverage_insufficient` |
| React 不依赖GSAP，只用原生CSS动画 | gsap-react-lifecycle；`partial_coverage` | 无候选；`coverage_insufficient` |
| 很多人用的服务，平时错峰，不存在同时访问 | capacity-model；`partial_coverage` | 无候选；`coverage_insufficient` |
| 不是要稳定后端，是要稳定的椅子 | availability-patterns；`needs_clarification` | 无候选；`coverage_insufficient` |

### 再追加 12 条、不为结果继续补映射

`additional-blind.json` 保留后续 12 条观测：10 条有相关知识的白话中，原始 CLI 只有 **4 条**给出候选，另 6 条返回不足；2 条非覆盖/非界面负例均没有被乱召回。

原始 CLI 仍未覆盖的例子包括“像弹簧一样回到原处”“按住不放才执行”“卡片停后画线”“切月图表更新”“换卧室控制跟着换”“删完能不能有后悔药”。这表明不能承诺所有白话只靠 CLI 就命中。本轮没有为了美化数字把这些完整句子再写成映射；其中按住、画线、月份三个缺口又通过下面的真实宿主流程验收。

## 真实宿主：实际运行，不是预写 context 模拟

环境：本机现有 Codex CLI `0.154.0-alpha.6.1`、继承用户现有模型配置、macOS/Python 3.9；在**消费项目的真实安装目录**内使用，只读沙箱，不允许回读父目录源码。默认 npm CLI 曾在本机异常退出，使用已有桌面捆绑 CLI 完成，没有更换模型。此处不是覆盖全部 Agent/操作系统的兼容承诺。

[脱敏命令、真实查询输出与模型最终回复](host-evidence.json) 保留了失败和复测，不能仅凭模型说“已运行”算通过；另用 `scripts/verify-host-review.py` 核对实际命令与返回值。

| 真实请求/步骤 | 实际结果 |
| --- | --- |
| “网站像赶集，眼睛没地方落” | 原话 CLI 未命中；宿主读取既有 ID 后原话回填，找到信息层级/留白等建议，未默认暗色或玻璃 |
| 同一会话补充“手机订单状态优先，只调层级和留白，配色不改” | 实际 resume 并再调用安装后的入口，返回 `ready`、无重复澄清；最终交付增强提示词与截图/E2E 验收，不声称页面已实现 |
| “按住不放才执行，提前松手就取消” | 原话不足；经 1 次 catalog、1 次建议回填，命中 `press-and-hold-confirm`，未把参考时长直接当需求 |
| “卡片停下来以后再画线” | 原话不足；经 2 次 catalog、1 次建议回填，命中 `snap-card-timeline`；仍询问是否吸附及空间锚点 |
| “切换月份后所有图表更新” | 初测误判不足且超查一次；增加来源摘要后最终独立复测经 **1 次 catalog** 找到 `glass-dot-matrix-dashboard` 的状态部分，原话建议回填成功，未套用配色/布局 |
| 不用 GPUIX、不依赖 GSAP，故障与重复付款 | 实际返回可靠性与幂等候选，没有引入被排除供应商；未附带并发/扩展要求 |
| 液态玻璃与移动端降级，正文预算 100 字符 | 实际返回 `needs_staging`，正文为 0，完整组合延后；没有仅输出外观而遗漏关键约束 |

**不能隐去的失败：**临时解包导致的真实安装失败、多分句证据导致的假“部分覆盖”、月份目录只看名字漏选，都保留了失败记录。早期一次宿主调用 catalog 超预算 1 次，宿主在最终回复中承认；最后月份复测只调用 1 次。当前每请求至多 2 次 catalog + 1 次候选重跑是宿主协议与测试观察，**并不是服务端硬性计费闸门**，仍需采样监督。部分调用出现供应商繁忙/重连，不能由这些单次观测推断稳定时延。

## 解释输出成本

`--format full` 向后兼容；Skill 默认要求 `--format agent`。逐例断言 `matches / dependencies` 完全相同，场景流程、范围排除、已知信息与验收规则也保留，只删除重复诊断/解释。字符不是 token。

| 同组输入 | 完整 JSON 平均字符 | 宿主紧凑输出平均字符 | 降低 |
| --- | ---: | ---: | ---: |
| 既有 30 条 | 7,604.7 | 2,855.4 | 62.45% |
| 新增 30 条 | 6,172.3 | 2,262.6 | 63.34% |

原“赶集”请求实际宿主工具输出观测：仓库基线 **23,336 字符 / 5 个命令**，安装后 **11,548 字符 / 4 个命令**；确认后再次交付只需 **1 次查询**。这是单次宿主行为观测，包含不同的工具选择，不是控制变量的 token/费用实验。

宿主 usage 原样记录在证据中，包含用户全局技能/配置、缓存与累计上下文：例如安装后第一轮 input_tokens=144,220、cached_input_tokens=83,968。不能把这些全部归因于本 Skill，更不能从输出字符下降推导同等幅度的模型费用节省。

本轮原始 CLI 的进程耗时中位数约 **51.9 ms**，复审前观测约 30 ms；范围校验有 CPU 成本，不宣称 CLI 延迟改善。主要收益是正确性、可部署性、减少工具上下文重复与有限的宿主检索过程。

## 回归与交付边界

通过既有 22 个场景、105 个标题检查、10 项 Dashboard、10 组用户效果，以及新增 12 组复审回归；新增测试包含分发复制、校验和损坏、stdin context、来源 slot、布局回填、目录限载、证据原文与紧凑格式保真。索引/检索投影/依赖图、分发包新鲜度、Python/JSON 与 Skill 校验通过。

原始宿主日志不提交：只保留脱敏的命令、真实返回和最终回复，删除消费项目、安装日志、临时上下文与字节码。运行时不会创建持久知识缓存。生成 ZIP/契约是可重建分发产物，不是第二套手工事实源。

**仍未验证：**其他宿主/平台、安装后的自动触发率、不同模型的大规模白话分布与多轮长期稳定性，以及真实网站/后端产品实现。此次 `ready` 只表示可交付方案信息，不代表产品已通过端到端验收。对没有测到的自然语言，不给 100% 召回或零幻觉保证。
