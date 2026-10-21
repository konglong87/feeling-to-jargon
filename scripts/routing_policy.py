"""Central CLI policies. Scores are heuristic ranks, never probabilities."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RETRIEVAL_INDEX = "index/retrieval.json"
SCENARIO_SOURCE = "templates/scenarios.json"
MAX_CONTENT_CHARS = 24000
MAX_QUESTIONS = 3
MAX_HOST_CANDIDATES = 12
EVIDENCE_SCORE = 12
IDENTITY_BONUS = 2
STATUS_READY = "ready"
STATUS_CLARIFY = "needs_clarification"
STATUS_UNCOVERED = "coverage_insufficient"
STATUS_PARTIAL = "partial_coverage"
STATUS_STAGING = "needs_staging"
NEGATION_MARKERS = ("不是", "不依赖", "不存在", "不采用", "无需", "不要", "不用", "不需要", "不使用", "不考虑", "禁止", "不做", "暂不", "without ", "not ")
CLAUSE_SEPARATORS = r"[，,。；！!;\n]|(?:而且|但是|然后|另外|此外|并且|顺便|还要|只想|只是|而非|而是|再(?=.{2,}))"
AMBIGUOUS_TERMS = ("稳定", "质感", "高级", "舒服", "乱", "专业", "精致")
COMPARISON_TERMS = ("比较", "对比", "选项", "或者", "二选一", "分别")
COMPOSITION_FIELDS = ("performance_budget", "fallback", "mobile_degradation", "reduced_motion", "acceptance")
CONTRACT_SECTIONS = ("field_contract", "shared_execution_contract")
BASE_OUTPUT_FIELDS = ("user_need", "candidate_terms", "explicit_vs_suggested", "open_questions", "constraints", "acceptance")

STATUS_VERIFY = "needs_verification"

CATALOG_LIMIT = 12
CATALOG_MAX_LIMIT = 30

TEXT_CACHE_SIZE = 2048

CATALOG_SUMMARY_CHARS = 160

CATALOG_PREFIX_CHARS = 2
CATALOG_IDENTITY_BONUS = 4
CATALOG_BODY_WEIGHT = 1
NEGATION_SCOPE_CHARS = 12
