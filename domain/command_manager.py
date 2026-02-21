from __future__ import annotations

from dataclasses import dataclass, field

from domain.commands import Command
from domain.model import SpecModel


@dataclass
class CommandManager:
    model: SpecModel
    undo_stack: list[Command] = field(default_factory=list)
    redo_stack: list[Command] = field(default_factory=list)
    is_dirty: bool = False

    def execute(self, command: Command) -> None:
        command.apply(self.model)
        self.undo_stack.append(command)
        self.redo_stack.clear()
        self.is_dirty = True

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        command = self.undo_stack.pop()
        command.rollback(self.model)
        self.redo_stack.append(command)
        self.is_dirty = True
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        command = self.redo_stack.pop()
        command.apply(self.model)
        self.undo_stack.append(command)
        self.is_dirty = True
        return True

    def clear_history(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.is_dirty = False
