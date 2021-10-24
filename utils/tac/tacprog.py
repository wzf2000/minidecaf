from typing import Any, Optional, Union

from utils.tac.tacinstr import TACInstr

from .tacfunc import TACFunc


# A TAC program consists of several TAC functions.
class TACProg:
    def __init__(self, funcs: list[TACFunc], globalVars: list[TACInstr]) -> None:
        self.funcs = funcs
        self.globalVars = globalVars

    def printTo(self) -> None:
        for var in self.globalVars:
            print("\t" + str(var))
        for func in self.funcs:
            func.printTo()
