---
skill_id: algorithms.attribution_graphs.frontend
name: "Attribution Graphs Frontend -- Interpretability Visualization"
description: "Frontend for visualizing Claude model attribution graphs. Used in mechanistic interpretability research to understand model behavior."
version: v00.33.0
status: CANDIDATE
domain_path: algorithms/attribution-graphs
anchors:
  - attribution_graphs
  - interpretability
  - mechanistic
  - visualization
  - model_behavior
source_repo: attribution-graphs-frontend
risk: safe
languages: [typescript]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Attribution Graphs Frontend

# attribution-graphs-frontend

Snapshot of the frontend code in [On the Biology of a Large Language Model](https://transformer-circuits.pub/2025/attribution-graphs/biology.html) and [Circuit Tracing: Revealing Computational Graphs in Language Models](https://transformer-circuits.pub/2025/attribution-graphs/methods.html).

To run:

```
git clone git@github.com:anthropics/attribution-graphs-frontend.git
cd attribution-graphs-frontend
npx hot-server
```


## Diff History
- **v00.33.0**: Ingested from attribution-graphs-frontend-main