---
skill_id: algorithms.torchtyping
name: "TorchTyping -- PyTorch Type Annotations"
description: "Reference documentation for TorchTyping -- PyTorch Type Annotations. Source: torchtyping-anthropic-0.1.5"
version: v00.33.0
status: CANDIDATE
domain_path: algorithms/torchtyping
anchors:
  - torchtyping
  - torchtyping
source_repo: torchtyping-anthropic-0.1.5
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# TorchTyping -- PyTorch Type Annotations

Source: `torchtyping-anthropic-0.1.5` (34 files)

## README

# Please use jaxtyping instead

*Welcome! For new projects I now **strongly** recommend using my newer [jaxtyping](https://github.com/google/jaxtyping) project instead. It supports PyTorch, doesn't actually depend on JAX, and unlike TorchTyping it is compatible with static type checkers. The 'jax' in the name is now historical!*

<br>
<br>
<br>

The original torchtyping README is as follows.

---

<h1 align='center'>torchtyping</h1>
<h2 align='center'>Type annotations for a tensor's shape, dtype, names, ...</h2>

Turn this:
```python
def batch_outer_product(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    # x has shape (batch, x_channels)
    # y has shape (batch, y_channels)
    # return has shape (batch, x_channels, y_channels)

    return x.unsqueeze(-1) * y.unsqueeze(-2)
```
into this:
```python
def batch_outer_product(x:   TensorType["batch", "x_channels"],
                        y:   TensorType["batch", "y_channels"]
                        ) -> TensorType["batch", "x_channels", "y_channels"]:

    return x.unsqueeze(-1) * y.unsqueeze(-2)
```
**with programmatic checking that the shape (dtype, ...) specification is met.**

Bye-bye bugs! Say hello to enforced, clear documentation of your code.

If (like me) you find yourself littering your code with comments like `# x has shape (batch, hidden_state)` or statements like `assert x.shape == y.shape` , just to keep track of what shape everything is, **then this is for you.**

---

## Installation

```bash
pip install 

## Diff History
- **v00.33.0**: Ingested from torchtyping-anthropic-0.1.5