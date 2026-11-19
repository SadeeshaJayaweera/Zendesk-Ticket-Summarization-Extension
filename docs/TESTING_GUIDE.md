# Testing & Verification Guide

## 1. Testing Philosophy

The **Zendesk Support Intelligence Platform** enforces strict testing standards:
* **Zero Fabrication**: Tests never mock external dependencies without verifying realistic schemas.
* **Deterministic Execution**: All tests run without requiring live network access or production API keys.
* **Coverage Standards**: High test coverage across business logic, security filters, and data repositories.

---

## 2. Test Execution Commands

```bash
# Run the entire test suite (123+ tests)
./.venv/bin/pytest backend/ shared/ mcp-server/

# Run tests with detailed test execution report
./.venv/bin/pytest -v backend/ shared/ mcp-server/

# Run tests with code coverage analysis
./.venv/bin/pytest --cov=shared --cov=backend --cov=mcp_server --cov-report=term-missing backend/ shared/ mcp-server/
```

---

## 3. Targeted Test Subsets

### Backend REST API & Webhooks
```bash
./.venv/bin/pytest backend/tests/test_api.py backend/tests/test_intelligence_endpoints.py backend/tests/test_webhooks.py
```

### Multi-Provider AI Orchestrator & Context Engine
```bash
./.venv/bin/pytest shared/tests/test_ai_orchestrator.py shared/tests/test_context_engine.py
```

### Database Persistence & Multi-Tenant Isolation
```bash
./.venv/bin/pytest shared/tests/test_db_repository.py
```

### Model Context Protocol (MCP) Server Tools
```bash
./.venv/bin/pytest mcp-server/tests/
```

### Security & Hardening Tests
```bash
./.venv/bin/pytest backend/tests/test_hardening.py
```

---

## 4. Current Test Suite Baseline

* **Total Tests**: 123 passing (100% pass rate).
* **Execution Duration**: ~3.75 seconds.
* **Code Coverage**: ~81% overall coverage across 4,127 lines of code.
