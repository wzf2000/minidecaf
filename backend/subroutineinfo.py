from utils.label.funclabel import FuncLabel

"""
SubroutineInfo: collect some info when selecting instr which will be used in SubroutineEmitter
"""


class SubroutineInfo:
    def __init__(self, funcLabel: FuncLabel, local_size: int) -> None:
        self.funcLabel = funcLabel
        self.local_size = local_size

    def __str__(self) -> str:
        return "funcLabel: {}(Alloc {} Byte)".format(
            self.funcLabel.name,
            self.local_size,
        )
