#!/usr/bin/env python2.7
from __future__ import print_function
import abc
import logging
import yaml

import appdirs

import pyinstl.log_utils
from pyinstl.log_utils import func_log_wrapper
from configVarList import ConfigVarList, value_ref_re
from aYaml import augmentedYaml
from pyinstl.utils import *
from pyinstl.searchPaths import SearchPaths
from instlException import InstlException
from platformSpecificHelper_Base import PlatformSpecificHelperFactory
from batchAccumulator import BatchAccumulator

current_os_names = get_current_os_names()
os_family_name = current_os_names[0]
os_second_name = current_os_names[0]
if len(current_os_names) > 1:
    os_second_name = current_os_names[1]

INSTL_VERSION=(0, 6, 5)
this_program_name = "instl"


class InstlInstanceBase(object):
    """ Main object of instl. Keeps the state of variables and install index
        and knows how to create a batch file for installation. InstlInstanceBase
        must be inherited by platform specific implementations, such as InstlInstance_mac
        or InstlInstance_win.
    """
    __metaclass__ = abc.ABCMeta
    @func_log_wrapper
    def __init__(self, initial_vars=None):
        # init objects owned by this class
        self.cvl = ConfigVarList()
        self.platform_helper = PlatformSpecificHelperFactory(os_family_name, self)
        self.batch_accum = BatchAccumulator(self.cvl)

        self.out_file_realpath = None
        self.init_default_vars(initial_vars)

        # initialize the search paths helper with the current directory and dir where instl is now
        self.search_paths_helper = SearchPaths(self.cvl.get_configVar_obj("__SEARCH_PATHS__"))
        self.search_paths_helper.add_search_path(os.getcwd())
        self.search_paths_helper.add_search_path(os.path.dirname(os.path.realpath(sys.argv[0])))
        self.search_paths_helper.add_search_path(self.cvl.get_str("__INSTL_DATA_FOLDER__"))

        self.guid_re = re.compile("""
                        [a-f0-9]{8}
                        (-[a-f0-9]{4}){3}
                        -[a-f0-9]{12}
                        $
                        """, re.VERBOSE)

    def get_version_str(self):
        retVal = " ".join( (this_program_name, "version", ".".join(self.cvl.get_list("__INSTL_VERSION__"))) )
        return retVal

    @func_log_wrapper
    def init_default_vars(self, initial_vars):
        if initial_vars:
            var_description = "from initial_vars"
            for var, value in initial_vars.iteritems():
                self.cvl.add_const_config_variable(var, var_description, value)

        var_description = "from InstlInstanceBase.init_default_vars"
        self.cvl.add_const_config_variable("__CURRENT_OS__", var_description, os_family_name)
        self.cvl.add_const_config_variable("__CURRENT_OS_SECOND_NAME__", var_description, os_second_name)
        self.cvl.add_const_config_variable("__CURRENT_OS_NAMES__", var_description, *current_os_names)
        self.cvl.set_variable("TARGET_OS", var_description).append(os_family_name)
        self.cvl.set_variable("TARGET_OS_NAMES", var_description).extend(current_os_names)
        self.cvl.add_const_config_variable("TARGET_OS_SECOND_NAME", var_description, os_second_name)
        self.cvl.add_const_config_variable("__INSTL_VERSION__", var_description, *INSTL_VERSION)
        self.cvl.set_variable("BASE_REPO_REV", var_description).append("1")

        log_file = pyinstl.log_utils.get_log_file_path(this_program_name, this_program_name, debug=False)
        self.cvl.set_variable("LOG_FILE", var_description).append(log_file)
        debug_log_file = pyinstl.log_utils.get_log_file_path(this_program_name, this_program_name, debug=True)
        self.cvl.set_variable("LOG_FILE_DEBUG", var_description).extend( (debug_log_file, logging.getLevelName(pyinstl.log_utils.debug_logging_level), pyinstl.log_utils.debug_logging_started) )
        for identifier in self.cvl:
            logging.debug("... %s: %s", identifier, self.cvl.get_str(identifier))


    @func_log_wrapper
    def init_from_cmd_line_options(self, cmd_line_options_obj):
        """ turn command line options into variables """
        if cmd_line_options_obj.input_file:
            self.cvl.add_const_config_variable("__MAIN_INPUT_FILE__", "from command line options", cmd_line_options_obj.input_file[0])
        if cmd_line_options_obj.output_file:
            self.cvl.add_const_config_variable("__MAIN_OUT_FILE__", "from command line options", cmd_line_options_obj.output_file[0])
        if cmd_line_options_obj.state_file:
            self.cvl.add_const_config_variable("__MAIN_STATE_FILE__", "from command line options", cmd_line_options_obj.state_file)
        if cmd_line_options_obj.props_file:
            self.cvl.add_const_config_variable("__PROPS_FILE__", "from command line options", cmd_line_options_obj.props_file[0])
        if cmd_line_options_obj.filter_out:
            self.cvl.add_const_config_variable("__FILTER_OUT_PATHS__", "from command line options", *cmd_line_options_obj.filter_out)
        if cmd_line_options_obj.filter_in:
            self.cvl.add_const_config_variable("__FILTER_IN_VERSION__", "from command line options", cmd_line_options_obj.filter_in[0])
        if cmd_line_options_obj.run:
            self.cvl.add_const_config_variable("__RUN_BATCH_FILE__", "from command line options", "yes")
        if cmd_line_options_obj.command:
            self.cvl.set_variable("__MAIN_COMMAND__", "from command line options").append(cmd_line_options_obj.command)

        if cmd_line_options_obj.repo_rev:
            self.cvl.set_variable("REPO_REV", "from command line options").append(cmd_line_options_obj.repo_rev[0])
        if cmd_line_options_obj.base_repo_rev:
            self.cvl.set_variable("BASE_REPO_REV", "from command line options").append(cmd_line_options_obj.base_repo_rev[0])

        if cmd_line_options_obj.config_file:
            self.cvl.add_const_config_variable("__CONFIG_FILE__", "from command line options", cmd_line_options_obj.config_file[0])
        if cmd_line_options_obj.folder:
            self.cvl.add_const_config_variable("__FOLDER__", "from command line options", cmd_line_options_obj.folder[0])
        if cmd_line_options_obj.svn:
            self.cvl.add_const_config_variable("__ISSUE_SVN_COMMANDS__", "from command line options")

        if cmd_line_options_obj.staging_folder:
            self.cvl.add_const_config_variable("__STAGING_FOLDER__", "from command line options", cmd_line_options_obj.staging_folder[0])
        if cmd_line_options_obj.svn_folder:
            self.cvl.add_const_config_variable("__SVN_FOLDER__", "from command line options", cmd_line_options_obj.svn_folder[0])

        if hasattr(cmd_line_options_obj, "subject") and cmd_line_options_obj.subject is not None:
            self.cvl.add_const_config_variable("__HELP_SUBJECT__", "from command line options", cmd_line_options_obj.subject)
        else:
            self.cvl.add_const_config_variable("__HELP_SUBJECT__", "from command line options", "")

        for identifier in self.cvl:
            logging.debug("... %s: %s", identifier, self.cvl.get_str(identifier))

    def is_acceptable_yaml_doc(self, doc_node):
        acceptables = self.cvl.get_list("ACCEPTABLE_YAML_DOC_TAGS") + ("define", "index")
        acceptables = ["!"+acceptibul for acceptibul in acceptables]
        retVal = doc_node.tag in acceptables
        return retVal

    @func_log_wrapper
    def read_yaml_file(self, file_path):
        try:
            logging.info("... Reading input file %s", file_path)
            with open_for_read_file_or_url(file_path, self.search_paths_helper) as file_fd:
                for a_node in yaml.compose_all(file_fd):
                    if self.is_acceptable_yaml_doc(a_node):
                        if a_node.tag.startswith('!define'):
                            self.read_defines(a_node)
                        elif a_node.tag.startswith('!index'):
                            self.read_index(a_node)
                        else:
                            logging.error("Unknown document tag '%s' while reading file %s; Tag should be one of: !define, !index'", a_node.tag, file_path)
        except InstlException as unused_ie:
            raise # re-raise in case of recursive call to read_file
        except yaml.YAMLError as ye:
            raise InstlException(" ".join( ("YAML error while reading file", "'"+file_path+"':\n", str(ye)) ), ye)
        except IOError as ioe:
            raise InstlException(" ".join(("Failed to read file", "'"+file_path+"'", ":")), ioe)

    internal_identifier_re = re.compile("""
                                        __                  # dunder here
                                        (?P<internal_identifier>\w*)
                                        __                  # dunder there
                                        """, re.VERBOSE)

    def resolve_defined_paths(self):
        self.search_paths_helper.add_search_paths(self.cvl.get_list("SEARCH_PATHS"))
        for path_var_to_resolve in self.cvl.get_list("PATHS_TO_RESOLVE"):
            if path_var_to_resolve in self.cvl:
                resolved_path = self.instlInstance.search_paths_helper.find_file_with_search_paths(self.cvl.get_str(path_var_to_resolve), return_original_if_not_found=True)
                self.cvl.set_variable(path_var_to_resolve, "resolve_defined_paths").append(resolved_path)



    @func_log_wrapper
    def read_defines(self, a_node):
        # if document is empty we get a scalar node
        if a_node.isMapping():
            for identifier, contents in a_node:
                logging.debug("... %s: %s", identifier, str(contents))
                if not self.internal_identifier_re.match(identifier): # do not read internal state identifiers
                    self.cvl.set_variable(identifier, str(contents.start_mark)).extend([item.value for item in contents])
                elif identifier == '__include__':
                    for file_name in contents:
                        resolved_file_name = self.cvl.resolve_string(file_name.value)
                        self.read_yaml_file(resolved_file_name)

    @func_log_wrapper
    def create_variables_assignment(self):
        self.batch_accum.set_current_section("assign")
        for identifier in self.cvl:
            self.batch_accum += self.platform_helper.var_assign(identifier,self.cvl.get_str(identifier))

    @func_log_wrapper
    def get_default_sync_dir(self):
        retVal = None
        user_cache_dir = None
        if os_family_name == "Mac":
            user_cache_dir_param = self.cvl.get_str("COMPANY_NAME")+"/"+this_program_name
            user_cache_dir = appdirs.user_cache_dir(user_cache_dir_param)
        elif os_family_name == "Win":
            user_cache_dir = appdirs.user_cache_dir(this_program_name, self.cvl.get_str("COMPANY_NAME"))
        from_url = main_url_item(self.cvl.get_str("SYNC_BASE_URL"))
        if from_url:
            from_url = from_url.lstrip("/\\")
            from_url = from_url.rstrip("/\\")
            retVal = os.path.normpath(os.path.join(user_cache_dir, from_url))
        else:
            raise ValueError("'SYNC_BASE_URL' was not properly defined")
        #print("1------------------", user_cache_dir, "-", from_url, "-", retVal)
        return retVal

    @func_log_wrapper
    def init_copy_vars(self):
        var_description = "from InstlInstanceBase.init_copy_vars"
        if "SET_ICON_PATH" in self.cvl:
            setIcon_full_path = self.search_paths_helper.find_file_with_search_paths(self.cvl.get_str("SET_ICON_PATH"))
            self.cvl.set_variable("SET_ICON_PATH", var_description).append(setIcon_full_path)
