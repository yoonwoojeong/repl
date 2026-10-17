"""Core-library re-proving benchmark: statements of `Nat`/`List` lemmas from Lean's own core
library (`data/library.json`), each to be proved *without* the lemma itself.

Why: the hand-written test sets were small (20 theorems) and written by a Claude model. These
statements were written by the Lean developers, and there are thousands of them, so a test set
of 100+ is possible without authoring anything.

Rules for a proof of the statement of lemma `L`:
- it must check in the core-only REPL environment, like every other proof here; and
- `Auditor` re-elaborates it in an `import Lean` environment and rejects it if the proof term
  directly uses `L` or any constant whose type is identical to the statement (an alias). Other
  lemmas, including ones proved from `L`, are allowed.

`screen` drops a statement as *easy* when a generic one-liner (see `one_liners`) proves it
without a banned constant.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time

from jev_demo.actions import _binder_names
from jev_demo.theorems import DATA_DIR

NAMESPACES = ("Nat.", "List.")
POOL_PATH = os.path.join(DATA_DIR, "core_pool.json")
SPLIT_PATHS = {s: os.path.join(DATA_DIR, f"core_{s}.json") for s in ("train", "dev", "test")}
# Second benchmark family (transfer test: the router is never trained on it): Int/Array/Option
# lemmas, premises from the extended library. Hash split 20% dev (pilot) / 80% test.
EXT_NAMESPACES = ("Int.", "Array.", "Option.")
EXT_LIBRARY_PATH = os.path.join(DATA_DIR, "library_ext.json")
EXT_POOL_PATH = os.path.join(DATA_DIR, "ext_pool.json")
EXT_SPLIT_PATHS = {s: os.path.join(DATA_DIR, f"ext_{s}.json") for s in ("dev", "test")}

_AUDIT = """theorem {name} : {statement} := by{body}

open Lean Meta in
#eval show MetaM Unit from do
  let env ← getEnv
  let some (.thmInfo v) := env.find? `{name} | IO.println "AUDIT:nothm"
  let banned : List Name := [{banned}]
  let mut bad : Array Name := #[]
  for c in v.value.getUsedConstants do
    if banned.contains c then
      bad := bad.push c
    else if let some ci := env.find? c then
      if ci.levelParams.length == v.levelParams.length then
        let t := ci.type.instantiateLevelParams ci.levelParams (v.levelParams.map Level.param)
        if t == v.type then
          bad := bad.push c
  IO.println s!"AUDIT:{{bad.toList}}"
"""


# Audit v2: also flags (a) any constant whose statement is *definitionally* equal to the target
# (catches aliases that differ only in binder kinds or universe names, which the exact-type check
# misses) and (b) "single-lemma proofs": the proof uses exactly one `Nat.`/`List.` theorem and no
# induction or case recursor, so it may be a near-restatement (reported, not rejected).
_AUDIT2 = """theorem {name} : {statement} := by{body}

open Lean Meta in
#eval show MetaM Unit from do
  let env ← getEnv
  let some (.thmInfo v) := env.find? `{name} | IO.println "AUDIT2:nothm"
  let banned : List Name := [{banned}]
  let mut bad : Array Name := #[]
  let mut defeq : Array Name := #[]
  for c in v.value.getUsedConstants do
    if banned.contains c then
      bad := bad.push c
    else if let some ci := env.find? c then
      if (← isProp ci.type) then
        let us ← ci.levelParams.mapM fun _ => mkFreshLevelMVar
        let t := ci.type.instantiateLevelParams ci.levelParams us
        if (← withNewMCtxDepth (isDefEq t v.type)) then
          defeq := defeq.push c
  -- single-lemma proof: exactly one Nat./List. theorem used, and no induction/case recursor
  let mut thms : Array Name := #[]
  let mut recs := 0
  for c in v.value.getUsedConstants do
    let s := c.toString
    if s.endsWith ".rec" || s.endsWith ".recAux" || s.endsWith ".casesOn" || s.endsWith ".casesAuxOn"
        || s.endsWith ".brecOn" || s.endsWith ".recOn" then
      recs := recs + 1
    else if ({ns}) && !banned.contains c then
      if let some (.thmInfo _) := env.find? c then
        thms := thms.push c
  let one := if thms.size == 1 && recs == 0 then thms[0]!.toString else ""
  IO.println s!"AUDIT2:{{bad.toList}}|{{defeq.toList}}|{{one}}"
