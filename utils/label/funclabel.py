from .label import Label, LabelKind


class FuncLabel(Label):
    def __init__(self, func: str, paramCount: int = 0) -> None:
        super().__init__(LabelKind.FUNC, func)
        self.func = func
        self.paramCount = paramCount

    def __str__(self) -> str:
        return "FUNCTION<%s>" % self.func


MAIN_LABEL = FuncLabel("main")
