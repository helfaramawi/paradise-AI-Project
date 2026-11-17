# HAQQ — Security, Privacy & Governance

| Control | Implementation | Verified by |
|---|---|---|
| Tenant isolation | `org_id` on every tenant row; `get_owned()` / `get_project()` / `accessible_project_ids()`; foreign ids → 404 | `tests/test_security.py` (15 read endpoints, 6 write paths, aggregates) |
| Project-level access | PM / site engineer roles see only assigned projects | `test_rbac_role_restrictions`, Playwright |
| RBAC | 8 roles × 26 permissions (`core/rbac.py`); stage-specific gates on claims (legal review → management approval → submission) | `test_s5_*`, `test_rbac_*` |
| Authentication | PBKDF2-SHA256 (310 000 iterations, per-user salt); password policy; JWT (HS256) bound to a server-side session (`sid`) → logout and password change revoke sessions | `test_auth_lockout_and_session_revocation` |
| Brute force | 5 failures → 15-minute lock; per-IP login rate limit; global API rate limit | `test_auth_*`, `test_rate_limit_login` |
| MFA | RFC 6238 TOTP enrolment and enforcement at login | `test_mfa_totp` |
| Separation of duties | valuation preparer cannot verify; substantiation needs verified valuation | `test_separation_of_duties_on_valuation` |
| Audit | hash-chained `audit_logs` (each entry hashes its content + previous hash) with `/audit/verify`; document access log | `test_audit_chain_and_security_headers` |
| Input validation | Pydantic schemas on every input; upload size limit, extension allow-list **and** magic-byte check, UTF-8 check for text, duplicate detection, safe filenames | `test_upload_validation_*`, `test_file_sniffing_*` |
| Untrusted documents / prompt injection | upload scan + UI flag; wrapped excerpts; system-prompt rule; citation validation | `test_prompt_injection_guard`, `test_upload_validation_and_injection_flag`, `test_ai.py` |
| AI data policy | per-organisation opt-in for external model processing (default **off**); no external call without it | `test_org_policy_blocks_external_processing` |
| Secrets | only via environment / secrets manager; production refuses the dev secret key | `config.get_settings` |
| Transport & headers | HSTS in production, `nosniff`, `X-Frame-Options: DENY`, CSP on API responses, no-referrer; downloads `Cache-Control: no-store` | test + nginx config |
| File integrity | SHA-256 stored and re-verified on every read of documents and generated claim files | storage layer |
| Backups | `ops/backup.sh` (pg_dump + storage tarball + SHA256SUMS), `ops/restore.sh` verifies checksums first | manual procedure |

## Egypt — Personal Data Protection Law No. 151 of 2020
Design choices supporting compliance (not a compliance claim — **qualified Egyptian legal review is required before
any compliance statement**): data minimisation (project/contract data, limited personal data of users and document
signatories); tenant-configurable retention period; no cross-border transfer of document text unless the tenant opts
in to an external AI provider; audit trails of access; role-based least privilege; ability to delete an organisation
and all its data. Outstanding items: automated retention purge, data-subject request workflow, DPA templates,
hosting-region decision and registration/licensing obligations with the Personal Data Protection Center.

## Residual risks
In-process rate limiter (not shared across replicas); local object store (no at-rest encryption beyond the disk);
JWT in `sessionStorage` (XSS-sensitive — mitigated by React escaping and CSP at the edge; consider httpOnly cookies);
no WAF/antivirus scanning of uploads yet. See `docs/KNOWN_LIMITATIONS.md`.
