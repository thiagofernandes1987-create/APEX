---
skill_id: algorithms.long_horizon_agent
name: "Long-Horizon Coding Agent Demo (RIV 2025)"
description: "Reference documentation for Long-Horizon Coding Agent Demo (RIV 2025). Source: riv2025-long-horizon-coding-agent-demo-main"
version: v00.33.0
status: CANDIDATE
domain_path: algorithms/long-horizon-agent
anchors:
  - riv2025
  - long-horizon_coding_agent_demo_(riv_2025)
source_repo: riv2025-long-horizon-coding-agent-demo-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Long-Horizon Coding Agent Demo (RIV 2025)

Source: `riv2025-long-horizon-coding-agent-demo-main` (139 files)

## README

# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default tseslint.config([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      ...tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      ...tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      ...tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugi

## Diff History
- **v00.33.0**: Ingested from riv2025-long-horizon-coding-agent-demo-main