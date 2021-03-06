#!/usr/bin/env python2.7
from __future__ import print_function

import abc
import urllib
from pyinstl.utils import *
from configVarStack import var_stack as var_list


class CopyToolBase(object):
    """ Create copy commands. Each function should be overridden to implement the copying
        on specific platform using a specific copying tool. All functions return
        a list of commands, even if there is only one. This will allow to return
        multiple commands if needed.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, platform_helper):
        self.platform_helper = platform_helper

    @abc.abstractmethod
    def finalize(self):
        pass

    @abc.abstractmethod
    def begin_copy_folder(self):
        pass

    @abc.abstractmethod
    def end_copy_folder(self):
        pass

    @abc.abstractmethod
    def copy_dir_to_dir(self, src_dir, trg_dir, link_dest=False, ignore=None):
        """ Copy src_dir as a folder into trg_dir.
            Example: copy_dir_to_dir("a", "/d/c/b") creates the folder:
            "/d/c/b/a"
        """
        pass

    @abc.abstractmethod
    def copy_file_to_dir(self, src_file, trg_dir, link_dest=False, ignore=None):
        """ Copy the file src_file into trg_dir.
            Example: copy_file_to_dir("a.txt", "/d/c/b") creates the file:
            "/d/c/b/a.txt"
        """
        pass

    @abc.abstractmethod
    def copy_dir_contents_to_dir(self, src_dir, trg_dir, link_dest=False, ignore=None):
        """ Copy the contents of src_dir into trg_dir.
            Example: copy_dir_contents_to_dir("a", "/d/c/b") copies
            everything from a into "/d/c/b"
        """
        pass

    @abc.abstractmethod
    def copy_dir_files_to_dir(self, src_dir, trg_dir, link_dest=False, ignore=None):
        """ Copy the files of src_dir into trg_dir.
            Example: copy_dir_contents_to_dir("a", "/d/c/b") copies
            all files from a into "/d/c/b", subfolders of a are not copied
        """
        pass

    @abc.abstractmethod
    def copy_file_to_file(self, src_file, trg_file, link_dest=False, ignore=None):
        """ Copy file src_file into trg_file.
            Example: copy_file_to_file("a", "/d/c/b") copies
            the file a to the file "/d/c/b".
        """
        pass

class CopyToolRsync(CopyToolBase):
    def __init__(self, platform_helper):
        super(CopyToolRsync, self).__init__(platform_helper)

    def finalize(self):
        pass

    def begin_copy_folder(self):
        return ()

    def end_copy_folder(self):
        return ()

    def create_ignore_spec(self, ignore):
        retVal = ""
        if ignore:
            if isinstance(ignore, basestring):
                ignore = (ignore,)
            retVal = " ".join(["--exclude="+quoteme_single(ignoree) for ignoree in ignore])
        return retVal

    def copy_dir_to_dir(self, src_dir, trg_dir, link_dest=False, ignore=None):
        if src_dir.endswith("/"):
            src_dir.rstrip("/")
        ignore_spec = self.create_ignore_spec(ignore)
        if link_dest:
            the_link_dest = os.path.join(src_dir, "..")
            sync_command = "rsync --owner --group -l -r -E --delete {ignore_spec} --link-dest=\"{the_link_dest}\" \"{src_dir}\" \"{trg_dir}\"".format(**locals())
        else:
            sync_command = "rsync --owner --group -l -r -E --delete {ignore_spec} \"{src_dir}\" \"{trg_dir}\"".format(**locals())

        return sync_command

    def copy_file_to_dir(self, src_file, trg_dir, link_dest=False, ignore=None):
        assert not src_file.endswith("/")
        ignore_spec = self.create_ignore_spec(ignore)
        if link_dest:
            the_link_dest, src_file_name = os.path.split(src_file)
            relative_link_dest = os.path.relpath(the_link_dest, trg_dir)
            sync_command = "rsync --owner --group -l -r -E {ignore_spec} --link-dest=\"{relative_link_dest}\" \"{src_file}\" \"{trg_dir}\"".format(**locals())
        else:
            sync_command = "rsync --owner --group -l -r -E {ignore_spec} \"{src_file}\" \"{trg_dir}\"".format(**locals())
        return sync_command

    def copy_file_to_file(self, src_file, trg_file, link_dest=False, ignore=None):
        assert not src_file.endswith("/")
        ignore_spec = self.create_ignore_spec(ignore)
        if link_dest:
            src_folder_name, src_file_name = os.path.split(src_file)
            trg_folder_name, trg_file_name = os.path.split(trg_file)
            relative_link_dest = os.path.relpath(src_folder_name, trg_folder_name)
            sync_command = "rsync --owner --group -l -r -E {ignore_spec} --link-dest=\"{relative_link_dest}\" \"{src_file}\" \"{trg_file}\"".format(**locals())
        else:
            sync_command = "rsync --owner --group -l -r -E {ignore_spec} \"{src_file}\" \"{trg_file}\"".format(**locals())
        return sync_command

    def copy_dir_contents_to_dir(self, src_dir, trg_dir, link_dest=False, ignore=None):
        if not src_dir.endswith("/"):
            src_dir += "/"
        ignore_spec = self.create_ignore_spec(ignore)
        if link_dest:
            relative_link_dest = os.path.relpath(src_dir, trg_dir)
            sync_command = "rsync --owner --group -l -r -E {ignore_spec} --link-dest=\"{relative_link_dest}\" \"{src_dir}\" \"{trg_dir}\"".format(**locals())
        else:
            sync_command = "rsync --owner --group -l -r -E {ignore_spec} \"{src_dir}\" \"{trg_dir}\"".format(**locals())
        return sync_command

    def copy_dir_files_to_dir(self, src_dir, trg_dir, link_dest=False, ignore=None):
        if not src_dir.endswith("/"):
            src_dir += "/"
        # in order for * to correctly expand, it must be outside the quotes, e.g. to copy all files in folder a: A=a ; "${A}"/* and not "${A}/*"
        ignore_spec = self.create_ignore_spec(ignore)
        if link_dest:
            relative_link_dest = os.path.relpath(src_dir, trg_dir)
            sync_command = "rsync --owner --group -l -E -d {ignore_spec} --link-dest=\"{relative_link_dest}\" \"{src_dir}\" \"{trg_dir}\"".format(**locals())
        else:
            sync_command = "rsync --owner --group -l -E -d {ignore_spec} \"{src_dir}\"/* \"{trg_dir}\"".format(**locals())

        return sync_command

class PlatformSpecificHelperBase(object):

    def __init__(self, instlObj):
        self.instlObj = instlObj
        self.copy_tool = None
        self.dl_tool = None
        self.num_items_for_progress_report = 0
        self.progress_staccato_period = int(var_list.resolve("$(PROGRESS_STACCATO_PERIOD)"))
        self.progress_staccato_count = 0

    def DefaultCopyToolName(self, target_os):
        retVal = None
        if target_os == "Win":
            retVal = "robocopy"
        elif target_os == "Mac":
            retVal = "rsync"
        elif target_os == 'Linux':
            retVal = "rsync"
        else:
            raise ValueError(target_os, "has no valid default copy tool")
        return retVal

    @abc.abstractmethod
    def init_download_tool(self):
        """ platform specific initialization of the download tool object.
            Can be done only after the definitions for index have been read."""
        pass

    def init_copy_tool(self):
        copy_tool_name = self.DefaultCopyToolName(var_list.resolve("$(__CURRENT_OS__)")) # copy instructions are always produced for the current os
        if "COPY_TOOL" in var_list:
            copy_tool_name = var_list.resolve("$(COPY_TOOL)")
        self.use_copy_tool(copy_tool_name)

    @abc.abstractmethod
    def get_install_instructions_prefix(self):
        """ platform specific """
        pass

    @abc.abstractmethod
    def get_install_instructions_postfix(self):
        """ platform specific last lines of the install script """
        pass

    @abc.abstractmethod
    def mkdir(self, directory):
        """ platform specific mkdir """
        pass

    def mkdir_with_owner(self, directory):
        return self.mkdir(directory)

    @abc.abstractmethod
    def cd(self, directory):
        """ platform specific cd """
        pass

    @abc.abstractmethod
    def pushd(self, directory):
        pass

    @abc.abstractmethod
    def popd(self):
        pass

    @abc.abstractmethod
    def save_dir(self, var_name):
        """ platform specific save current dir """
        pass

    @abc.abstractmethod
    def restore_dir(self, var_name):
        """ platform specific restore current dir """
        pass

    @abc.abstractmethod
    def rmdir(self, directory, recursive=False):
        """ platform specific rmdir """
        pass

    @abc.abstractmethod
    def rmfile(self, file):
        """ platform specific rm file """
        pass

    def new_line(self):
        return "" # empty string because write_batch_file adds \n to each line

    def progress(self, msg, num_items = 0):
        self.num_items_for_progress_report += num_items+1
        prog_msg = "Progress: {} of $(TOTAL_ITEMS_FOR_PROGRESS_REPORT); ".format(str(self.num_items_for_progress_report)) + msg
        return self.echo(prog_msg)

    def progress_staccato(self, msg):
        retVal = ()
        self.progress_staccato_count = (self.progress_staccato_count + 1) % self.progress_staccato_period
        if self.progress_staccato_count == 0:
            prog_instruction = self.progress(msg)
            retVal = prog_instruction
        return retVal

    @abc.abstractmethod
    def get_svn_folder_cleanup_instructions(self):
        """ platform specific cleanup of svn locks """
        pass

    @abc.abstractmethod
    def var_assign(self, identifier, value, comment=None):
        pass

    @abc.abstractmethod
    def echo(self, message):
        pass

    @abc.abstractmethod
    def remark(self, remark):
        pass

    @abc.abstractmethod
    def use_copy_tool(self, tool):
        pass

    @abc.abstractmethod
    def copy_file_to_file(self, src_file, trg_file):
        """ Copy src_file to trg_file.
            Example: create_copy_file_to_file("a.txt", "/d/c/bt.txt") copies
            the file a.txt into "/d/c/bt.txt".
        """
        pass

    def svn_add_item(self, item_path):
        svn_command = " ".join( ("$(SVN_CLIENT_PATH)", "add", '"'+item_path+'"') )
        return svn_command

    def svn_remove_item(self, item_path):
        svn_command = " ".join( ("$(SVN_CLIENT_PATH)", "rm", "--force", '"'+item_path+'"') )
        return svn_command

    @abc.abstractmethod
    def check_checksum_for_file(self, file, checksum):
        pass

    def check_checksum_for_folder(self, info_map_file):
        check_checksum_for_folder_command = " ".join( (self.run_instl(),
                                                    "check-checksum",
                                                    "--in", quoteme_double(info_map_file),
                                                    "--start-progress", str(self.num_items_for_progress_report),
                                                    "--total-progress", "$(TOTAL_ITEMS_FOR_PROGRESS_REPORT)",
                                                    ) )
        return check_checksum_for_folder_command

    def create_folders(self, info_map_file):
        create_folders_command = " ".join( (self.run_instl(),
                                                    "create-folders",
                                                    "--in", quoteme_double(info_map_file),
                                                    "--start-progress", str(self.num_items_for_progress_report),
                                                    "--total-progress", "$(TOTAL_ITEMS_FOR_PROGRESS_REPORT)",
                                                    ) )
        return create_folders_command

    def set_exec_for_folder(self, info_map_file):
        set_exec_for_folder_command = " ".join( (self.run_instl(),
                                                    "set-exec",
                                                    "--in", quoteme_double(info_map_file),
                                                    "--start-progress", str(self.num_items_for_progress_report),
                                                    "--total-progress", "$(TOTAL_ITEMS_FOR_PROGRESS_REPORT)",
                                                    ) )
        return set_exec_for_folder_command

    @abc.abstractmethod
    def tar(self, to_tar_name):
        pass

    @abc.abstractmethod
    def unwtar_file(self, filepath):
        pass

    def unwtar_current_folder(self):
        unwtar_command = " ".join( (self.instlObj.platform_helper.run_instl(),
                                                    "unwtar",
                                                    "--start-progress", str(self.num_items_for_progress_report),
                                                    "--total-progress", "$(TOTAL_ITEMS_FOR_PROGRESS_REPORT)",
                                                    ) )
        return unwtar_command

    @abc.abstractmethod
    def wait_for_child_processes(self):
        pass

    @abc.abstractmethod
    def chmod(self, new_mode, filepath):
        pass

    @abc.abstractmethod
    def make_executable(self, filepath):
        pass

    @abc.abstractmethod
    def unlock(self, filepath, recursive=False):
        """ Remove the system's read-only flag, this is different from permissions.
            For changing permissions use chmod.
        """
        pass

    @abc.abstractmethod
    def touch(self, filepath):
        pass

    def run_instl(self):
        return '\"$(__INSTL_EXE_PATH__)\"'

    @abc.abstractmethod
    def append_file_to_file(self, source_file, target_file):
        pass

def PlatformSpecificHelperFactory(in_os, instlObj):
    retVal = None
    if in_os == "Mac":
        import platformSpecificHelper_Mac
        retVal = platformSpecificHelper_Mac.PlatformSpecificHelperMac(instlObj)
    elif in_os == "Win":
        import platformSpecificHelper_Win
        retVal = platformSpecificHelper_Win.PlatformSpecificHelperWin(instlObj)
    elif in_os == "Linux":
        import platformSpecificHelper_Linux
        retVal = platformSpecificHelper_Linux.PlatformSpecificHelperLinux(instlObj)
    else:
        raise ValueError(in_os, "has no PlatformSpecificHelper")
    return retVal

class DownloadToolBase(object):
    """ Create download commands. Each function should be overridden to implement the download
        on specific platform using a specific copying tool. All functions return
        a list of commands, even if there is only one. This will allow to return
        multiple commands if needed.
    """
    curl_write_out_str = r'%{url_effective}, %{size_download} bytes, %{time_total} sec., %{speed_download} bps.\n'
    # for debugging:
    curl_extra_write_out_str = r'    num_connects:%{num_connects}, time_namelookup: %{time_namelookup}, time_connect: %{time_connect}, time_pretransfer: %{time_pretransfer}, time_redirect: %{time_redirect}, time_starttransfer: %{time_starttransfer}\n\n'

    __metaclass__ = abc.ABCMeta

    def __init__(self, platform_helper):
        self.platform_helper = platform_helper
        self.urls_to_download = list()

    @abc.abstractmethod
    def download_url_to_file(self, src_url, trg_file):
        pass

    def add_download_url(self, url, path):
        self.urls_to_download.append( (urllib.quote(url, "$()/:"), path) )

    def get_num_urls_to_download(self):
        return len(self.urls_to_download)

    def download_from_config_file(self, config_file):
        pass

    @abc.abstractmethod
    def download_from_config_files(self, config_file):
        pass
