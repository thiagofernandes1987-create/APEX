"""
AutofixEngine — BaseTransform ABC
==================================
Every concrete transform inherits this class and implements `apply()`.

A transform receives the parsed AST tree + original source, and returns
(new_tree, list_of_TransformResult).  It MUST NOT raise on any valid Python
AST — unexpected node shapes are silently skipped.
"""
from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class TransformResult:
    """
    Record of a single transform application.

    Attributes
    ----------
    transform   : short name, e.g. "DeadCodeRemover"
    description : human-readable summary of what was changed
    location    : function/class/module where the change occurred
    lines_removed : how many source lines were eliminated (0 for rewrites)
    """
    transform:     str
    description:   str
    location:      str  = "module"
    lines_removed: int  = 0


class BaseTransform(ABC):
    """
    Abstract base for AST-level code transforms.

    Subclasses override ``apply`` to visit/mutate the tree and return
    a (possibly new) tree plus a list of ``TransformResult`` objects
    describing every change made.  Return an empty list when no changes
    were made — this lets the engine decide whether to re-unparse.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        """
        Apply the transform to *tree*.

        Parameters
        ----------
        tree   : parsed AST (may be mutated in-place or replaced)
        source : original source string (for context; do not re-parse)

        Returns
        -------
        (tree, results)
            tree    — possibly mutated / replaced AST
            results — list of TransformResult (empty if nothing changed)
        """
