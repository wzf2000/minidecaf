from __future__ import annotations
from frontend.ast.tree import Function

from utils.label.blocklabel import BlockLabel
from utils.label.funclabel import FuncLabel
from utils.label.label import Label, LabelKind


class Context:
    def __init__(self) -> None:
        self.labels = {}
        self.funcs = []
        self.nextTempLabelId = 1

    def putFuncLabel(self, func: Function) -> None:
        self.labels[func.ident.value] = FuncLabel(func.ident.value, len(func.params))

    def getFuncLabel(self, name: str) -> FuncLabel:
        return self.labels[name]

    def freshLabel(self) -> BlockLabel:
        name = str(self.nextTempLabelId)
        self.nextTempLabelId += 1
        return BlockLabel(name)
