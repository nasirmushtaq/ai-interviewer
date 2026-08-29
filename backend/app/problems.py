"""Coding problems: a small seeded bank (hybrid) plus AI generation. Each problem
has a statement, per-language starter code, visible example tests, and hidden
tests. Tests use stdin -> stdout so they run uniformly across languages."""
import json

from . import openai_service as ai

# --------------------------------------------------------------------------- #
# Seeded bank (vetted). stdin/stdout based so one test format fits all langs.
# --------------------------------------------------------------------------- #
SEED_PROBLEMS = {
    "two_sum_indices": {
        "id": "two_sum_indices",
        "title": "Pair Sum",
        "difficulty": "easy",
        "statement": (
            "Given a line with N space-separated integers followed by a line with "
            "a target integer T, print the 1-based indices (i j, i<j) of the two "
            "numbers that add up to T. If none exist, print -1.\n\n"
            "Input:\nLine 1: the array, space-separated\nLine 2: target T\n\n"
            "Output: two indices separated by a space, or -1."
        ),
        "starter": {
            "python": "def solve(nums, t):\n    # return (i, j) 1-based or None\n    pass\n\nimport sys\ndata=sys.stdin.read().split('\\n')\nnums=list(map(int, data[0].split()))\nt=int(data[1])\n# TODO: print result\n",
            "java": "import java.util.*;\npublic class Main {\n  public static void main(String[] a){\n    Scanner sc=new Scanner(System.in);\n    // read array line then target; print result\n  }\n}\n",
            "cpp": "#include <bits/stdc++.h>\nusing namespace std;\nint main(){\n  // read array line then target; print result\n}\n",
        },
        "examples": [
            {"input": "2 7 11 15\n9", "expected": "1 2"},
            {"input": "3 2 4\n6", "expected": "2 3"},
        ],
        "hidden": [
            {"input": "1 2 3\n7", "expected": "-1", "hidden": True},
            {"input": "5 5\n10", "expected": "1 2", "hidden": True},
            {"input": "-3 4 3 90\n0", "expected": "1 3", "hidden": True},
        ],
    },
    "reverse_words": {
        "id": "reverse_words",
        "title": "Reverse Words",
        "difficulty": "easy",
        "statement": (
            "Read a single line of text and print the words in reverse order, "
            "single-spaced, with no leading/trailing spaces."
        ),
        "starter": {
            "python": "import sys\nline=sys.stdin.readline().rstrip('\\n')\n# TODO: print reversed words\n",
            "java": "import java.util.*;\npublic class Main{public static void main(String[] a){\n  Scanner sc=new Scanner(System.in);\n  String line=sc.hasNextLine()?sc.nextLine():\"\";\n  // TODO\n}}\n",
            "cpp": "#include <bits/stdc++.h>\nusing namespace std;\nint main(){string line; getline(cin,line); /* TODO */}\n",
        },
        "examples": [
            {"input": "the sky is blue", "expected": "blue is sky the"},
            {"input": "hello world", "expected": "world hello"},
        ],
        "hidden": [
            {"input": "a b c d e", "expected": "e d c b a", "hidden": True},
            {"input": "single", "expected": "single", "hidden": True},
        ],
    },
}


def list_seed_titles() -> list[dict]:
    return [
        {"id": p["id"], "title": p["title"], "difficulty": p["difficulty"]}
        for p in SEED_PROBLEMS.values()
    ]


def get_seed(problem_id: str) -> dict | None:
    return SEED_PROBLEMS.get(problem_id)


GEN_SYSTEM = (
    "You generate ONE self-contained coding-interview problem. It MUST use "
    "standard input (stdin) and standard output (stdout) so it can be tested "
    "language-agnostically. Return STRICT JSON with keys: "
    "'title' (string), "
    "'statement' (clear problem text including exact input and output format), "
    "'starter' (object with keys 'python','java','cpp' — minimal starter code that "
    "reads stdin and where the candidate writes the solution; Java's public class "
    "MUST be named Main), "
    "'examples' (list of 2-3 objects {input, expected} shown to the candidate), "
    "'hidden' (list of 4-6 objects {input, expected} NOT shown, covering edge "
    "cases). Ensure every expected output is exactly what a correct program would "
    "print (mind trailing newlines/spaces). Keep inputs small."
)


def generate_problem(difficulty: str, focus: str, company: str | None = None,
                     topic: str | None = None) -> dict | None:
    if not ai.has_key():
        return None
    ask = (
        f"Difficulty: {difficulty}. Focus: {focus}. "
        + (f"Company style: {company}. " if company else "")
        + (f"Topic hint: {topic}. " if topic else "")
        + "Generate the problem now as JSON."
    )
    try:
        data = ai.chat_json(
            [{"role": "system", "content": GEN_SYSTEM},
             {"role": "user", "content": ask}]
        )
    except Exception:  # noqa: BLE001
        return None
    # Basic shape validation; fall back to a seed if malformed.
    if not all(k in data for k in ("title", "statement", "starter", "examples")):
        return None
    data.setdefault("hidden", [])
    for h in data["hidden"]:
        h["hidden"] = True
    data["id"] = "generated"
    data.setdefault("difficulty", difficulty)
    # Ensure all three languages have starter code.
    starter = data.get("starter") or {}
    for lng in ("python", "java", "cpp"):
        starter.setdefault(lng, "")
    data["starter"] = starter
    return data


def pick_problem(difficulty: str, focus: str, company: str | None = None,
                 topic: str | None = None, prefer_seed_id: str | None = None) -> dict:
    """Hybrid: use a specific/seed problem when asked, else try AI generation,
    else fall back to a seed."""
    if prefer_seed_id and prefer_seed_id in SEED_PROBLEMS:
        return SEED_PROBLEMS[prefer_seed_id]
    gen = generate_problem(difficulty, focus, company, topic)
    if gen:
        return gen
    # Fallback: pick a seed roughly matching difficulty.
    for p in SEED_PROBLEMS.values():
        if p["difficulty"] == (difficulty or "easy"):
            return p
    return next(iter(SEED_PROBLEMS.values()))
