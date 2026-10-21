# Feeling-first review and acceptance — 2026-10-21

## Outcome and boundary

Implemented and tested **short feeling → several source-backed terminology directions → only necessary clarification → existing knowledge composition**. Users no longer need to supply a professional title to get useful candidates for the supported feelings. This is not universal semantic search: unseen idioms still miss in the raw CLI, and installed-host interpretation is a separate, measured capability.

No new knowledge leaves, external services, vector database, runtime model calls, dependencies, branches or worktrees. The corpus remains **19 domains / 105 leaves / 120 entries**, four existing scene recipes, and the existing five authored Dashboard layouts. The generic overview entry is not a sixth layout.

## Reproduction and minimal changes

Baseline is `67987bb`; the clean working tree was inspected and `git pull --ff-only` completed before editing. `before.json` preserves original CLI outputs before the change. Fixed 20-case inputs are in `tests/fixtures/short-feelings.json`. Expected IDs/status/forbidden metadata was completed after freezing outputs; the erroneous initial target `concurrency-capacity` was corrected to the existing `capacity-model`, without rewriting baseline outputs. These are engineering acceptance cases, not independent user research.

Before this review, “太挤了 / 没重点 / 有呼吸感 / 稳一点 / 像弹簧一样 / 顺滑一点” returned no knowledge. “有质感一点 / 太乱了” asked about scope but supplied no terminology first. Scoped rules were useful but insufficient for short feeling inputs.

Changes:

1. **A terminology surface, not extra body loading.** `candidate_terms` contains readable terms, short source definitions, original matched expressions, stable source IDs, applicability, suggestion/explicit role and `knowledge_loaded`. Optional previews have no implementation authority. Full and compact formats preserve identical candidates and knowledge.
2. **One maintenance location.** `retrieval.feelings` lives on its owning entry. Where scoped rules already exist, `rule_ref` reuses them; the generator projects their non-subject cues and subject scope instead of creating a second synonym dictionary. Validator checks that selected terms occur in existing name/definition/parameters. Knowledge facts/parameters were not rewritten.
3. **Reuse composition.** A matching explicit object or validated `context.answers.feeling_scope` sends the cue into the existing router/composer. `information-hierarchy` joins the existing visual-brief recipe, not a new scenario. Required dependencies, source provenance, conflicts, count/character budgets and Dashboard selection remain intact.
4. **Central limits and accounting.** At most four unloaded candidate directions, four terms per direction, 120 definition characters. Clipping is reported. Existing loaded knowledge retains its own limits. `output_cost` reports actual compact Unicode character counts, not calibrated probabilities, tokens or billing estimates. Preview-only output cannot claim bundles have been assembled, and a supported first clause cannot hide an uncovered second request.
5. **Review repairs.** Preserve subjects around “再稳一点” (previous splitting allowed the chair’s “稳” to become service availability). Named offices/chairs and academic papers must not become UI/service matches. Ambiguous “后台” without design evidence no longer loads eight Dashboard/style leaves; existing explicit design requests retain their regression behavior.

Example actual outputs:

| Raw input | Source-backed candidates | Detailed leaves loaded |
|---|---|---:|
| 太挤了 | 留白、比例；信息层级、主任务优先 | 0 |
| 有质感一点 | 文字层级、主强调色、圆角/阴影、卡片材质 | 0 |
| 稳一点 | 高可用模式、故障转移、RTO/RPO, conditional on service scope | 0 |
| 顺滑一点 | 速度继承、减速、吸附；可中断与恢复, conditional on interaction scope | 0 |

These are alternatives/directions, not instructions to implement every term. In particular, stability does not imply concurrency/scaling/idempotency, and quality does not imply dark/glass/gradient. Interaction-smoothness candidates do not diagnose FPS or general scrolling performance.

## Same-input and held-out results

Detailed inputs, outputs, counts and timings are retained in `comparison.json`, `after.json`, `holdouts*.json` and `untouched.json`.

| Dataset | Positive cases with all expected directions | Listed forbidden-item violations | Notes |
|---|---:|---:|---|
| Frozen 20 before | 2 / 16 via bodies or terms | 0 / 20 | No dedicated terminology surface existed |
| Same 20 after | 16 / 16 | 0 / 20 | 20 / 20 expected statuses |
| Extra 24 initial | 12 / 16 | 2 / 24 | Found office/chair scope leakage; also manually found irrelevant Dashboard fan-out |
| Same extra 24 after safety fixes | 12 / 16 | 0 / 24 | A replay, **not untouched blind data**; status target agreement 18 / 24 |
| Further untouched 12 | 5 / 8 | 0 / 12 | No cue/route tuning after observation; status target agreement 8 / 12 |

All sets were engineer-authored. “Forbidden violations = 0” is only the prelisted checks, **not proof of zero false positives or measured universal precision**. Fixed status expectations also do not replace semantic acceptance: an ambiguous description of scrolling may reasonably require distinguishing performance from motion continuity rather than automatically selecting the fixture's proposed gesture knowledge.

Remaining raw-CLI misses include “屏幕像早高峰，眼睛没地方落”, “后台别在大家一起来的时候趴窝”, “滑起来别一顿一顿”, “按钮压下去以后想让它自己弹回来”, and untouched “整体有些喘不过气 / 网页密密麻麻，好累 / 按下去有点韧劲”. Do not copy these complete sentences into a growing keyword table to claim blind-test success. Conservative cue-only handling deliberately rejects unknown named subjects; the host must interpret or clarify them.

