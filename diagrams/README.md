# Diagrams

Diagrams live **inline, next to the text they explain**, as Mermaid — one source that
renders in GitHub, and stays diffable in review rather than becoming a binary that drifts
out of date with the system it describes.

| Diagram | Where |
|---|---|
| Platform service topology | [`platform/architecture.md`](../platform/architecture.md) |
| Agent execution sequence | [`platform/architecture.md`](../platform/architecture.md) |
| One run end to end, with failure branches | [`platform/runtime-sequence.md`](../platform/runtime-sequence.md) |
| Seven-phase development lifecycle | [`platform/ai-development-lifecycle.md`](../platform/ai-development-lifecycle.md) |
| Support agent decision gate | [`case-studies/01-it-support-deflection.md`](../case-studies/01-it-support-deflection.md) |
| Invoice extraction and grounding | [`case-studies/02-invoice-to-erp-grounding.md`](../case-studies/02-invoice-to-erp-grounding.md) |
| One brand brain → many surfaces | [`case-studies/03-compliance-gated-content.md`](../case-studies/03-compliance-gated-content.md) |

The system context diagram below is the only one that does not belong to a single document.

```mermaid
flowchart TB
    subgraph USERS["People"]
        BUILDER["Agent builders<br/>configure, don't code"]
        END["End users<br/>Slack · Freshdesk · web · API"]
        AUDIT["Auditors<br/>why did it answer that?"]
    end

    subgraph PLATFORM["Agent platform"]
        STUDIO["Studio UI"]
        RUNTIME["Agent runtime<br/>+ workflow engine"]
        GOV["Governance<br/>isolation · guardrails · audit"]
        EVAL["Evaluation<br/>gates · regressions"]
    end

    subgraph EXTERNAL["External"]
        LLM["Model providers"]
        TOOLS["Business systems<br/>ticketing · commerce · ERP"]
        OBS["Tracing backend"]
    end

    BUILDER --> STUDIO --> RUNTIME
    END --> RUNTIME
    RUNTIME --> GOV
    GOV --> LLM
    GOV --> TOOLS
    EVAL -.->|black box over HTTP| RUNTIME
    RUNTIME -.->|OTel spans| OBS
    GOV -.->|append-only record| AUDIT
```
