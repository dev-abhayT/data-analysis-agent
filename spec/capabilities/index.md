# Capabilities Index

## Capabilities in This Project

| Capability | File | Phase |
|-----------|------|-------|
| File Upload and Profile | [file_upload_and_profile.md](file_upload_and_profile.md) | Phase 1 |
| Data Query and Answer | [data_query_and_answer.md](data_query_and_answer.md) | Phase 1 |
| Streaming Answers | [streaming_answers.md](streaming_answers.md) | Phase 1 |
| Session Persistence | [session_persistence.md](session_persistence.md) | Phase 2 |
| Multi-File Join | [multi_file_join.md](multi_file_join.md) | Phase 2 |
| Export and Audit | [export_and_audit.md](export_and_audit.md) | Phase 2 |

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning
