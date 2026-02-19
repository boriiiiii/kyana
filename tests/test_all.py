"""
Lance tous les tests Kyana.

Usage:
    python tests/test_all.py           # tous les tests
    python tests/test_all.py gemini    # seulement Gemini
    python tests/test_all.py webhook   # seulement Webhook
"""

import subprocess
import sys
import os

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)


def run_test(script: str, label: str) -> bool:
    print(f"\n{'━' * 50}")
    print(f"▶ {label}")
    print(f"{'━' * 50}\n")
    result = subprocess.run(
        [sys.executable, os.path.join(TESTS_DIR, script)],
        cwd=PROJECT_DIR,
    )
    return result.returncode == 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    tests = {
        "ollama": ("test_ollama.py", "🔬 DIAGNOSTIC OLLAMA"),
        "webhook": ("test_webhook.py", "🧪 TESTS WEBHOOK"),
    }

    if target == "all":
        to_run = list(tests.items())
    elif target in tests:
        to_run = [(target, tests[target])]
    else:
        print(f"❌ Test inconnu : {target}")
        print(f"   Disponibles : {', '.join(tests.keys())}, all")
        sys.exit(1)

    print("🚀 KYANA — SUITE DE TESTS")

    results = {}
    for name, (script, label) in to_run:
        results[name] = run_test(script, label)

    print(f"\n{'━' * 50}")
    print("📊 RÉSUMÉ")
    print(f"{'━' * 50}")
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} — {name}")
