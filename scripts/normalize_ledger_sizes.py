#!/usr/bin/env python3
"""台账 size 口径归一：全表按 python len(text) 字符重测，并标 size_measured_version。

为什么需要（本脚本存在的全部理由）：
- 早期台账条目混进过 n×1024 取整合约数（8192 / 10240 / 18432 / 22528 / 24576 …）——
  既不是字符也不是字节，正常核对认不出；拿它当 Δ 基线会算出假缩水（18432 对实测 9,868
  → 假 -45%，看起来像「大幅瘦身」，掩盖真实体量变化）。
- size 是 skill 臃肿的烟感表，口径必须唯一：python len(text) 字符；
  禁用 read_file 的 file_size 与 wc -c（中文文件字节≈3×字符，混比必出假警报）。

用法：
    python3 normalize_ledger_sizes.py [ledger.json] [skills_root]
    默认：~/workspace/skill-acceptance/ledger.json 与 ~/.hermes/skills

行为（就地写回 ledger.json，幂等可重跑）：
- 只更新**已有 size 字段**的条目：size = 当前 SKILL.md 字符数，并加 size_measured_version
- 顶层写 _meta.size_convention / size_normalized_at
- `version` 字段语义不动（= 上次验收时的版本），重测常发生在它之后，两者分开记
- 找不到 SKILL.md 的条目跳过并打印（人工判：skill 改名 / 已删）
- 打印改动表与 n×1024 脏值探测结果；无改动则明确报「已是字符口径」
"""
import datetime
import glob
import json
import os
import re
import sys

LEDGER = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    "~/workspace/skill-acceptance/ledger.json")
SKILLS = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/.hermes/skills")

convention = "python len(text) 字符（禁用 file_size/wc -c：那是 UTF-8 字节）"


def find_skill_md(name):
    hits = glob.glob(os.path.join(SKILLS, "**", name, "SKILL.md"), recursive=True)
    return hits[0] if hits else None


def frontmatter_version(text):
    m = re.search(r"^version:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else "?"


def looks_like_kib_artifact(n):
    """n×1024 取整合约数（仅指早期脏值形态，非字符非字节）。"""
    return isinstance(n, int) and n >= 4096 and n % 1024 == 0


def main():
    with open(LEDGER, encoding="utf-8") as f:
        ledger = json.load(f)

    rows, changed, skips, kiib = [], 0, [], []
    for name, entry in list(ledger.items()):
        if not isinstance(entry, dict) or "size" not in entry:
            continue
        path = find_skill_md(name)
        if not path:
            skips.append(name)
            continue
        text = open(path, encoding="utf-8").read()
        old = entry.get("size")
        if looks_like_kib_artifact(old):
            kiib.append((name, old))
        entry["size"] = len(text)
        entry["size_measured_version"] = frontmatter_version(text)
        if old != entry["size"]:
            changed += 1
        rows.append((name, old, entry["size"], entry["size_measured_version"]))

    ledger["_meta"] = ledger.get("_meta", {})
    ledger["_meta"]["size_convention"] = convention
    ledger["_meta"]["size_normalized_at"] = datetime.date.today().isoformat()
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)

    print(f"{'skill':30} {'旧size':>8} {'新size':>8}  size_measured_version")
    for name, old, new, ver in rows:
        flag = "  ← 校正" if old != new else ""
        print(f"{name:30} {str(old):>8} {str(new):>8}  {ver}{flag}")
    print(f"\n改动 {changed} 条｜脏值（n×1024）探测：{kiib or '无'}")
    if skips:
        print(f"跳过（未找到 SKILL.md，人工判改名/已删）：{skips}")
    if not changed and not kiib:
        print("已是字符口径，无需归一。")


if __name__ == "__main__":
    main()
