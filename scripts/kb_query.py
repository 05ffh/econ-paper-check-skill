#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M1 · KB 检索路由（v1）· 供 skill 主流程调用

补齐清单对齐:
- P0-8: A/B/C 三路由检索
  · A 路由 → 规范层 KB-A（norms/）→ 判红黄绿的权威依据
  · B 路由 → 范例层 KB-B（Chroma examples_v1）→ 仅作改进参照
  · C 路由 → 无匹配 fallback → 明确"未找到参照"
- P0-3: 严格分层（B 路由结果强制标注 can_be_error_evidence=false）
- P0-9: 通过 kb_ingest 复用 EmbeddingProvider（不锁死）
- 原则 1 红线: 每个 B 路由结果附 notice「范例仅作改进参照，不作错误判定唯一依据」

用法:
  # CLI 单次查询
  python3 scripts/kb_query.py --query "文献综述部分应该怎么写" --topk 3

  # 带过滤
  python3 scripts/kb_query.py --query "DID平行趋势检验" --method DID --topk 5

  # 输出 JSON（供 skill 消费）
  python3 scripts/kb_query.py --query "..." --json

  # 交互式验证
  python3 scripts/kb_query.py --interactive

  # Python 调用
  from scripts.kb_query import search, KBQuery
  kbq = KBQuery()
  results = kbq.search("文献综述怎么写", topk=3)
