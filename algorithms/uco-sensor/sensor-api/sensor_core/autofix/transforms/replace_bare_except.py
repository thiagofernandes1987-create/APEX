"""
AutofixEngine — BareExceptReplacer  (M8.1, transform #6)
==========================================================
Replaces bare ``except:`` handlers with ``except Exception as e:``.

Before:
    try:
        risky()
    except:
        pass

After:
    try:
        risky()
    except Exception as e:
        pass

Safety constraints:
  - Only targets ExceptHandler nodes where ``type`` is None (bare except).
  - Assigns the canonical name ``e`` when no ``as`` name is present.
  - If the handler already has a name (impossible with bare except, but
    guarded anyway) it is left unchanged.
  - Never removes or restructures the handler body.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


class BareExceptReplacer(BaseTransform):
    """
    Converts bare ``except:`` to ``except Exception as e:``.

    Bare except clauses catch *everything* including ``SystemExit``,
    ``KeyboardInterrupt``, and ``GeneratorExit``, making controlled
    shutdown impossible. Replacing with ``Exception`` preserves the
    intent while allowing process signals to propagate normally.
    """

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is not None:
                # Already has an exception type — leave it alone.
                continue

            # Patch: bare → except Exception as e
            node.type = ast.Name(id="Exception", ctx=ast.Load())
            if node.name is None:
                node.name = "e"

            line = getattr(node, "lineno", 0)
            results.append(TransformResult(
                transform=self.name,
                description=(
                    f"Replaced bare 'except:' with 'except Exception as e:'"
                    + (f" at line {line}" if line else "")
                ),
                location=f"line {line}" if line else "module",
            ))

        ast.fix_missing_locations(tree)
        return tree, results
