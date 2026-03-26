# Sovran AI — Obsidian Memory Migration & First-Principles Debug

## Phase 1: Obsidian Memory Setup
- [ ] Copy all 14 brain artifacts into Obsidian vault (structured for retrieval)
- [ ] Update `GEMINI.md` with Obsidian-as-memory protocol
- [ ] Write bug report protocol rule into memory

## Phase 2: First-Principles Analysis
- [ ] Read `sovran_ai.py` fully — understand the ENTIRE codebase
- [ ] Write diagnostic `test_quote_shape.py` to prove `event.data` structure
- [ ] Run diagnostic and capture raw output
- [ ] Write Obsidian bug report with findings
- [ ] Test each subsystem in isolation:
  - [ ] WebSocket connection
  - [ ] Quote data parsing
  - [ ] Trade data parsing
  - [ ] Session phase gate
  - [ ] Monitor loop logic
  - [ ] LLM API call
- [ ] Only proceed to implementation after all tests pass