"""


def _names(s: str) -> list[str]:
    return [x.strip() for x in s.strip().strip("[]").split(",") if x.strip()]


def _body(tactics: list[str]) -> str:
    return "".join(f"\n  {t}" for t in tactics)  # same layout as ReplClient.check_proof


class Auditor:
    """Rejects proofs that use a banned constant. Owns one REPL with `import Lean`."""

    def __init__(self, repl):
        self.repl = repl
        reply = repl.command("import Lean", fresh=True, timeout_s=300)
        if "env" not in reply:
            raise RuntimeError(f"could not import Lean in the auditor REPL: {reply}")
        self.env = reply["env"]
        self._n = 0

    def violations(self, statement: str, tactics: list[str], banned: tuple[str, ...],
                   prelude: str = "") -> list[str] | None:
        """Banned or alias constants the proof uses ([] = clean), or None if the audit itself
        failed (the proof did not re-elaborate, or the REPL timed out): treat None as rejected."""
        self._n += 1
        cmd = _AUDIT.format(name=f"audit_{self._n}", statement=statement, body=_body(tactics),
                            banned=", ".join(f"`{b}" for b in banned))
        if prelude.strip():
            cmd = prelude + "\n\n" + cmd
        reply = self.repl.command(cmd, env=self.env, timeout_s=60)
        msgs = reply.get("messages", [])
        if any(m.get("severity") == "error" for m in msgs) or reply.get("sorries"):
            return None
        for m in msgs:
            data = m.get("data", "")
            if data.startswith("AUDIT:"):
                out = data[len("AUDIT:"):].strip()
                if out == "nothm":
                    return None
                return [s.strip() for s in out.strip("[]").split(",") if s.strip()]
        return None


def analyse(auditor: "Auditor", statement: str, tactics: list[str], banned: tuple[str, ...],
            prelude: str = "", namespaces: tuple[str, ...] = NAMESPACES) -> dict | None:
    """Audit v2 of one proof: `{"banned": [...], "defeq_aliases": [...], "one_lemma": name|None}`,
    or None if the proof did not re-elaborate in the auditor. A one-lemma proof uses exactly one
    theorem from `namespaces` (and no recursor)."""
    auditor._n += 1
    ns = " || ".join(f's.startsWith "{n}"' for n in namespaces)
    cmd = _AUDIT2.format(name=f"audit2_{auditor._n}", statement=statement, body=_body(tactics),
                         banned=", ".join(f"`{b}" for b in banned), ns=ns)
    if prelude.strip():
        cmd = prelude + "\n\n" + cmd
    reply = auditor.repl.command(cmd, env=auditor.env, timeout_s=120)
    msgs = reply.get("messages", [])
    if any(m.get("severity") == "error" for m in msgs) or reply.get("sorries"):
        return None
    for m in msgs:
        data = m.get("data", "")
        if data.startswith("AUDIT2:") and data != "AUDIT2:nothm":
            bad, defeq, one = data[len("AUDIT2:"):].split("|")
            one = one.strip()
            return {"banned": _names(bad), "defeq_aliases": _names(defeq),
                    "one_lemma": one if one.startswith(tuple(namespaces)) else None}
    return None


class AuditedRepl:
    """A REPL whose `check_proof` also requires a clean audit. Everything else is delegated, so
    the search and `claude_whole` need no changes."""

    def __init__(self, repl, auditor: Auditor, banned: tuple[str, ...]):
        self._repl, self.auditor, self.banned = repl, auditor, banned
        self.rejected = 0  # proofs that checked but used a banned constant

    def __getattr__(self, attr):
        return getattr(self._repl, attr)

    def check_proof(self, statement: str, tactics: list[str], prelude: str = "") -> bool:
        if not self._repl.check_proof(statement, tactics, prelude):
            return False
        if self.auditor.violations(statement, list(tactics), self.banned, prelude) == []:
            return True
        self.rejected += 1
        return False


def one_liners(statement: str) -> list[str]:
    """Generic tactics tried by `screen`, including intro + induction/cases on every binder."""
    tacs = ["rfl", "decide", "trivial", "omega", "simp", "simp_all", "grind", "exact?",
            "intros; simp_all", "intros; omega", "intros; grind"]
    names = [n for n in _binder_names(statement) if n.isidentifier() or "'" in n or "₁" in n]
    if names:
        intro = "intro " + " ".join(names)
        for v in names:
            tacs += [f"{intro}; induction {v} <;> simp_all", f"{intro}; induction {v} <;> grind",
                     f"{intro}; cases {v} <;> simp_all"]
    return tacs


def candidates(library: list[dict], n: int, seed: int, namespaces: tuple[str, ...] = NAMESPACES) -> list[dict]:
    """`n` lemmas from `namespaces`, in a seeded random order, as theorem rows."""
    rows = [l for l in library if l["name"].startswith(tuple(namespaces))]
    rng = random.Random(seed)
    rng.shuffle(rows)
    return [{"name": "core_" + l["name"].replace(".", "_"), "lemma": l["name"],
             "statement": l["type"]} for l in rows[:n]]


def screen(repl, auditor: Auditor, row: dict, log=lambda m: None) -> str:
    """'easy' (a one-liner proves it cleanly), 'kept', or 'invalid' (the statement does not
    elaborate in the core-only environment)."""
    try:
        repl.start_theorem(row["statement"], "")
    except Exception:
        return "invalid"
    banned = (row["lemma"],)
    for tac in one_liners(row["statement"]):
        if repl.check_proof(row["statement"], [tac], ""):
            if auditor.violations(row["statement"], [tac], banned) == []:
                log(f"  easy: {tac}")
                return "easy"
    return "kept"


def split_of(name: str) -> str:
    """Deterministic split by name hash: 40% train, 20% dev, 40% test."""
    h = int(hashlib.sha256(name.encode()).hexdigest(), 16) % 10
    return "train" if h < 4 else "dev" if h < 6 else "test"


def ext_split_of(name: str) -> str:
    """Second family: deterministic 20% dev / 80% test by name hash (no training split)."""
    return "dev" if int(hashlib.sha256(name.encode()).hexdigest(), 16) % 10 < 2 else "test"


def load_core(split: str) -> list[Theorem]:
    from jev_demo.theorems import load_theorems
    return load_theorems(SPLIT_PATHS[split])


def build(n: int, seed: int, out_path: str = POOL_PATH, family: str = "core") -> None:
    from jev_demo.repl_client import ReplClient

    ext = family == "ext"
    if ext:
        out_path = EXT_POOL_PATH
    lib_path = EXT_LIBRARY_PATH if ext else os.path.join(DATA_DIR, "library.json")
    with open(lib_path, encoding="utf-8") as f:
        library = json.load(f)
    done: dict[str, dict] = {}
    if os.path.exists(out_path):  # resume
        with open(out_path, encoding="utf-8") as f:
            done = {r["name"]: r for r in json.load(f)["rows"]}
    rows = candidates(library, n, seed, EXT_NAMESPACES if ext else NAMESPACES)
    with ReplClient(timeout_s=20) as repl, ReplClient(timeout_s=60) as arepl:
        auditor = Auditor(arepl)
        for i, row in enumerate(rows):
            if row["name"] in done:
                continue
            t0 = time.perf_counter()
            row["screen"] = screen(repl, auditor, row)
            done[row["name"]] = row
            print(f"[{i + 1}/{len(rows)}] {row['screen']:7s} {time.perf_counter() - t0:5.1f}s "
                  f"{row['lemma']}", file=sys.stderr, flush=True)
            if (i + 1) % 20 == 0:
                _write_pool(out_path, n, seed, done)
    _write_pool(out_path, n, seed, done)
    kept = [r for r in done.values() if r["screen"] == "kept"]
    for split, path in (EXT_SPLIT_PATHS if ext else SPLIT_PATHS).items():
        part = sorted((r for r in kept if (ext_split_of if ext else split_of)(r["name"]) == split),
                      key=lambda r: r["name"])
        with open(path, "w", encoding="utf-8") as f:
            f.write("[\n" + ",\n".join("  " + json.dumps({k: r[k] for k in ("name", "lemma", "statement")},
                                                        ensure_ascii=False) for r in part) + "\n]\n")
        print(f"{split}: {len(part)}", file=sys.stderr)


def _write_pool(path: str, n: int, seed: int, done: dict) -> None:
    rows = sorted(done.values(), key=lambda r: r["name"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"n": n, "seed": seed, "one_liners": one_liners("∀ (n : Nat), n = n"),
                   "rows": rows}, f, ensure_ascii=False, indent=0)
        f.write("\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) not in (3, 4) or args[0] != "build" or (len(args) == 4 and args[3] not in ("core", "ext")):
        sys.exit("usage: python -m jev_demo.corebench build N SEED [core|ext]")
    build(int(args[1]), int(args[2]), family=args[3] if len(args) == 4 else "core")
