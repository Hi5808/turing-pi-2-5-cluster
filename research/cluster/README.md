# Cluster-level research

Claims that are about the machine as a whole, or that span hardware classes, so they are not
honestly filed under one board.

| Paper | Claim | Status |
|---|---|---|
| [000](000-cluster-rebuild-and-baseline.md) | What the cluster is, how it is measured, and the baselines everything else is compared against | complete |
| [001](001-heterogeneous-llm-pipeline.md) | A 32B model runs split across the two Orins when it OOMs on either alone | complete |
| [002](002-pipeline-parallel-measurements.md) | The cost of splitting: 4% dense, 18.5% MoE; logit return dominates wire cost | complete |
| [008](008-serving-capacity-knee.md) | Serviceable capacity is 4 concurrent streams, not the 16 slots or the 61 tok/s peak | complete |

**Candidate channels:** homelab / self-hosted / local-LLM communities. Confirm the exact subreddit
names and their self-promotion rules before posting.
