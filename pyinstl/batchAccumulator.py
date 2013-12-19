#!/usr/bin/env python2.7
from __future__ import print_function

from collections import OrderedDict, defaultdict

import pyinstl.log_utils
from pyinstl.log_utils import func_log_wrapper
from pyinstl.utils import *


class BatchAccumulator(object):
    """ from batchAccumulator import BatchAccumulator
        accumulate batch instructions and prepare them for writing to file
    """
    section_order = ("pre", "assign", "links", "upload", "sync", "copy", "admin", "post")

    @func_log_wrapper
    def __init__(self, in_cvl_obj):
        self.cvl = in_cvl_obj
        self.variables_assignment_lines = list()
        self.instruction_lines = defaultdict(list)
        self.indent_level = 0
        self.current_section = None

    @func_log_wrapper
    def set_current_section(self, section):
        if section in BatchAccumulator.section_order:
            self.current_section = section
        else:
            raise ValueError(section+" is not a known section name")

    @func_log_wrapper
    def add(self, instructions):
        if isinstance(instructions, basestring):
            self.instruction_lines[self.current_section].append(" " * 4 * self.indent_level + instructions)
        else:
            for instruction in instructions:
                self.add(instruction)

    def __iadd__(self, instructions):
        self.add(instructions)
        return self

    @func_log_wrapper
    def finalize_list_of_lines(self):
        lines = list()
        for section in BatchAccumulator.section_order:
            section_lines = self.instruction_lines[section]
            if section_lines:
                if section == "assign":
                    section_lines.sort()
                resolved_sync_instruction_lines = map(self.cvl.resolve_string, section_lines)
                lines.extend(resolved_sync_instruction_lines)
                lines.append("") # empty string will cause to emit new line
        return lines

    def merge_with(self, another_accum):
        save_section = self.current_section
        for section in BatchAccumulator.section_order:
            self.set_current_section(section)
            self += another_accum.instruction_lines[section]
        self.current_section = save_section