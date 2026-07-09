---
status: accepted
---

# Project Config geometry is explicit; the core never auto-lays-out

The original demo config listed rooms by size only, implying the core would
arrange them into a floor plan. We decided the Project Config always states
explicit geometry — footprint, wall segments, opening positions — and the
Deterministic Core draws only what is stated. Auto-layout is an open-ended
solver problem, produces results professional Drafters fight against, and
breaks the same-input-same-output guarantee. Convenience (computing positions
from a conversation) belongs to the Agent Layer, which writes explicit
geometry into the config.
