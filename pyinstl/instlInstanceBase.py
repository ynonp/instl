#!/usr/local/bin/python2.7
from __future__ import print_function

import sys
import os
import argparse
import yaml
import re
import tempfile
import shutil
from collections import OrderedDict, defaultdict

import configVar
from configVarList import ConfigVarList, value_ref_re
from aYaml import augmentedYaml
from installItem import InstallItem, read_index_from_yaml

import platform
current_os = platform.system()
if current_os == 'Darwin':
    current_os = 'mac'
elif current_os == 'Windows':
    current_os = 'win'

class cmd_line_options(object):
    """ namespace object to give to parse_args
        holds command line options
    """
    def __init__(self):
        self.input_files = None
        self.out_file_option = None
        self.main_targets = None
        self.state_file_option = None
        self.run = False
        self.alias_args = None

    def __str__(self):
        retVal = ("input_files: {self.input_files}\nout_file_option: {self.out_file_option}\n"+
                "main_targets: {self.main_targets}\nstate_file_option: {self.state_file_option}\n"+
                "run: {self.run}\n").format(**vars())
        return retVal

class InstlInstanceBase(object):
    """ Main object of instl. Keeps the state of variables and install index
        and knows how to create a batch file for installation. InstlInstanceBase
        must be inherited by platform specific implementations, such as InstlInstance_mac
        or InstlInstance_win.
    """
    def __init__(self):
        self.out_file_realpath = None
        self.install_definitions_index = dict()
        self.cvl = ConfigVarList()
        self.variables_assignment_lines = []
        self.install_instruction_lines = []
        self.var_replacement_pattern = None
        self.svn_version = "HEAD"

    def repr_for_yaml(self, what=None):
        """ Create representation of self suitable for printing as yaml.
            parameter 'what' is a list of identifiers to represent. If 'what'
            is None (the default) creare representation of everything.
            InstlInstanceBase object is represented as two yaml documents:
            one for define (tagged !define), one for the index (tagged !index).
        """
        retVal = list()
        if what is None: # None is all
            retVal.append(augmentedYaml.YamlDumpDocWrap(self.cvl, '!define', "Definitions", explicit_start=True, sort_mappings=True))
            retVal.append(augmentedYaml.YamlDumpDocWrap(self.install_definitions_index, '!index', "Installation index", explicit_start=True, sort_mappings=True))
        else:
            for item in what:
                if item in self.cvl:
                    retVal.append(self.cvl.repr_for_yaml(item))
                elif item in self.install_definitions_index:
                    retVal.append({item: self.install_definitions_index[item].repr_for_yaml()})
                else:
                    retVal.append(YamlDumpWrap(value="UNKNOWN VARIABLE", comment=name+" is not in variable list"))

        return retVal

    def read_command_line_options(self, arglist=None):
        """ parse command line options """
        try:
            if arglist and len(arglist) > 0:
                self.mode = "batch"
                parser = prepare_args_parser()
                name_space_obj = cmd_line_options()
                args = parser.parse_args(arglist, namespace=name_space_obj)
                if name_space_obj.alias_args:
                    self.something_to_do = ('alias', name_space_obj.alias_args)
                    self.mode = "do_something"
                else:
                    self.init_from_cmd_line_options(name_space_obj)
            else:
                self.mode = "interactive"
        except Exception as ex:
            print(ex)
            raise

    def do_something(self):
        try:
            import do_something
            do_something.do_something(self.something_to_do)
        except Exception as es:
            import traceback
            tb = traceback.format_exc()
            print("do_something", es, tb)

    def init_from_cmd_line_options(self, cmd_line_options_obj):
        """ turn command line options into variables """
        if cmd_line_options_obj.input_files:
            self.cvl.add_const_config_variable("__MAIN_INPUT_FILES__", "from commnad line options", *cmd_line_options_obj.input_files)
        if cmd_line_options_obj.out_file_option:
            self.cvl.add_const_config_variable("__MAIN_OUT_FILE__", "from commnad line options", cmd_line_options_obj.out_file_option[0])
        if cmd_line_options_obj.main_targets:
            self.cvl.add_const_config_variable("__CMD_INSTALL_TARGETS__", "from commnad line options", *cmd_line_options_obj.main_targets)
        if cmd_line_options_obj.state_file_option:
            self.cvl.add_const_config_variable("__MAIN_STATE_FILE__", "from commnad line options", cmd_line_options_obj.state_file_option)
        if cmd_line_options_obj.run:
            self.cvl.add_const_config_variable("__MAIN_RUN_INSTALLATION__", "from commnad line options", "yes")
        self.resolve()

    def digest(self):
        """
        """
        self.resolve()
        if "SVN_REPO_VERSION" in self.cvl:
            self.svn_version = self.cvl.get_str("SVN_REPO_VERSION")
        # command line targets take precedent, if they were not specifies, look for "MAIN_INSTALL_TARGETS"
        copy_main_install_to_from = None
        if "__CMD_INSTALL_TARGETS__" in self.cvl:
            copy_main_install_to_from = "__CMD_INSTALL_TARGETS__"
        elif "MAIN_INSTALL_TARGETS" in self.cvl:
            copy_main_install_to_from = "MAIN_INSTALL_TARGETS"
        if copy_main_install_to_from:
            self.cvl.duplicate_variable(copy_main_install_to_from, "__MAIN_INSTALL_TARGETS__")
        self.resolve()
        #self.evaluate_graph()

    def dedigest(self):
        """ reverse the effect of digest """
        del self.cvl["__MAIN_INSTALL_TARGETS__"]
        del self.cvl["__FULL_LIST_OF_INSTALL_TARGETS__"]
        del self.cvl["__ORPHAN_INSTALL_TARGETS__"]
        self.resolve()

    internal_identifier_re = re.compile("""
                                        __                  # dunder here
                                        (?P<internal_identifier>\w*)
                                        __                  # dunder there
                                        """, re.VERBOSE)
    def read_defines(self, a_node):
        # if document is empty we get a scalar node
        if a_node.isMapping():
            for identifier, value in a_node:
                if not self.internal_identifier_re.match(identifier): # do not read internal state indentifiers
                    self.cvl.set_variable(identifier, str(a_node[identifier].start_mark)).extend([item.value for item in a_node[identifier]])

    def read_index(self, a_node):
        self.install_definitions_index.update(read_index_from_yaml(a_node))
        with open("sample_data/yaml.out", "w") as wf:
            augmentedYaml.writeAsYaml(self.repr_for_yaml(), wf)

    def read_input_files(self):
        input_files = self.cvl.get("__MAIN_INPUT_FILES__", ())
        if input_files:
            file_actually_opened = list()
            for file_path in input_files:
                try:
                    self.read_file(file_path)
                except Exception as ex:
                    print("failed to read", file_path, ex)
                else:
                    file_actually_opened.append(os.path.abspath(file_path))
            self.cvl.add_const_config_variable("__MAIN_INPUT_FILES_ACTUALLY_OPENED__", "opened by read_input_files", *file_actually_opened)

    def read_file(self, file_path):
        try:
            with open(file_path, "r") as file_fd:
                for a_node in yaml.compose_all(file_fd):
                    if a_node.tag == u'!define':
                        self.read_defines(a_node)
                    elif a_node.tag == u'!index':
                        self.read_index(a_node)
                    else:
                        print("Unknown document tag '"+a_node.tag+"'; Tag should be one of: !define, !index'")
        except Exception as ex:
            import traceback
            tb = traceback.format_exc()
            print("read_file", file_path, ex, tb)

    def resolve(self):
        self.cvl.resolve()

    def sort_install_instructions_by_folder(self):
        full_install_to = self.cvl.get("__FULL_LIST_OF_INSTALL_TARGETS__", None)
        install_by_folder = defaultdict(set)
        for GUID in full_install_to:
            for folder in self.install_definitions_index[GUID].folder_list():
                install_by_folder[folder].add(GUID)
        return install_by_folder

    def create_install_list(self):
        main_install_to = self.cvl.get("__MAIN_INSTALL_TARGETS__")
        full_install_set = set()
        orphan_set = set()
        for GUID in main_install_to:
            try:
                self.install_definitions_index[GUID].get_recursive_depends(self.install_definitions_index, full_install_set, orphan_set)
            except KeyError:
                orphan_set.add(GUID)
        self.cvl.add_const_config_variable("__FULL_LIST_OF_INSTALL_TARGETS__", "calculated by create_install_list", *full_install_set)
        if orphan_set:
            self.cvl.add_const_config_variable("__ORPHAN_INSTALL_TARGETS__", "calculated by create_install_list", *orphan_set)

    def create_variables_assignment(self):
        for value in self.cvl:
            if not self.internal_identifier_re.match(value): # do not read internal state indentifiers
                self.variables_assignment_lines.append(value+'="'+" ".join(self.cvl[value])+'"')

    def create_install_instructions(self):
        self.create_variables_assignment()
        self.create_install_list()
        install_by_folder = self.sort_install_instructions_by_folder()
        if install_by_folder:
            for folder_name in install_by_folder:
                self.create_install_instructions_for_folder(folder_name, install_by_folder[folder_name])

    def create_install_instructions_for_folder(self, folder_name, items):
        self.install_instruction_lines.append(self.make_directory_cmd(folder_name))
        self.install_instruction_lines.append(self.change_directory_cmd(folder_name))
        for GUID in items: # folder in actions
            installi = self.install_definitions_index[GUID]
            actions = installi.action_list('folder_in')
            if actions:
                self.install_instruction_lines.append(" ".join(actions))
        for GUID in items:
            self.create_instal_instructions_for_item(self.install_definitions_index[GUID])         # pass the installItem object
        for GUID in items: # folder out actions
            installi = self.install_definitions_index[GUID]
            actions = installi.action_list('folder_out')
            if actions:
                self.install_instruction_lines.append(" ".join(actions))
        self.install_instruction_lines.append(os.linesep)

    def create_instal_instructions_for_item(self, installi):
        for action in installi.action_list('before'):           # actions to do before pulling from svn
            self.install_instruction_lines.append(action)
        for source in installi.source_list():                   # svn pulling actions
            self.create_svn_pull_instructions_for_source(source)
        for action in installi.action_list('after'):            # actions to do after pulling from svn
            self.install_instruction_lines.append(action)

    def create_svn_pull_instructions_for_source(self, source):
        """ source is a tuple (source_folder, tag), where tag is either !file or !dir """
        source_url = '$(BASE_URL)'+source[0]
        if source[1] == '!file':
            source_url_split = source_url.split('/')
            source_url_dir = '/'.join(source_url_split[:-1])
            source_url_file = source_url_split[-1]
            self.install_instruction_lines.append(" ".join(('"$(SVN_CLIENT_PATH)"', "checkout", "--revision", self.svn_version, '"'+source_url_dir+'"', ".", "--depth empty")))
            self.install_instruction_lines.append(" ".join(('"$(SVN_CLIENT_PATH)"', "up", '"'+source_url_file+'"')))
        else:
            self.install_instruction_lines.append(" ".join(('"$(SVN_CLIENT_PATH)"', "checkout", "--revision", self.svn_version, '"'+source_url+'"')))

    def create_install_instructions_lines(self):
        lines = list()
        lines.extend(self.get_install_instructions_prefix())
        lines.extend( (os.linesep, ) )

        lines.extend(sorted(self.variables_assignment_lines))
        lines.extend( (os.linesep, ) )

        lines.extend(self.install_instruction_lines)
        lines.extend( (os.linesep, ) )

        lines.extend(self.get_install_instructions_postfix())
        return lines

    def write_install_batch_file(self):
        lines = self.create_install_instructions_lines()
        lines_after_var_replacement = os.linesep.join([value_ref_re.sub(self.var_replacement_pattern, line) for line in lines])

        from utils import write_to_file_or_stdout
        out_file = self.cvl.get("__MAIN_OUT_FILE__", ("stdout",))
        with write_to_file_or_stdout(out_file[0]) as fd:
            fd.write(lines_after_var_replacement)
            fd.write(os.linesep)

        if out_file[0] != "stdout":
            self.out_file_realpath = os.path.realpath(out_file[0])
            os.chmod(self.out_file_realpath, 0744)

    def write_program_state(self):
        from utils import write_to_file_or_stdout
        state_file = self.cvl.get("__MAIN_STATE_FILE__", ("stdout",))
        with write_to_file_or_stdout(state_file[0]) as fd:
            augmentedYaml.writeAsYaml(self, fd)

    def find_cycles(self):
            if not self.install_definitions_index:
                print ("index empty - nothing to check")
            else:
                try:
                    from pyinstl import installItemGraph
                    graph = installItemGraph.create_installItem_graph(self.install_definitions_index)
                    cycles = installItemGraph.find_cycles(graph)
                    if not cycles:
                        print ("No cycles found")
                    else:
                        for cy in cycles:
                            print("cycle:", " -> ".join(cy))
                except ImportError as IE: # no installItemGraph, no worry
                    print("Could not load installItemGraph")

    def needs(self, guid, out_list):
        """ return all items that depend on guid """
        if guid not in self.install_definitions_index:
            raise KeyError(guid+" is not in index")
        for dep in self.install_definitions_index[guid].depend_list():
            if dep in self.install_definitions_index:
                out_list.append(dep)
                self.needs(dep, out_list)
            else:
                out_list.append(dep+"(missing)")

    def needed_by(self, guid):
        try:
            from pyinstl import installItemGraph
            graph = installItemGraph.create_installItem_graph(self.install_definitions_index)
            needed_by_list = installItemGraph.find_needed_by(graph, guid)
            return needed_by_list
        except ImportError as IE: # no installItemGraph, no worry
            print("Could not load installItemGraph")
            return None

    def do_da_interactive(self):
        try:
            from instlInstanceBase_interactive import go_interactive
            go_interactive(self)
        except Exception as es:
            print("go_interactive", es)
            raise

    def get_install_instructions_prefix(self):
        """ platform specific first lines of the install script
            must be overridden """
        raise  NotImplementedError

    def get_install_instructions_postfix(self):
        """ platform specific last lines of the install script
            must be overridden """
        raise  NotImplementedError

    def make_directory_cmd(self, directory):
        """ platform specific mkdir for install script
            must be overridden """
        raise  NotImplementedError

    def change_directory_cmd(self, directory):
        """ platform specific cd for install script
            must be overridden """
        raise  NotImplementedError

