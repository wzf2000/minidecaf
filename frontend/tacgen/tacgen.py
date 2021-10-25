from frontend.parser.ply_parser import unary
from frontend.symbol.funcsymbol import FuncSymbol
from frontend.type import builtin_type
from utils.error import DecafGlobalVarBadInitValueError
import utils.riscv as riscv
from frontend.ast import node
from frontend.ast.tree import *
from frontend.ast.visitor import Visitor
from frontend.symbol.varsymbol import VarSymbol
from frontend.type.array import ArrayType
from utils.tac import tacop
from utils.tac.funcvisitor import FuncVisitor
from utils.tac.programwriter import ProgramWriter
from utils.tac.tacinstr import Global, LoadSymbol
from utils.tac.tacprog import TACProg
from utils.tac.temp import Temp

import sys
"""
The TAC generation phase: translate the abstract syntax tree into three-address code.
"""


class TACGen(Visitor[FuncVisitor, None]):
    def __init__(self) -> None:
        pass

    # Entry of this phase
    def transform(self, program: Program) -> TACProg:
        mainFunc = program.mainFunc()
        pw = ProgramWriter(program.functions())

        mv_dict: dict[str, FuncVisitor] = {}

        for child in program:
            if isinstance(child, Declaration):
                if child.array_size != []:
                    symbol: VarSymbol = child.ident.getattr("symbol")
                    pw.globalVars.append(Global(child.ident.value, False, 0, symbol.type.size))
                elif child.init_expr == NULL:
                    pw.globalVars.append(Global(child.ident.value))
                else:
                    if not isinstance(child.init_expr, IntLiteral):
                        raise DecafGlobalVarBadInitValueError(child.ident.value)
                    pw.globalVars.append(Global(child.ident.value, True, child.init_expr.value))

        for func_name, func in list(program.functions().items()):
            if func.ident.value == "main":
                continue
            mv = pw.visitFunc(func_name, len(func.params))
            mv_dict[func_name] = mv
            symbol: FuncSymbol = func.getattr("symbol")
            for param in func.params:
                symbol.addParaTemp(param.accept(self, mv))

        # The function visitor of 'main' is special.
        mv = pw.visitMainFunc()

        mainFunc.body.accept(self, mv)
        # Remember to call mv.visitEnd after the translation a function.
        mv.visitEnd()

        for func_name, func in list(program.functions().items()):
            if func.ident.value == "main":
                continue
            mv = mv_dict[func_name]
            func.body.accept(self, mv)
            mv.visitEnd()

        # Remember to call pw.visitEnd before finishing the translation phase.
        return pw.visitEnd()

    def visitParameter(self, param: Parameter, mv: FuncVisitor) -> Temp:
        symbol = param.ident.getattr("symbol")
        symbol.temp = mv.freshTemp()
        return symbol.temp

    def visitFunctionCall(self, func: FunctionCall, mv: FuncVisitor) -> None:
        for param in func.params:
            param.accept(self, mv)
        for param in func.params:
            mv.visitParam(param.getattr("val"))
        func.setattr("val", mv.visitCall(mv.ctx.getFuncLabel(func.ident.value)))

    def visitBlock(self, block: Block, mv: FuncVisitor) -> None:
        for child in block:
            child.accept(self, mv)

    def visitReturn(self, stmt: Return, mv: FuncVisitor) -> None:
        stmt.expr.accept(self, mv)
        mv.visitReturn(stmt.expr.getattr("val"))

    def visitBreak(self, stmt: Break, mv: FuncVisitor) -> None:
        mv.visitBranch(mv.getBreakLabel())

    def visitContinue(self, stmt: Continue, mv: FuncVisitor) -> None:
        mv.visitBranch(mv.getContinueLabel())

    def visitIdentifier(self, ident: Identifier, mv: FuncVisitor) -> None:
        symbol: VarSymbol = ident.getattr("symbol")
        if isinstance(symbol.type, builtin_type.BuiltinType):
            if symbol.isGlobal:
                addr = mv.visitLoadSymbol(ident.value)
                symbol.temp = mv.visitLoadMem(addr, 0)
                ident.setattr("val", symbol.temp)
            else:
                ident.setattr("val", symbol.temp)
        else:
            if symbol.isGlobal:
                symbol.temp = mv.visitLoadSymbol(ident.value)
                ident.setattr("val", symbol.temp)
            else:
                ident.setattr("val", symbol.temp)

    def visitReference(self, ref: Reference, mv: FuncVisitor) -> None:
        ref.base.accept(self, mv)
        if ref.index != NULL:
            ref.index.accept(self, mv)
        ref.setattr("val", ref.base.getattr("val"))
        if isinstance(ref.base.type, ArrayType):
            if ref.index == NULL:
                temp = mv.visitLoad(0)
                ref.setattr("index", temp)
            else:
                temp = mv.visitBinary(tacop.BinaryOp.ADD, ref.base.getattr("index"), ref.index.getattr("val"))
                if isinstance(ref.type, ArrayType):
                    mv.visitBinarySelf(tacop.BinaryOp.MUL, temp, mv.visitLoad(ref.type.length))
                else:
                    mv.visitBinarySelf(tacop.BinaryOp.MUL, temp, mv.visitLoad(4))
                    mv.visitBinarySelf(tacop.BinaryOp.ADD, temp, ref.getattr("val"))
                    ref.setattr("val", mv.visitLoadMem(temp, 0))
                ref.setattr("index", temp)

    def visitDeclaration(self, decl: Declaration, mv: FuncVisitor) -> None:
        symbol: VarSymbol = decl.getattr("symbol")
        symbol.temp = mv.freshTemp()
        if not isinstance(symbol.type, builtin_type.BuiltinType):
            size = symbol.type.size
            print(decl, file=sys.stderr)
            symbol.temp = mv.visitAlloc(size)
        if decl.init_expr != NULL:
            decl.init_expr.accept(self, mv)
            mv.visitAssignment(symbol.temp, decl.init_expr.getattr("val"))

    def visitAssignment(self, expr: Assignment, mv: FuncVisitor) -> None:
        expr.rhs.accept(self, mv)
        expr.lhs.accept(self, mv)
        symbol: VarSymbol = expr.lhs.getattr("symbol")
        if isinstance(symbol.type, ArrayType):
            addr = expr.lhs.getattr("index")
            mv.visitStoreMem(expr.rhs.getattr("val"), addr, 0)
            expr.setattr("val", expr.rhs.getattr("val"))
        else:
            temp = expr.lhs.getattr("val")
            expr.setattr("val", mv.visitAssignment(temp, expr.rhs.getattr("val")))
            if symbol.isGlobal:
                addr = mv.visitLoadSymbol(symbol.name)
                mv.visitStoreMem(temp, addr, 0)

    def visitIf(self, stmt: If, mv: FuncVisitor) -> None:
        stmt.cond.accept(self, mv)

        if stmt.otherwise is NULL:
            skipLabel = mv.freshLabel()
            mv.visitCondBranch(
                tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), skipLabel
            )
            stmt.then.accept(self, mv)
            mv.visitLabel(skipLabel)
        else:
            skipLabel = mv.freshLabel()
            exitLabel = mv.freshLabel()
            mv.visitCondBranch(
                tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), skipLabel
            )
            stmt.then.accept(self, mv)
            mv.visitBranch(exitLabel)
            mv.visitLabel(skipLabel)
            stmt.otherwise.accept(self, mv)
            mv.visitLabel(exitLabel)

    def visitFor(self, stmt: For, mv: FuncVisitor) -> None:
        stmt.init.accept(self, mv)

        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)

        mv.visitLabel(beginLabel)
        if not isinstance(stmt.cond, node.NullType):
            stmt.cond.accept(self, mv)
            mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)

        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        stmt.update.accept(self, mv)

        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitWhile(self, stmt: While, mv: FuncVisitor) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)

        mv.visitLabel(beginLabel)
        stmt.cond.accept(self, mv)
        mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)

        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitDoWhile(self, stmt: DoWhile, mv: FuncVisitor) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)

        mv.visitLabel(beginLabel)
        stmt.body.accept(self, mv)

        mv.visitLabel(loopLabel)
        stmt.cond.accept(self, mv)
        mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)
        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitUnary(self, expr: Unary, mv: FuncVisitor) -> None:
        expr.operand.accept(self, mv)

        op = {
            node.UnaryOp.Neg: tacop.UnaryOp.NEG,
            node.UnaryOp.BitNot: tacop.UnaryOp.NOT,
            node.UnaryOp.LogicNot: tacop.UnaryOp.SEQZ,
            # You can add unary operations here.
        }[expr.op]
        expr.setattr("val", mv.visitUnary(op, expr.operand.getattr("val")))

    def visitBinary(self, expr: Binary, mv: FuncVisitor) -> None:
        expr.lhs.accept(self, mv)
        expr.rhs.accept(self, mv)

        op = {
            node.BinaryOp.Add: tacop.BinaryOp.ADD,
            node.BinaryOp.Sub: tacop.BinaryOp.SUB,
            node.BinaryOp.Mul: tacop.BinaryOp.MUL,
            node.BinaryOp.Div: tacop.BinaryOp.DIV,
            node.BinaryOp.Mod: tacop.BinaryOp.REM,
            node.BinaryOp.LT:  tacop.BinaryOp.SLT,
            node.BinaryOp.GT:  tacop.BinaryOp.SGT,
            node.BinaryOp.LogicAnd: tacop.BinaryOp.AND,
            node.BinaryOp.LogicOr:  tacop.BinaryOp.OR,
            node.BinaryOp.LE:  tacop.BinaryOp.LEQ,
            node.BinaryOp.GE:  tacop.BinaryOp.GEQ,
            node.BinaryOp.EQ:  tacop.BinaryOp.EQU,
            node.BinaryOp.NE:  tacop.BinaryOp.NEQ,
            # You can add binary operations here.
        }[expr.op]
        expr.setattr(
            "val", mv.visitBinary(op, expr.lhs.getattr("val"), expr.rhs.getattr("val"))
        )

    def visitCondExpr(self, expr: ConditionExpression, mv: FuncVisitor) -> None:
        """
        1. Refer to the implementation of visitIf and visitBinary.
        """
        expr.cond.accept(self, mv)
        skipLabel = mv.freshLabel()
        exitLabel = mv.freshLabel()
        mv.visitCondBranch(
            tacop.CondBranchOp.BEQ, expr.cond.getattr("val"), skipLabel
        )
        expr.then.accept(self, mv)
        mv.visitBranch(exitLabel)
        mv.visitLabel(skipLabel)
        expr.otherwise.accept(self, mv)
        mv.visitAssignment(expr.then.getattr("val"), expr.otherwise.getattr("val"))
        mv.visitLabel(exitLabel)
        expr.setattr("val", expr.then.getattr("val"))

    def visitIntLiteral(self, expr: IntLiteral, mv: FuncVisitor) -> None:
        expr.setattr("val", mv.visitLoad(expr.value))