"""
from __future__ import annotations
import json, os, sys, argparse, warnings
from pathlib import Path
from datetime import datetime, timezone
warnings.filterwarnings("ignore")

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

ROOT = Path("/root/.openclaw/workspace/econ-paper-check-skill")
sys.path.insert(0, str(ROOT))

VDB_ROOT = ROOT / "knowledge_base/vector_db/active"
NORMS_ROOT = ROOT / "knowledge_base/norms"  # KB-A 规范层（未来）

# 复用 kb_ingest 的 EmbeddingProvider 和 config
from scripts.kb_ingest import EmbeddingProvider, EMBEDDING_CONFIG, get_chroma

# ===================== 常量 =====================

KB_B_NOTICE = "范例仅作改进参照，不作错误判定唯一依据；如需权威依据请查规范层（KB-A）"
KB_A_NOTICE = "规范层结果可作为红黄绿判定依据"
DEFAULT_MIN_SIMILARITY = 0.30  # 距离 = 1 - cos，0.30 大约对应 cos≈0.70

# ===================== KBQuery 主类 =====================

class KBQuery:
    """检索路由器"""

    def __init__(self, embedding_cfg=None, min_similarity=DEFAULT_MIN_SIMILARITY):
        self.provider = EmbeddingProvider(embedding_cfg or EMBEDDING_CONFIG)
        self.min_similarity = min_similarity
        self._client = None
        self._coll = None

    def _get_coll(self):
        if self._coll is None:
            self._client = get_chroma()
            try:
                self._coll = self._client.get_collection("examples_v1")
            except Exception as e:
                raise RuntimeError(f"KB-B collection 未创建，请先跑 kb_ingest: {e}")
        return self._coll

    # ---------- A 路由 · 规范层（占位）----------
    def query_norms(self, query: str, topk: int = 5) -> list[dict]:
        """
        A 路由：规范层 KB-A 检索（红黄绿判定依据）

        当前 KB-A 尚未起草，返回 stub；未来实现后此方法即接入。
        """
        if not NORMS_ROOT.exists():
            return []
        # TODO: 起草 KB-A 规范层后实现（norms/writing/, citation/, methods/ 等）
        return []

    # ---------- B 路由 · 范例层 ----------
    def _fetch_neighbors(self, paper_id: str, start_chunk_no: int, n: int = 2) -> list[dict]:
        """取指定论文中，chunk_no > start_chunk_no 的紧邻 n 个 body chunk
        用于 section_header 命中时展开正文。"""
        coll = self._get_coll()
        # 拉后续 5 个，过滤出 body 类的 n 个
        r = coll.get(
            where={"paper_id": paper_id},
            include=["metadatas", "documents"],
            limit=1000,
        )
        if not r or not r.get("ids"): return []
        picks = []
        pairs = list(zip(r["ids"], r["metadatas"], r["documents"]))
        # 按 chunk_no 排序
        pairs.sort(key=lambda x: (x[1] or {}).get("chunk_no", 0))
        for cid, m, doc in pairs:
            m = m or {}
            if m.get("chunk_no", 0) <= start_chunk_no: continue
            sec = m.get("section", "")
            if sec in ("body", "references"):
                picks.append({"chunk_id": cid, "meta": m, "text": doc})
                if len(picks) >= n:
                    break
            elif sec == "section_header":
                # 遇到下一个 header 就停
                break
        return picks

    def query_examples(self, query: str, topk: int = 3,
                        topic: str = None, method: str = None,
                        paper_type: str = None,
                        expand_header: bool = True) -> list[dict]:
        """
        B 路由：范例层 KB-B 检索（改进参照，非错误依据）

        参数:
            query: 查询文本
            topk: 返回 top-K
            topic: 主题硬过滤（如 "数字经济"），匹配 topic_hint 包含
            method: 方法硬过滤（如 "DID"），匹配 method_tags 包含
            paper_type: 论文类型过滤（theoretical / empirical）
        """
        coll = self._get_coll()

        qvec = self.provider.embed_query(query)

        # Chroma metadata filter（$contains 不支持字符串包含匹配，改为拉大 topk 后 Python 侧过滤）
        # 但 paper_type 是精确匹配，可以下推
        where = None
        if paper_type:
            where = {"paper_type": paper_type}

        # 为了后过滤，拉更多结果
        fetch_k = topk * 5 if (topic or method) else topk * 2

        r = coll.query(
            query_embeddings=[qvec],
            n_results=min(fetch_k, 50),
            where=where,
            include=["metadatas", "distances", "documents"],
        )

        results = []
        if not r["ids"] or not r["ids"][0]:
            return results

        for i in range(len(r["ids"][0])):
            cid = r["ids"][0][i]
            dist = r["distances"][0][i]
            m = r["metadatas"][0][i] or {}
            doc = r["documents"][0][i]

            # 距离阈值
            if dist > (1.0 - self.min_similarity):
                continue

            # topic 软过滤（子串匹配）
            if topic and topic not in (m.get("topic_hint", "") or ""):
                continue

            # method 软过滤（method_tags 是逗号分隔字符串）
            if method:
                mt = (m.get("method_tags", "") or "").lower()
                if method.lower() not in mt:
                    continue

            item = {
                "rank": len(results) + 1,
                "chunk_id": cid,
                "paper_id": m.get("paper_id", ""),
                "section": m.get("section", ""),
                "current_section": m.get("current_section", ""),
                "topic_hint": m.get("topic_hint", ""),
                "method_tags": m.get("method_tags", ""),
                "paper_type": m.get("paper_type", ""),
                "similarity": round(1.0 - dist, 4),
                "distance": round(dist, 4),
                "text": doc,
                "char_len": m.get("char_len", len(doc)),
                "meta": {
                    "kb_layer": "example_reference",
                    "can_be_error_evidence": False,
                    "admission_source": m.get("admission_source", "online_top_journal"),
                },
            }

            # section_header 命中 → 展开后续正文
            if expand_header and m.get("section") == "section_header":
                neighbors = self._fetch_neighbors(
                    m.get("paper_id", ""),
                    m.get("chunk_no", 0),
                    n=2,
                )
                if neighbors:
                    item["expanded"] = [
                        {
                            "chunk_id": n["chunk_id"],
                            "text": n["text"],
                            "char_len": n["meta"].get("char_len", len(n["text"])),
                            "section": n["meta"].get("section"),
                        }
                        for n in neighbors
                    ]

            results.append(item)
            if len(results) >= topk:
                break

        return results

    # ---------- 主入口 · 三路由决策 ----------
    def search(self, query: str, topk: int = 3,
               topic: str = None, method: str = None,
               paper_type: str = None,
               prefer: str = "auto") -> dict:
        """
        统一检索入口

        参数:
            prefer: "auto" | "A" | "B"
                auto → 先 A 再 B，A 有结果时 route=A；否则 route=B
                A    → 只查规范层
                B    → 只查范例层

        返回:
            {
                "query": ...,
                "route": "A" | "B" | "C",
                "results": [...],
                "notice": ...,
                "meta": {"topk": ..., "min_similarity": ...},
            }
        """
        out = {
            "query": query,
            "route": None,
            "results": [],
            "notice": "",
            "meta": {
                "topk": topk,
                "min_similarity": self.min_similarity,
                "filters": {"topic": topic, "method": method, "paper_type": paper_type},
                "queried_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # A 路由
        if prefer in ("auto", "A"):
            a_results = self.query_norms(query, topk=topk)
            if a_results:
                out["route"] = "A"
                out["results"] = a_results
                out["notice"] = KB_A_NOTICE
                return out
            if prefer == "A":
                out["route"] = "C"
                out["notice"] = "规范层（KB-A）尚未起草或无匹配"
                return out

        # B 路由
        b_results = self.query_examples(query, topk=topk,
                                          topic=topic, method=method,
                                          paper_type=paper_type)
        if b_results:
            out["route"] = "B"
            out["results"] = b_results
            out["notice"] = KB_B_NOTICE
            return out

        # C 路由：无匹配
        out["route"] = "C"
        out["notice"] = "未找到可用参照；建议扩大查询范围或调低 min_similarity"
        return out


# ===================== 模块级便捷入口 =====================

_default_kbq = None

def _get_default() -> KBQuery:
    global _default_kbq
    if _default_kbq is None:
        _default_kbq = KBQuery()
    return _default_kbq

def search(query: str, **kwargs) -> dict:
    """供 skill 主流程调用的模块函数"""
    return _get_default().search(query, **kwargs)


# ===================== CLI =====================

def format_result_human(res: dict, verbose=False) -> str:
    """人类可读输出"""
    lines = []
    lines.append("=" * 70)
    lines.append(f"🔎 Query: 「{res['query']}」")
    lines.append(f"   Route: {res['route']} · "
                 f"Filters: {res['meta']['filters']} · "
                 f"topk={res['meta']['topk']}")
    lines.append(f"   Notice: {res['notice']}")
    lines.append("=" * 70)

    if not res["results"]:
        lines.append("  ⚠️  无结果")
        return "\n".join(lines)

    for r in res["results"]:
        lines.append(f"\n  #{r['rank']}  {r['chunk_id']}  (sim={r['similarity']})")
        lines.append(f"      paper_id: {r['paper_id']} · "
                     f"section: {r.get('section','')} · "
                     f"current: {r.get('current_section','')[:40]}")
        lines.append(f"      topic: {r['topic_hint']} · "
                     f"method: {r.get('method_tags','')} · "
                     f"type: {r.get('paper_type','')}")
        preview = r["text"].replace("\n", " ")
        if not verbose and len(preview) > 180:
            preview = preview[:180] + "..."
        lines.append(f"      text: {preview}")
        if r.get("expanded"):
            for ex in r["expanded"]:
                ex_preview = ex["text"].replace("\n", " ")
                if not verbose and len(ex_preview) > 200:
                    ex_preview = ex_preview[:200] + "..."
                lines.append(f"      ↳ {ex['chunk_id']}: {ex_preview}")
        lines.append(f"      ⚠️  can_be_error_evidence: {r['meta']['can_be_error_evidence']}")
    return "\n".join(lines)


def interactive_loop(kbq: KBQuery):
    print("🔍 KB 交互式检索 (输入 :q 退出，:help 帮助)")
    print("=" * 60)
    while True:
        try:
            q = input("\nquery> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye"); break
        if not q: continue
        if q in (":q", ":quit", "exit"): break
        if q == ":help":
            print("直接输入查询，或 :q 退出")
            continue
        try:
            res = kbq.search(q, topk=3)
            print(format_result_human(res))
        except Exception as e:
            print(f"❌ {e}")


def main():
    ap = argparse.ArgumentParser(description="KB 三路由检索")
    ap.add_argument("--query", "-q", help="查询文本")
    ap.add_argument("--topk", "-k", type=int, default=3)
    ap.add_argument("--topic", help="主题过滤（子串）")
    ap.add_argument("--method", help="方法过滤（如 DID）")
    ap.add_argument("--paper-type", choices=["theoretical", "empirical"])
    ap.add_argument("--prefer", choices=["auto", "A", "B"], default="auto")
    ap.add_argument("--min-sim", type=float, default=DEFAULT_MIN_SIMILARITY)
    ap.add_argument("--json", action="store_true", help="JSON 输出（供 skill）")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--interactive", "-i", action="store_true")
    args = ap.parse_args()

    kbq = KBQuery(min_similarity=args.min_sim)

    if args.interactive:
        interactive_loop(kbq)
        return

    if not args.query:
        ap.error("--query 必填（或用 --interactive）")

    res = kbq.search(
        args.query,
        topk=args.topk,
        topic=args.topic,
        method=args.method,
        paper_type=args.paper_type,
        prefer=args.prefer,
    )

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(format_result_human(res, verbose=args.verbose))


if __name__ == "__main__":
    main()
