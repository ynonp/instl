#!/usr/bin/env python2.7
from __future__ import print_function
import abc
import logging
import yaml

import appdirs

import pyinstl.log_utils
from pyinstl.log_utils import func_log_wrapper
from configVarStack import value_ref_re
from aYaml import augmentedYaml
from pyinstl.utils import *
from pyinstl.searchPaths import SearchPaths
from batchAccumulator import BatchAccumulator
from installItem import read_index_from_yaml, InstallItem
from platformSpecificHelper_Base import PlatformSpecificHelperFactory
from configVarStack import var_stack as var_list

class InstlInstanceBase(object):
    """ Main object of instl. Keeps the state of variables and install index
        and knows how to create a batch file for installation. InstlInstanceBase
        must be inherited by platform specific implementations, such as InstlInstance_mac
        or InstlInstance_win.
    """
    __metaclass__ = abc.ABCMeta
    def __init__(self, initial_vars=None):
        # init objects owned by this class
        self.path_searcher = SearchPaths(var_list.get_configVar_obj("__SEARCH_PATHS__"))
        self.init_default_vars(initial_vars)
        # initialize the search paths helper with the current directory and dir where instl is now
        self.path_searcher.add_search_path(os.getcwd())
        self.path_searcher.add_search_path(os.path.dirname(os.path.realpath(sys.argv[0])))
        self.path_searcher.add_search_path(var_list.resolve("$(__INSTL_DATA_FOLDER__)"))

        self.platform_helper = PlatformSpecificHelperFactory(var_list.resolve("$(__CURRENT_OS__)"), self)
        self.platform_helper.init_copy_tool() # init initial copy tool, tool might be later overridden after reading variable COPY_TOOL from yaml.


        self.install_definitions_index = dict()
        self.batch_accum = BatchAccumulator()
        self.do_not_write_vars = ("INFO_MAP_SIG", "INDEX_SIG","PUBLIC_KEY")
        self.out_file_realpath = None


    def get_version_str(self):
        retVal = var_list.resolve("$(INSTL_EXEC_DISPLAY_NAME) version $(__INSTL_VERSION__) $(__COMPILATION_TIME__) $(__PLATFORM_NODE__)", list_sep=".", default="")
        return retVal

    def init_default_vars(self, initial_vars):
        if initial_vars:
            var_description = "from initial_vars"
            for var, value in initial_vars.iteritems():
                if isinstance(value, basestring):
                    var_list.add_const_config_variable(var, var_description, value)
                else:
                    var_list.add_const_config_variable(var, var_description, *value)

        var_description = "from InstlInstanceBase.init_default_vars"

        # read defaults/main.yaml
        main_defaults_file_path = os.path.join(var_list.resolve("$(__INSTL_DATA_FOLDER__)"), "defaults", "main.yaml")
        self.read_yaml_file(main_defaults_file_path)

        # read defaults/compile-info.yaml
        compile_info_file_path = os.path.join(var_list.resolve("$(__INSTL_DATA_FOLDER__)"), "defaults", "compile-info.yaml")
        if os.path.isfile(compile_info_file_path):
            self.read_yaml_file(compile_info_file_path)
        if "__COMPILATION_TIME__" not in var_list:
            if var_list.resolve("$(__INSTL_COMPILED__)") == "True":
                var_list.add_const_config_variable("__COMPILATION_TIME__", var_description, "unknown compilation time")
            else:
                var_list.add_const_config_variable("__COMPILATION_TIME__", var_description, "(not compiled)")

        # read class specific defaults/*.yaml
        class_specific_defaults_file_path = os.path.join(var_list.resolve("$(__INSTL_DATA_FOLDER__)"), "defaults", type(self).__name__+".yaml")
        if os.path.isfile(class_specific_defaults_file_path):
            self.read_yaml_file(class_specific_defaults_file_path)

        log_file = pyinstl.log_utils.get_log_file_path(var_list.resolve("$(INSTL_EXEC_DISPLAY_NAME)"), var_list.resolve("$(INSTL_EXEC_DISPLAY_NAME)"), debug=False)
        var_list.set_var("LOG_FILE", var_description).append(log_file)
        debug_log_file = pyinstl.log_utils.get_log_file_path(var_list.resolve("$(INSTL_EXEC_DISPLAY_NAME)"), var_list.resolve("$(INSTL_EXEC_DISPLAY_NAME)"), debug=True)
        var_list.set_var("LOG_FILE_DEBUG", var_description).extend( (debug_log_file, logging.getLevelName(pyinstl.log_utils.debug_logging_level), pyinstl.log_utils.debug_logging_started) )

    def check_prerequisite_var_existence(self, prerequisite_vars):
        missing_vars = [var for var in prerequisite_vars if var not in var_list]
        if len(missing_vars) > 0:
            msg = "Prerequisite variables were not defined: "+", ".join(missing_vars)
            logging.info("msg")
            raise ValueError(msg)

    def init_from_cmd_line_options(self, cmd_line_options_obj):
        """ turn command line options into variables """
        const_attrib_to_var = {
                         "input_file":      ("__MAIN_INPUT_FILE__", None),
                         "output_file":     ("__MAIN_OUT_FILE__", None),
                         "props_file":      ("__PROPS_FILE__", None),
                         "config_file":     ("__CONFIG_FILE__", None),
                         "sh1_checksum":    ("__SHA1_CHECKSUM__", None),
                         "rsa_signature":   ("__RSA_SIGNATURE__", None),
                         "start_progress":  ("__START_DYNAMIC_PROGRESS__", "0"),
                         "total_progress":  ("__TOTAL_DYNAMIC_PROGRESS__", "0"),
                         "just_with_number":  ("__JUST_WITH_NUMBER__", "0"),
                         "limit_command_to":  ("__LIMIT_COMMAND_TO__", None),
                         }

        for attrib, var in const_attrib_to_var.iteritems():
            attrib_value = getattr(cmd_line_options_obj, attrib)
            if attrib_value:
                var_list.add_const_config_variable(var[0], "from command line options", *attrib_value)
            elif var[1]: # there's a default
                var_list.add_const_config_variable(var[0], "from default", var[1])

        non_const_attrib_to_var = {
                        "filter_in":       "__FILTER_IN_VERSION__",
                         "target_repo_rev": "TARGET_REPO_REV",
                         "base_repo_rev":   "BASE_REPO_REV",
                         }

        for attrib, var in non_const_attrib_to_var.iteritems():
            attrib_value = getattr(cmd_line_options_obj, attrib)
            if attrib_value:
                var_list.set_var(var, "from command line options").append(attrib_value[0])

        if cmd_line_options_obj.command:
            var_list.set_var("__MAIN_COMMAND__", "from command line options").append(cmd_line_options_obj.command)

        if hasattr(cmd_line_options_obj, "subject") and cmd_line_options_obj.subject is not None:
            var_list.add_const_config_variable("__HELP_SUBJECT__", "from command line options", cmd_line_options_obj.subject)
        else:
            var_list.add_const_config_variable("__HELP_SUBJECT__", "from command line options", "")


        if cmd_line_options_obj.state_file:
            var_list.add_const_config_variable("__MAIN_STATE_FILE__", "from command line options", cmd_line_options_obj.state_file)
        if cmd_line_options_obj.filter_out:
            var_list.add_const_config_variable("__FILTER_OUT_PATHS__", "from command line options", *cmd_line_options_obj.filter_out)
        if cmd_line_options_obj.run:
            var_list.add_const_config_variable("__RUN_BATCH_FILE__", "from command line options", "yes")

    def is_acceptable_yaml_doc(self, doc_node):
        acceptables = var_list.resolve_to_list("$(ACCEPTABLE_YAML_DOC_TAGS)") + var_list.resolve_to_list("$(__ACCEPTABLE_YAML_DOC_TAGS__)")
        acceptables = ["!"+acceptibul for acceptibul in acceptables]
        retVal = doc_node.tag in acceptables
        return retVal

    def read_yaml_file(self, file_path):
        logging.info("%s", file_path)
        with open_for_read_file_or_url(file_path, self.path_searcher) as file_fd:
            for a_node in yaml.compose_all(file_fd):
                if self.is_acceptable_yaml_doc(a_node):
                    if a_node.tag.startswith('!define_const'):
                        self.read_const_defines(a_node)
                    elif a_node.tag.startswith('!define'):
                        self.read_defines(a_node)
                    elif a_node.tag.startswith('!index'):
                        self.read_index(a_node)
                    else:
                        read_yaml_func = getattr(self, "read_"+a_node.tag[1:])
                        if read_yaml_func:
                            read_yaml_func(self, a_node)
                        else:
                            logging.error("Unknown document tag '%s' while reading file %s; Tag should be one of: !define, !index'", a_node.tag, file_path)
        var_list.get_configVar_obj("__READ_YAML_FILES__").append(file_path)

    internal_identifier_re = re.compile("""
                                        __                  # dunder here
                                        (?P<internal_identifier>\w*)
                                        __                  # dunder there
                                        """, re.VERBOSE)

    def resolve_defined_paths(self):
        self.path_searcher.add_search_paths(var_list.resolve_to_list("$(SEARCH_PATHS)"))
        for path_var_to_resolve in var_list.resolve_to_list("$(PATHS_TO_RESOLVE)"):
            if path_var_to_resolve in var_list:
                resolved_path = self.path_searcher.find_file(var_list.resolve_var(path_var_to_resolve), return_original_if_not_found=True)
                var_list.set_var(path_var_to_resolve, "resolve_defined_paths").append(resolved_path)



    def read_defines(self, a_node):
        # if document is empty we get a scalar node
        if a_node.isMapping():
            for identifier, contents in a_node:
                logging.debug("%s: %s", identifier, str(contents))
                if not self.internal_identifier_re.match(identifier): # do not read internal state identifiers
                    var_list.set_var(identifier, str(contents.start_mark)).extend([item.value for item in contents])
                elif identifier == '__include__':
                    self.read_include_node(contents)

    def read_const_defines(self, a_node):
        """ Read a !define_const sub-doc. All variables will be made const.
            Reading of internal state identifiers is allowed.
            __include__ is not allowed.
        """
        if a_node.isMapping():
            for identifier, contents in a_node:
                if identifier == "__include__":
                    raise ValueError("!define_const doc cannot except __include__")
                logging.debug("%s: %s", identifier, str(contents))
                var_list.add_const_config_variable(identifier, "from !define_const section", *[item.value for item in contents])

    def read_include_node(self, i_node):
        if i_node.isScalar():
            resolved_file_name = var_list.resolve(i_node.value)
            self.read_yaml_file(resolved_file_name)
        elif i_node.isSequence():
            for sub_i_node in i_node:
                self.read_include_node(sub_i_node)
        elif i_node.isMapping():
            if "url" in i_node and "checksum" in i_node and "sig" in i_node:
                resolved_file_url = var_list.resolve(i_node["url"].value)
                resolved_checksum = var_list.resolve(i_node["checksum"].value)
                resolved_signature = var_list.resolve(i_node["sig"].value)
                cached_files_dir = self.get_default_sync_dir(continue_dir="cache", mkdir=True)
                cached_file = os.path.join(cached_files_dir, resolved_checksum)

                if "PUBLIC_KEY" not in var_list:
                    if "PUBLIC_KEY_FILE" in var_list:
                        public_key_file = var_list.resolve("$(PUBLIC_KEY_FILE)")
                        with open_for_read_file_or_url(public_key_file, self.path_searcher) as file_fd:
                            public_key_text = file_fd.read()
                            var_list.set_var("PUBLIC_KEY", "from "+public_key_file).append(public_key_text)


                public_key_text = var_list.resolve("$(PUBLIC_KEY)")
                download_from_file_or_url(resolved_file_url, cached_file, cache=True,
                                          public_key=public_key_text,
                                          textual_sig=resolved_signature,
                                          expected_checksum=resolved_checksum)
                self.read_yaml_file(cached_file)
                if "copy" in i_node:
                    self.batch_accum.set_current_section('post-sync')
                    self.batch_accum += self.platform_helper.copy_tool.copy_file_to_file(cached_file, var_list.resolve(i_node["copy"].value), link_dest=True)

    def create_variables_assignment(self):
        self.batch_accum.set_current_section("assign")
        for identifier in var_list:
            if identifier not in self.do_not_write_vars:
                self.batch_accum += self.platform_helper.var_assign(identifier,var_list.resolve_var(identifier), None) # var_list[identifier].resolved_num

    def get_default_sync_dir(self, continue_dir=None, mkdir=True):
        retVal = None
        os_family_name = var_list.resolve("$(__CURRENT_OS__)")
        if os_family_name == "Mac":
            user_cache_dir_param = "$(COMPANY_NAME)/$(INSTL_EXEC_DISPLAY_NAME)"
            retVal = appdirs.user_cache_dir(user_cache_dir_param)
        elif os_family_name == "Win":
            retVal = appdirs.user_cache_dir("$(INSTL_EXEC_DISPLAY_NAME)", "$(COMPANY_NAME)")
        elif os_family_name == "Linux":
            user_cache_dir_param = "$(COMPANY_NAME)/$(INSTL_EXEC_DISPLAY_NAME)"
            retVal = appdirs.user_cache_dir(user_cache_dir_param)
        if continue_dir:
            #from_url = from_url.lstrip("/\\")
            #from_url = from_url.rstrip("/\\")
            retVal = os.path.join(retVal, continue_dir)
        #print("1------------------", user_cache_dir, "-", from_url, "-", retVal)
        if mkdir and retVal:
            retVal = var_list.resolve(retVal)
            safe_makedirs(retVal)
        return retVal

    def relative_sync_folder_for_source(self, source):
        retVal = None
        if source[1] in ('!dir', '!file'):
            retVal = "/".join(source[0].split("/")[0:-1])
        elif source[1] in ('!dir_cont', '!files'):
            retVal = source[0]
        else:
            raise ValueError("unknown tag for source "+source[0]+": "+source[1])
        return retVal

    def write_batch_file(self):
        self.batch_accum.set_current_section('pre')
        self.batch_accum += self.platform_helper.get_install_instructions_prefix()
        self.batch_accum.set_current_section('post')
        var_list.set_var("TOTAL_ITEMS_FOR_PROGRESS_REPORT").append(str(self.platform_helper.num_items_for_progress_report))
        self.batch_accum += self.platform_helper.get_install_instructions_postfix()
        lines = self.batch_accum.finalize_list_of_lines()
        lines_after_var_replacement = '\n'.join([value_ref_re.sub(self.platform_helper.var_replacement_pattern, line) for line in lines])

        from utils import write_to_file_or_stdout
        out_file = var_list.resolve("$(__MAIN_OUT_FILE__)")
        with write_to_file_or_stdout(out_file) as fd:
            fd.write(lines_after_var_replacement)
            fd.write('\n')

        if out_file != "stdout":
            self.out_file_realpath = os.path.realpath(out_file)
            # chmod to 0777 so that file created under sudo, can be re-written under regular user.
            # However regular user cannot chmod for file created under sudo, hence the try/except
            try: os.chmod(self.out_file_realpath, 0777)
            except: pass
        else:
            self.out_file_realpath = "stdout"
        msg = " ".join( (self.out_file_realpath, str(self.platform_helper.num_items_for_progress_report), "progress items") )
        print(msg)
        logging.info(msg)

    def run_batch_file(self):
        logging.info("running batch file %s", self.out_file_realpath)
        from subprocess import Popen
        p = Popen([self.out_file_realpath], shell=False)
        unused_stdout, unused_stderr = p.communicate()
        retcode = p.returncode
        if retcode != 0:
            raise SystemExit(self.out_file_realpath + " returned exit code " + str(retcode))

    def write_program_state(self):
        from utils import write_to_file_or_stdout
        state_file = var_list.resolve("$(__MAIN_STATE_FILE__)")
        with write_to_file_or_stdout(state_file) as fd:
            augmentedYaml.writeAsYaml(self, fd)

    def read_index(self, a_node):
        self.install_definitions_index.update(read_index_from_yaml(a_node))

    def find_cycles(self):
            if not self.install_definitions_index:
                print ("index empty - nothing to check")
            else:
                try:
                    from pyinstl import installItemGraph
                    depend_graph = installItemGraph.create_dependencies_graph(self.install_definitions_index)
                    depend_cycles = installItemGraph.find_cycles(depend_graph)
                    if not depend_cycles:
                        print ("No depend cycles found")
                    else:
                        for cy in depend_cycles:
                            print("depend cycle:", " -> ".join(cy))
                    inherit_graph = installItemGraph.create_inheritItem_graph(self.install_definitions_index)
                    inherit_cycles = installItemGraph.find_cycles(inherit_graph)
                    if not inherit_cycles:
                        print ("No inherit cycles found")
                    else:
                        for cy in inherit_cycles:
                            print("inherit cycle:", " -> ".join(cy))
                except ImportError: # no installItemGraph, no worry
                    print("Could not load installItemGraph")

    def read_info_map_file(self, in_file_path):
        self.svnTree.read_info_map_from_file(in_file_path)

    def write_info_map_file(self):
        self.svnTree.write_to_file(var_list.resolve("$(__MAIN_OUT_FILE__)"))

