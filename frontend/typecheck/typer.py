from typing import Protocol, TypeVar

from frontend.ast.node import Node
from frontend.ast.tree import *
from frontend.ast.visitor import Visitor
from frontend.scope.globalscope import GlobalScope
from frontend.scope.scope import Scope, ScopeKind
from frontend.scope.scopestack import ScopeStack
from frontend.symbol.funcsymbol import FuncSymbol
from frontend.symbol.varsymbol import VarSymbol
from frontend.type.array import ArrayType
from utils.error import *

"""
The typer phase: type check abstract syntax tree.
"""


class Typer(Visitor[None, None]):
    def __init__(self) -> None:
        pass

    # Entry of this phase
    def transform(self, program: Program) -> Program:
        ctx = None
        program.accept(self, ctx)
        return program

    def visitProgram(self, program: Program, ctx: None) -> None:
        for child in program:
            if isinstance(child, Function):
                child.accept(self, ctx)

    def visitFunctionCall(self, func: FunctionCall, ctx: None) -> None:
        symbol: FuncSymbol = func.ident.getattr("symbol")
        func.type = symbol.type
        if func.type != INT:
            raise DecafTypeMismatchError()
    
    def visitFunction(self, func: Function, ctx: None) -> None:
        for param in func.params:
            param.accept(self, ctx)
        for child in func.body:
            child.accept(self, ctx)

    def visitBlock(self, block: Block, ctx: None) -> None:
        for child in block:
            child.accept(self, ctx)

    def visitReturn(self, stmt: Return, ctx: None) -> None:
        stmt.expr.accept(self, ctx)
        if stmt.expr.type != INT:
            raise DecafTypeMismatchError()

    def visitFor(self, stmt: For, ctx: None) -> None:
        stmt.init.accept(self, ctx)
        stmt.cond.accept(self, ctx)
        if stmt.cond != NULL and stmt.cond.type != INT:
            raise DecafTypeMismatchError()
        stmt.update.accept(self, ctx)
        stmt.body.accept(self, ctx)

    def visitIf(self, stmt: If, ctx: None) -> None:
        stmt.cond.accept(self, ctx)
        if stmt.cond.type != INT:
            raise DecafTypeMismatchError()
        stmt.then.accept(self, ctx)

        # check if the else branch exists
        if not stmt.otherwise is NULL:
            stmt.otherwise.accept(self, ctx)

    def visitWhile(self, stmt: While, ctx: None) -> None:
        stmt.cond.accept(self, ctx)
        if stmt.cond.type != INT:
            raise DecafTypeMismatchError()
        stmt.body.accept(self, ctx)

    def visitDoWhile(self, stmt: DoWhile, ctx: None) -> None:
        stmt.body.accept(self, ctx)
        stmt.cond.accept(self, ctx)
        if stmt.cond.type != INT:
            raise DecafTypeMismatchError()

    def visitDeclaration(self, decl: Declaration, ctx: None) -> None:
        if decl.init_expr != NULL:
            decl.init_expr.accept(self, ctx)
            if decl.init_expr.type != INT:
                raise DecafTypeMismatchError()

    def visitUnary(self, expr: Unary, ctx: None) -> None:
        expr.operand.accept(self, ctx)
        if expr.operand.type != INT:
            raise DecafTypeMismatchError()
        expr.type = INT

    def visitBinary(self, expr: Binary, ctx: None) -> None:
        expr.lhs.accept(self, ctx)
        if expr.lhs.type != INT:
            raise DecafTypeMismatchError()
        expr.rhs.accept(self, ctx)
        if expr.rhs.type != INT:
            raise DecafTypeMismatchError()
        expr.type = INT

    def visitCondExpr(self, expr: ConditionExpression, ctx: None) -> None:
        expr.cond.accept(self, ctx)
        if expr.cond.type != INT:
            raise DecafTypeMismatchError()
        expr.then.accept(self, ctx)
        if expr.then.type != INT:
            raise DecafTypeMismatchError()
        expr.otherwise.accept(self, ctx)
        if expr.otherwise.type != INT:
            raise DecafTypeMismatchError()
        expr.type = INT

    def visitIdentifier(self, ident: Identifier, ctx: None) -> None:
        symbol: VarSymbol = ident.getattr("symbol")
        ident.type = symbol.type

    def visitReference(self, ref: Reference, ctx: None) -> None:
        ref.base.accept(self, ctx)
        if ref.index != NULL:
            ref.index.accept(self, ctx)
            if ref.index.type != INT:
                raise DecafTypeMismatchError()
            if not isinstance(ref.base.type, ArrayType):
                raise DecafTypeMismatchError()
            ref.type = ref.base.type.base
        else:
            ref.type = ref.base.type

    def visitIntLiteral(self, expr: IntLiteral, ctx: None) -> None:
        expr.type = INT