# check which variables are needed for for offline install....
        if "REL_SRC_PATH" not in self.cvl: #?
            if "SYNC_BASE_URL" not in self.cvl:
                raise ValueError("'SYNC_BASE_URL' was not defined")
            if "SYNC_TRAGET_OS_URL" not in self.cvl:
                self.cvl.set_variable("SYNC_TRAGET_OS_URL", var_description).append("$(SYNC_BASE_URL)/$(TARGET_OS)")
            rel_sources = relative_url(self.cvl.get_str("SYNC_BASE_URL"), self.cvl.get_str("SYNC_TRAGET_OS_URL"))
            self.cvl.set_variable("REL_SRC_PATH", var_description).append(rel_sources)

        self.cvl.set_value_if_var_does_not_exist("LOCAL_SYNC_DIR", self.get_default_sync_dir(), description=var_description)

        if "COPY_TOOL" not in self.cvl:
            from platformSpecificHelper_Base import DefaultCopyToolName
            self.cvl.set_variable("COPY_TOOL", var_description).append(DefaultCopyToolName(self.cvl.get_str("TARGET_OS")))
        for identifier in ("REL_SRC_PATH", "COPY_TOOL"):
            logging.debug("... %s: %s", identifier, self.cvl.get_str(identifier))

    @func_log_wrapper
    def relative_sync_folder_for_source(self, source):
        retVal = None
        if source[1] in ('!dir', '!file'):
            retVal = "/".join(source[0].split("/")[0:-1])
        elif source[1] in ('!dir_cont', '!files'):
            retVal = source[0]
        else:
            raise ValueError("unknown tag for source "+source[0]+": "+source[1])
        return retVal

    @func_log_wrapper
    def write_batch_file(self):
        self.batch_accum.set_current_section('pre')
        self.batch_accum += self.platform_helper.get_install_instructions_prefix()
        self.batch_accum.set_current_section('post')
        self.cvl.set_variable("TOTAL_ITEMS_FOR_PROGRESS_REPORT").append(str(self.platform_helper.num_items_for_progress_report))
        self.batch_accum += self.platform_helper.get_install_instructions_postfix()
        lines = self.batch_accum.finalize_list_of_lines()
        lines_after_var_replacement = '\n'.join([value_ref_re.sub(self.platform_helper.var_replacement_pattern, line) for line in lines])

        from utils import write_to_file_or_stdout
        out_file = self.cvl.get_str("__MAIN_OUT_FILE__")
        logging.info("... %s", out_file)
        with write_to_file_or_stdout(out_file) as fd:
            fd.write(lines_after_var_replacement)
            fd.write('\n')

        if out_file != "stdout":
            self.out_file_realpath = os.path.realpath(out_file)
            os.chmod(self.out_file_realpath, 0755)
        print(out_file)

    @func_log_wrapper
    def run_batch_file(self):
        logging.info("running batch file %s", self.out_file_realpath)
        from subprocess import Popen
        p = Popen(self.out_file_realpath)
        unused_stdout, unused_stderr = p.communicate()

    @func_log_wrapper
    def write_program_state(self):
        from utils import write_to_file_or_stdout
        state_file = self.cvl.get_str("__MAIN_STATE_FILE__")
        with write_to_file_or_stdout(state_file) as fd:
            augmentedYaml.writeAsYaml(self, fd)

