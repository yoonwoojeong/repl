"""JSON client for the Lean 4 REPL (`lake exe repl`) in command and tactic mode."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from dataclasses import dataclass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_STARTUP_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class TacticResult:
    proof_state: int | None
    goals: list[str]
    ok: bool
    completed: bool
    error: str | None
    infos: list[str]


def _failure(error: str) -> TacticResult:
    return TacticResult(None, [], False, False, error, [])


class ReplClient:
    def __init__(
        self,
        repl_path: str = ".lake/build/bin/repl",
        cwd: str = REPO_ROOT,
        timeout_s: float = 10.0,
    ):
        self.repl_path = repl_path
        self.cwd = cwd
        self.timeout_s = timeout_s
        # Proof-state ids restart at 0 in a fresh process. Ids handed out are shifted by
        # `_offset`, so ids from a killed process stay below it and are rejected.
        self._offset = 0
        self._issued = 0  # raw proof-state ids seen from the current process
        self._proc: subprocess.Popen | None = None
        self._lines: queue.Queue = queue.Queue()
        self._spawn()

    # -- process management -------------------------------------------------

    def _spawn(self) -> None:
        env = dict(os.environ)
        elan_bin = os.path.expanduser("~/.elan/bin")
        if os.path.isdir(elan_bin):  # the REPL shells out to `lean`
            env["PATH"] = elan_bin + os.pathsep + env.get("PATH", "")
        self._proc = subprocess.Popen(
            [self.repl_path],
            cwd=self.cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
        self._lines = queue.Queue()
        threading.Thread(
            target=self._read_loop, args=(self._proc.stdout, self._lines), daemon=True
        ).start()
        self._issued = 0
        # Import Init once and reuse that environment: a command without `env` re-imports
        # Init (~1s). This also keeps the startup cost out of any caller's timeout.
        reply = self._request({"cmd": "example : True := trivial"}, _STARTUP_TIMEOUT_S, starting=True)
        self._base_env = reply["env"]

    @staticmethod
    def _read_loop(stream, lines: queue.Queue) -> None:
        block: list[str] = []
        for line in stream:
            if line.strip():
                block.append(line)
            elif block:
                lines.put("".join(block))
                block = []
        lines.put(None)  # EOF

    def _kill(self) -> None:
        if self._proc is not None:
            self._proc.kill()
            self._proc.wait()
            self._proc = None

    def _restart(self) -> None:
        self._kill()
        self._offset += self._issued
        self._spawn()

    def close(self) -> None:
        self._kill()

    def __enter__(self) -> "ReplClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- protocol -------------------------------------------------------------

    def _request(self, payload: dict, timeout_s: float, starting: bool = False) -> dict | None:
        """Send one request; return the parsed reply, or None on timeout/crash (after restart)."""
        try:
            self._proc.stdin.write(json.dumps(payload) + "\n\n")
            self._proc.stdin.flush()
            block = self._lines.get(timeout=timeout_s)
        except (queue.Empty, BrokenPipeError, OSError):
            block = None
        if block is None:
            if starting:
                raise RuntimeError("Lean REPL failed to start")
            self._restart()
            return None
        return json.loads(block)

    def command(self, cmd: str, env: int | None = None, timeout_s: float | None = None) -> dict:
        payload = {"cmd": cmd, "env": self._base_env if env is None else env}
        reply = self._request(payload, self.timeout_s if timeout_s is None else timeout_s)
        if reply is None:
            return {"message": "timeout"}
        return reply

    # -- high-level API -------------------------------------------------------

    def start_theorem(self, statement: str, prelude: str = "") -> tuple[int, str]:
        # Elaborate the prelude as its own command: a proof state taken from the same
        # command as the definitions cannot see them in tactic mode ("Unknown constant").
        env = None
        if prelude.strip():
            pre = self.command(prelude)
            if "env" not in pre or any(m.get("severity") == "error" for m in pre.get("messages", [])):
                raise RuntimeError(f"could not elaborate prelude {prelude!r}: {pre}")
            env = pre["env"]
        reply = self.command(f"theorem t : {statement} := by sorry", env=env)
        sorries = reply.get("sorries")
        if not sorries:
            raise RuntimeError(f"could not start theorem {statement!r}: {reply}")
        sorry = sorries[-1]
        raw = sorry["proofState"]
        self._issued = max(self._issued, raw + 1)
        return raw + self._offset, sorry["goal"]

    def tactic(self, tac: str, proof_state: int, timeout_s: float | None = None) -> TacticResult:
        raw = proof_state - self._offset
        if raw < 0:
            return _failure("invalid proof state (REPL was restarted)")
        # The REPL parses a single tactic; parentheses admit `a; b` and multi-line sequences.
        payload = {"tactic": f"({tac})", "proofState": raw}
        reply = self._request(payload, self.timeout_s if timeout_s is None else timeout_s)
        if reply is None:
            return _failure("timeout")
        if "message" in reply:  # protocol-level error, e.g. unknown proof state or parse error
            return _failure(reply["message"])
        messages = reply.get("messages", [])
        errors = [m["data"] for m in messages if m.get("severity") == "error"]
        infos = [m["data"] for m in messages if m.get("severity") == "info"]
        ok = not errors
        new_raw = reply.get("proofState")
        if new_raw is not None:
            self._issued = max(self._issued, new_raw + 1)
        return TacticResult(
            proof_state=new_raw + self._offset if ok and new_raw is not None else None,
            goals=reply.get("goals", []),
            ok=ok,
            completed=ok and reply.get("proofStatus") == "Completed",
            error="\n".join(errors) if errors else None,
            infos=infos,
        )

    def check_proof(self, statement: str, tactics: list[str], prelude: str = "") -> bool:
        body = "".join(f"\n  {t}" for t in tactics)
        reply = self.command(f"{prelude}\ntheorem t : {statement} := by{body}")
        if "message" in reply:
            return False
        has_error = any(m.get("severity") == "error" for m in reply.get("messages", []))
        return not has_error and not reply.get("sorries")
