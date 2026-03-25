---
paths:
  - "extraction/extractor.py"
  - "extraction/validator.py"
  - "extraction/batch_processor.py"
---

# API Call Rules

## Client Setup
- Use `anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))` — never hardcode keys
- Load env with `python-dotenv` before creating the client
- Define `MODEL` as a module-level constant

## Request Parameters
- Always set `max_tokens` explicitly (use 4096 for extraction tasks)
- Always set `model` using the module-level `MODEL` constant
- Build tool definitions from Pydantic models via `get_tool_definition()`

## tool_choice Patterns
- **Forced single tool**: `tool_choice={"type": "tool", "name": "tool_name"}` — use when
  you know exactly which extraction to run. Response always contains a tool_use block.
- **Auto-detect**: `tool_choice={"type": "auto"}` — use when Claude should pick the tool.
  Response may contain both text and tool_use blocks.
- **Structured output**: `output_config={"format": {"type": "json_schema", "schema": schema}}`
  — no tools needed, response text IS the JSON.

## Response Handling
- Always iterate `response.content` blocks — never assume block order
- Check `block.type == "tool_use"` for tool results, `block.type == "text"` for reasoning
- For forced tool_choice: extract `block.input` from the tool_use block
- For output_config: parse `json.loads(response.content[0].text)`
- For auto-detect: capture both text (reasoning) and tool_use (data) blocks

## Retry / Correction Pattern (CCA)
- Append Claude's response as `{"role": "assistant", "content": response.content}`
- Follow with `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": ..., "is_error": True, "content": error_text}]}`
- Claude sees its own output + the validation errors and self-corrects

## Batch API
- Use `client.messages.batches.create(requests=[...])` for bulk processing
- Each request needs `custom_id` (for correlation) and `params` (standard message params)
- Poll with `client.messages.batches.retrieve(batch_id)` until `processing_status` is terminal
- Retrieve results with `client.messages.batches.results(batch_id)`
