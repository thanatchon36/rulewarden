| Property | Tests passed |
|---|---|
| Determinism across processes, TZ, locale, hash seed | 4/4 |
| ReDoS-shaped patterns rejected or killed | 3/3 |
| Oversized inputs fail closed | 3/3 |
| Corrupted rules and lock tampering fail closed | 5/5 |
| Injected engine timeouts and crashes fail closed (blocking rules) | 4/4 |
| Protected-path edits blocked (diff, drift, shell) | 5/5 |
| Agent-authored deviations of blocking rules rejected | 3/3 |
| Audit log tamper-evident | 1/1 |
