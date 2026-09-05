"""Code execution against test cases via a self-hosted Piston instance.

Piston sandboxes untrusted candidate code (time/memory limits, no network) and
works on cgroup v2 hosts. Each test is one execute call (stdin -> stdout), and
we compare stdout to expected output.
"""

import httpx

from .config import settings

# Map our language ids to Piston language + a preferred version + filename.
LANGUAGES = {
    "python": {
        "lang": "python",
        "version": "3.10.0",
        "file": "main.py",
        "label": "Python 3.10",
        "monaco": "python",
    },
    "java": {
        "lang": "java",
        "version": "15.0.2",
        "file": "Main.java",
        "label": "Java 15",
        "monaco": "java",
    },
    "cpp": {
        "lang": "c++",
        "version": "10.2.0",
        "file": "main.cpp",
        "label": "C++ (GCC 10)",
        "monaco": "cpp",
    },
}


def list_languages() -> list[dict]:
    return [{"id": k, "label": v["label"], "monaco": v["monaco"]} for k, v in LANGUAGES.items()]


def available() -> bool:
    try:
        r = httpx.get(f"{settings.piston_api_base}/runtimes", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def installed_runtimes() -> list[dict]:
    try:
        r = httpx.get(f"{settings.piston_api_base}/runtimes", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def _resolve_version(lang_cfg: dict) -> str:
    """Use an installed version for this language if present, else the preferred."""
    for rt in installed_runtimes():
        names = [rt.get("language"), *rt.get("aliases", [])]
        if lang_cfg["lang"] in names:
            return rt.get("version", lang_cfg["version"])
    return lang_cfg["version"]


def _norm(s: str) -> str:
    return "\n".join(line.rstrip() for line in (s or "").replace("\r\n", "\n").split("\n")).strip()


def _execute_one(lang_cfg: dict, version: str, source: str, stdin: str) -> dict:
    payload = {
        "language": lang_cfg["lang"],
        "version": version,
        "files": [{"name": lang_cfg["file"], "content": source}],
        "stdin": stdin,
    }
    r = httpx.post(f"{settings.piston_api_base}/execute", json=payload, timeout=40)
    r.raise_for_status()
    return r.json()


def run_tests(language: str, source: str, tests: list[dict]) -> dict:
    """Run `source` against each test ({input, expected}). Returns per-test
    results plus a summary."""
    lang_cfg = LANGUAGES.get(language)
    if not lang_cfg:
        return {
            "error": f"Unsupported language: {language}",
            "results": [],
            "passed": 0,
            "total": 0,
        }
    if not tests:
        return {"results": [], "passed": 0, "total": 0}

    version = _resolve_version(lang_cfg)
    results = []
    passed = 0
    for t in tests:
        try:
            out = _execute_one(lang_cfg, version, source, t.get("input", ""))
        except Exception as e:
            results.append(
                {
                    "input": t.get("input", ""),
                    "expected": t.get("expected", ""),
                    "stdout": "",
                    "stderr": f"execution error: {e}",
                    "status": "Error",
                    "passed": False,
                    "hidden": t.get("hidden", False),
                }
            )
            continue

        compile_stage = out.get("compile") or {}
        run_stage = out.get("run") or {}
        compile_err = (compile_stage.get("stderr") or "").strip()
        stdout = run_stage.get("stdout") or ""
        stderr = (run_stage.get("stderr") or "").strip()
        code = run_stage.get("code")

        if compile_err and run_stage.get("stdout") in (None, ""):
            status = "Compilation Error"
            ok = False
        elif code not in (0, None):
            status = "Runtime Error"
            ok = False
        else:
            ok = _norm(stdout) == _norm(t.get("expected", ""))
            status = "Accepted" if ok else "Wrong Answer"

        if ok:
            passed += 1
        results.append(
            {
                "input": t.get("input", ""),
                "expected": t.get("expected", ""),
                "stdout": stdout,
                "stderr": stderr or compile_err,
                "status": status,
                "passed": ok,
                "time": None,
                "hidden": t.get("hidden", False),
            }
        )

    return {"results": results, "passed": passed, "total": len(tests)}