def prepare_args_parser():
    def decent_convert_arg_line_to_args(self, arg_line):
        """ parse a file with options so that we do not have to write one sub-option
            per line.  Remove empty lines and comment lines and end of line comments.
            ToDo: handle quotes
        """
        line_no_whitespce = arg_line.strip()
        if line_no_whitespce and line_no_whitespce[0] != '#':
            for arg in line_no_whitespce.split():
                if not arg:
                    continue
                elif  arg[0] == '#':
                    break
                yield arg

    parser = argparse.ArgumentParser(description='instl: cross platform svn based installer',
                    prefix_chars='-+',
                    fromfile_prefix_chars='@',
                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    argparse.ArgumentParser.convert_arg_line_to_args = decent_convert_arg_line_to_args
    standard_options = parser.add_argument_group(description='standard arguments:')
    standard_options.add_argument('input_files',
                                nargs='*',
                                metavar='file(s)-to-process',
                                help="One or more files containing dependencies and defintions")
    standard_options.add_argument('--out','-o',
                                required=False,
                                nargs=1,
                                default="stdout",
                                metavar='path-to-output-file',
                                dest='out_file_option',
                                help="a file to write installtion instructions")
    standard_options.add_argument('--target','-t',
                                required=False,
                                nargs='+',
                                default=["MAIN_INSTALL"],
                                metavar='which-target-to-install',
                                dest='main_targets',
                                help="Target to create install instructions for")
    standard_options.add_argument('--run','-r',
                                required=False,
                                default=False,
                                action='store_true',
                                dest='run',
                                help="run the installtion instructions script, requires --out")
    standard_options.add_argument('--state','-s',
                                required=False,
                                nargs='?',
                                const="stdout",
                                metavar='path-to-state-file',
                                dest='state_file_option',
                                help="a file to write program state - good for debugging")
    if current_os == 'mac':
        standard_options.add_argument('--alias','-a',
                                required=False,
                                nargs=2,
                                default=False,
                                metavar='create-an-alias',
                                dest='alias_args',
                                help="Create an alias of original in target (mac only)")
    return parser;