## Output cost — improvement is not free

The same 20 cases average **1,261.5 → 2,321.9 compact output characters**. This increases by about **84%**, rather than reducing output cost versus the mostly-empty baseline. New terminology averages 425.7 characters; knowledge body averages 132.3 → 289.1 characters; average loaded leaves 0.20 → 0.45. Supported bare-feeling examples above still load zero detailed leaves. Median internal routing was about 23–24 ms in the final run; timings are single-machine observations, not a performance guarantee.

The old 30 user-outcome cases still pass. Current full vs compact averages are **8,949.5 vs 3,701.6 characters (58.64% smaller)**, with exact source bodies and dependencies preserved. Previous review's compact mean was 2,855.4: adding terminology incurs roughly 30% extra compact cost on this existing set. The previous-review 30 cases also pass and average 7,041.9 full / 2,864.9 compact characters. See `regression-cost.json`.

Counters distinguish body, terminology, explanation and whole compact serialization. Printed full JSON adds whitespace; `output_cost` excludes its own accounting object from its payload count. Internal index scanning is not model-context loading. No character-to-token conversion or marginal model-billing claim is made.

## Actual installed-host acceptance

Five recorded actual Codex host turns are in `host-evidence.json`, using inherited local model configuration, copied installation through `skills@1.7.4`, and the real read-only sandbox. No model override, synthetic “LLM” answer, or repository-access fallback was used. Final `verified` evidence records the exact bundled runtime SHA256; prior runs are explicitly labelled in-session snapshots.

- **Short feeling:** “太挤了” produces conditional terminology and explanation first, then one scope question; no detailed body is loaded. Final installed runtime retest did the same.
- **Real resumed conversation:** user identifies a website and prioritizes making the first action obvious. Host loads existing information hierarchy and layout knowledge, supplies professional terms, a usable requirements paragraph and acceptance checks, and does not impose dark/glass/gradient or fixed numeric parameters. It explicitly says a requirements answer is not a tested website. CLI still reports partial coverage; the recorded answer does not make that a full semantic proof.
- **Metaphor recovery:** host maps “后台别在大家一起来的时候趴窝” to the existing capacity and availability entries with original-query evidence. Availability remains conditional; it does not load idempotency or prescribe a stack.
- **Honest limit:** for “滑起来别一顿一顿”, host distinguishes FPS, loading pauses and motion continuity, says the installed knowledge does not establish a general scrolling-performance implementation, and asks for interaction/device scope rather than inventing one.
- **Short stability / quality:** host first gives applicable terminology, explicitly marks ambiguity, and does not equate quality with glass/gradient or stability with all backend attributes.

Captured host tool-output characters by turn: 6,913 (initial short), 23,685 (resumed), 21,130 (three-request holdout), 8,563 (stability/quality), 6,844 (final runtime retest). These include Skill/guide reads and OS warnings; large catalogs in the resumed run show **remaining explanation/discovery overhead**, not an optimized universal cost ceiling. Total reported model tokens include global instructions/history/cache and are not the marginal cost of Jargon.

Some multi-command host events omit an earlier command's captured JSON. The visual-metaphor final answer is recorded, but missing payloads must not be treated as proof of full knowledge-body delivery. Final short-input acceptance used a separately captured invocation. User-facing text and CLI outputs were reviewed directly; no website UI was built, so there is no fabricated screenshot or claim of rendered-product acceptance. Other hosts/platforms are unverified.

## Regression and verification

Completed successfully:

- `python3 -B scripts/test-progressive-index.py`: 22 scenarios, all 105 title-addressability checks, 10 Dashboard tests, 10 user-outcome groups, 12 previous-review groups, 8 new feeling-preview groups.
- `python3 -B scripts/validate-routing.py`
- `python3 -B scripts/validate-index.py`
- `python3 -B scripts/build-skill.py --check`
- `python3 -B scripts/verify-host-review.py`
- `python3 -B scripts/verify-feeling-host.py` (offline verification of actual recordings; **not** a fresh model call)
- Skill creator `quick_validate.py`, and `git diff --check`.

New tests cover source-backed terms, cue/source reuse, multi-term preview without body fan-out, scope-answer roundtrip, wrong domain/negation/cross-topic leakage, bounded previews and explicit clipping, uncovered second requests, required dependency closure, tiny-budget staging, exact full/compact/source/installed-ZIP parity, and deterministic output-cost accounting.

## Changed areas and follow-up

- Runtime: `scripts/feeling_preview.py`, `retrieval.py`, `query-index.py`, `output_formats.py`, `routing_policy.py`.
- Generation/checks: `retrieval_index.py`, `validate-routing.py`, `build-skill.py`, generated `index/retrieval.json` and Skill distribution.
- Existing source metadata: seven existing leaf files, `templates/scenarios.json`; no leaf additions.
- Host instructions/contract: installed `SKILL.md`, canonical `docs/routing-contract.md` and generated installed reference.
- Acceptance: new feeling tests/evaluator, real-event collector/verifier, three fixtures, and persistent sanitized evidence in this directory. Raw temporary consumer/log artifacts are removed after preservation.

Next useful work is independent user testing, broader actual-host paraphrase acceptance, reducing catalog/explanation overhead without hiding uncertainty, and better handling of short feelings with unknown objects. No claim of exhaustive natural-language understanding. No need to add leaves to make these improvements.
