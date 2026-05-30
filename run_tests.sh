#!/usr/bin/env bash
# ==============================================================================
# IMPERIO Full Test Suite
# ==============================================================================
# Runs all 871+ tests across IMPERIO_ROOT and IMPERIO_UNIFICADO.
# Exit code: 0 if all pass, non-zero if any fail.
# ==============================================================================
set -euo pipefail

# Ensure we run from the repo root (IMPERIO_ROOT/) regardless of invocation dir
cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0

echo -e "${YELLOW}=== IMPERIO Full Test Suite ===${NC}"
echo ""

# ── IMPERIO_ROOT tests ──────────────────────────────────────────────────────
echo -e "${YELLOW}--- IMPERIO_ROOT/tests/ ---${NC}"
if python3 -m pytest tests/ -v --tb=short; then
    echo -e "${GREEN}  ✓ IMPERIO_ROOT tests passed${NC}"
else
    echo -e "${RED}  ✗ IMPERIO_ROOT tests failed${NC}"
    FAILED=1
fi

# ── IMPERIO_UNIFICADO tests ─────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}--- IMPERIO_UNIFICADO ---${NC}"
IMPERIO_UNIFICADO_TESTS=(
    "../IMPERIO_UNIFICADO/IMPERIO_NUCLEO/amazon_content_system/test_workflow.py"
    "../IMPERIO_UNIFICADO/IMPERIO_NUCLEO/efficiency_layer/test_efficiency.py"
)
for test_file in "${IMPERIO_UNIFICADO_TESTS[@]}"; do
    if [ -f "$test_file" ]; then
        pytest_output=$(python3 -m pytest "$test_file" -v --tb=short 2>&1)
        pytest_exit=$?
        if [ "$pytest_exit" -eq 0 ]; then
            echo -e "${GREEN}  ✓ $test_file passed${NC}"
        elif [ "$pytest_exit" -eq 5 ]; then
            echo -e "${YELLOW}  - $test_file: no tests collected (skip)${NC}"
        else
            echo -e "${RED}  ✗ $test_file failed${NC}"
            echo "$pytest_output" | tail -40
            FAILED=1
        fi
    else
        echo -e "${YELLOW}  - $test_file not found, skipping${NC}"
    fi
done

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}=== All test suites passed ===${NC}"
    exit 0
else
    echo -e "${RED}=== One or more test suites FAILED ===${NC}"
    exit 1
fi
