---
skill_id: integrations.science.physics_mcp_catalog
name: "Physics & Science MCP Catalog -- Quantum, Materials, arXiv, Wolfram, NASA"
description: "Scientific computing MCP servers: IBM Qiskit (official quantum hardware), PsiAnimator (QuTiP quantum simulation), arXiv search, Wolfram Language, Materials Project (DFT), OpenFOAM (CFD), OpenMM (molecular dynamics), mcp.science suite."
version: v00.33.0
status: ADOPTED
domain_path: integrations/science-physics-mcp
anchors:
  - quantum_computing
  - quantum_physics
  - statistical_physics
  - materials_science
  - molecular_dynamics
  - arxiv
  - wolfram
  - simulation
  - dft
  - cfd
  - scientific_computing
  - qiskit
source_repo: community-research
risk: safe
languages: [python, julia, wolfram]
llm_compat: {claude: full, gpt4o: full, gemini: full, llama: partial}
apex_version: v00.33.0
---

# Physics & Science MCP Catalog

## Quantum Computing & Simulation

| Server | Repo | Capabilities | Auth |
|--------|------|-------------|------|
| Qiskit MCP (IBM official) | github.com/Qiskit/mcp-servers | Real IBM Quantum hardware (156-qubit Heron R2), qiskit-ibm-runtime, transpiler | IBM Quantum API key |
| IBM Quantum (community) | github.com/aaronsb/ibm-quantum-mcp | Local simulator + real IBM Quantum, VQE molecular energy | IBM Quantum API key |
| PsiAnimator (QuTiP + Manim) | github.com/manasp21/PsiAnimator-MCP | Quantum states, Lindblad master eq, Monte Carlo, Wigner functions, Bloch sphere, entanglement, gate sequences | Local |
| SpinQ (official hardware) | github.com/SpinQTech/spinqit_mcp_tools | Real SpinQ quantum hardware, QASM, SpinQ Cloud | SpinQ account |
| Qiskit Simulator (Docker) | github.com/YuChenSSR/quantum-simulator-mcp | Noise models, OpenQASM 2.0, Docker-based | Local Docker |

## Literature & Knowledge Databases

| Server | Repo/URL | Coverage |
|--------|---------|---------|
| arXiv (blazickjp) | github.com/blazickjp/arxiv-mcp-server | Search + retrieve full paper content |
| Multi-paper search | github.com/openags/paper-search-mcp | arXiv, PubMed, bioRxiv, IEEE (skeleton), Semantic Scholar, OpenAlex, Crossref, 20+ sources |
| Wolfram Language | github.com/rhennigan/MCPServer | Full Wolfram Language computation, CAS, mathematical reasoning |
| Wolfram Alpha | github.com/StoneDot/wolframalpha-mcp-server | Math, science, factual queries via WolframAlpha LLM API |

## Materials Science & Computational Chemistry

| Server | Repo | Capabilities |
|--------|------|-------------|
| mcp.science suite (pathintegral) | github.com/pathintegral-institute/mcp.science | Materials Project (search/visualize), GPAW (DFT), Mathematica, Jupyter-Act, NEMAD (neuroscience) |
| OpenMM + Abacus DFT | github.com/PhelanShao/openmm-mcp-server | Molecular dynamics simulations, DFT calculations, task management |
| GROMACS copilot | github.com/ChatMol/molecule-mcp | GROMACS MD workflows, molecular modeling |

## Engineering & Earth Sciences

| Server | Repo | Capabilities |
|--------|------|-------------|
| NASA (20+ APIs) | github.com/ProgramComputer/NASA-MCP-server | APOD, Mars Rovers, NEO, space weather, exoplanets, JPL Solar System, FIRMS |
| NASA Earthdata (official) | github.com/nasa/earthdata-mcp | Earth science data semantic search |
| OpenFOAM CFD | github.com/webworn/openfoam-mcp-server | Computational fluid dynamics, AI-guided error resolution |
| OpenSCAD CAD | github.com/fboldo/openscad-mcp-server | 3D parametric modeling, STL/PNG rendering |

## Activation in APEX

- `quantum_computing` → Qiskit/PsiAnimator/SpinQ
- `simulation` → OpenFOAM/OpenMM/PsiAnimator
- `materials_science` + `dft` → mcp.science + OpenMM
- `arxiv` + `statistical_physics` → arXiv + multi-paper search
- `wolfram` → Wolfram Language full computation
- SCIENTIFIC mode auto-activates `scientist_agent` which can leverage these

## Diff History
- **v00.33.0**: Cataloged from community research — all verified functional as of 2026-04