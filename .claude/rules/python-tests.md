---
paths:
  - "tests/**/*.py"
---

# Python Test Rules

## Framework
- Use **pytest** exclusively — no unittest.TestCase subclassing
- Run tests with: `python -m pytest tests/ -v`

## Naming Conventions
- Test files: `test_<module>.py`
- Test classes: `Test<Feature>` (e.g., `TestInvoiceValidation`)
- Test functions: `test_<behavior_under_test>` (e.g., `test_line_items_not_summing_to_subtotal`)
- Use descriptive names that explain WHAT is being tested and the EXPECTED outcome

## API Mocking
- **Never make real API calls** in unit tests
- Mock `client.messages.create()` when testing extraction functions
- Use `unittest.mock.patch` or `pytest.monkeypatch` to mock the anthropic client
- Validation and schema tests don't need mocks — test them directly

## Assertions
- Assert specific error messages, not just truthiness
- For validation tests: check that specific error strings appear in the errors list
- For schema tests: verify specific property names, types, and required fields
- Use `assert ... is True` / `assert ... is False` for boolean validation results

## Test Data
- Use helper factories (e.g., `_valid_invoice_data(**overrides)`) for building test data
- Override only the fields relevant to each test case
- Keep test data realistic — use values from sample_data/ as reference

## Structure
- Group related tests in classes (e.g., `TestInvoiceSchemaGeneration`, `TestInvoiceValidationMathError`)
- One assertion concept per test — a test should fail for exactly one reason
