#!/usr/bin/env python2.7
from __future__ import print_function

"""
    class InstallItem hold information about how to install one or more install_sources.
    information include:
        iid - must be unique amongst all InstallItems.
        name - description for log and errors messages has no bering on the installation.
        guid - a standard 36 character guid. Can be used as additional identification.
        Several iids can share the same guid.
        remark - remarks for human consumption has no bering on the installation.
        description - auto generated, usually the file and line from which the item was read.
        inherit - iids of other InstallItems to inherit from.
        These fields appear once for each InstallItem.
    Further fields can be be found in a common section or in a section for specific OS:
        install_sources - install_sources to install.
        install_folders - folders to install the install_sources to.
        depends - iids of other InstallItems that must be installed before the current item.
        actions - actions to preform. These actions are further divided into:
            folder_in - actions to preform before installing to each folder in install_folders section.
                        if several InstallItems have the same actions for the folder, each action
                        will be preformed only once.
            folder_out - actions to preform after installing to each folder in install_folders section.
                        if several InstallItems have the same actions for the folder, each action
                        will be preformed only once.
            before -    actions to preform before installing the install_sources in each folder.
            after -    actions to preform after installing the install_sources in each folder.
    Except iid field, all fields are optional.

    Example in Yaml:

    test:
        name: test
        guid: f01f84d6-ad21-11e0-822a-b7fd7bebd530
        remarks: testing, testing 1, 2, 3
        description: index.txt line 1245
        install_sources:
            - Plugins/test_1
            - Plugins/test_2
        install_folders:
            - test_target_folder_1
            - test_target_folder_2
        actions:
            folder_in:
                - action when entering folder
            before:
                - action before item
            after:
                - action after item
            folder_out:
                - action when leaving folder
"""

from collections import OrderedDict, defaultdict

import sys
sys.path.append("..")
from aYaml import augmentedYaml
from pyinstl.utils import *
from pyinstl.configVarList import ConfigVarList
from configVarStack import var_stack as var_list

current_os_names = get_current_os_names()
os_family_name = current_os_names[0]

def read_index_from_yaml(all_items_node):
    retVal = dict()
    for IID in all_items_node.iterkeys():
        if IID in retVal:
            pass #print(IID, "already in all_items_node")
        else:
            # print(IID, "not in all_items_node")
            item = InstallItem()
            item.read_from_yaml_by_idd(IID, all_items_node)
            retVal[IID] = item
    return retVal


class InstallItem(object):
    __slots__ = ('iid', 'name', 'guid',
                'remark', "description", 'inherit',
                '__set_for_os', '__items', '__resolved_inherit',
                'var_list')
    os_names = ('common', 'Mac', 'Mac32', 'Mac64', 'Win', 'Win32', 'Win64')
    item_types = ('install_sources', 'install_folders', 'depends', 'actions')
    action_types = ('copy_in', 'folder_in', 'before', 'after', 'folder_out', 'copy_out')
    file_types = ('!dir_cont', '!files', '!file', '!dir')
    resolve_inheritance_stack = list()
    _get_for_os = [os_names[0]] # _get_for_os is a class member since we usually want to get for same oses for all InstallItems

    @staticmethod
    def create_items_section():
        retVal = defaultdict(unique_list)
        return retVal

    @staticmethod
    def merge_item_sections(this_items, the_other_items):
        common_items = set(this_items.keys() + the_other_items.keys())
        try:
            for item in common_items:
                this_items[item].extend(the_other_items[item])
        except TypeError:
            print("TypeError for", item)
            raise

    @staticmethod
    def begin_get_for_all_oses():
        """ adds all known os names to the list of os that will influence all get functions
            such as depend_list, source_list etc.
            This is a static method so it will influence all InstallItem objects.
            This method is useful in code that does reporting or analyzing, where
            there is need to have access to all oses not just the current or target os.
        """
        InstallItem._get_for_os = []
        InstallItem._get_for_os.extend(InstallItem.os_names)

    @staticmethod
    def reset_get_for_all_oses():
        """ resets the list of os that will influence all get functions
            such as depend_list, source_list etc.
            This is a static method so it will influence all InstallItem objects.
            This method is useful in code that does reporting or analyzing, where
            there is need to have access to all oses not just the current or target os.
        """
        InstallItem._get_for_os = [InstallItem.os_names[0]]

    @staticmethod
    def begin_get_for_specific_os(for_os):
        """ adds another os name to the list of os that will influence all get functions
            such as depend_list, source_list etc.
            This is a static method so it will influence all InstallItem objects.
        """
        InstallItem._get_for_os.append(for_os)

    @staticmethod
    def end_get_for_specific_os():
        """ removed the last added os name to the list of os that will influence all get functions
            such as depend_list, source_list etc.
             This is a static method so it will influence all InstallItem objects.
        """
        InstallItem._get_for_os.pop()

    def merge_all_item_sections(self, otherInstallItem):
        for os_ in InstallItem.os_names:
            InstallItem.merge_item_sections(self.__items[os_], otherInstallItem.__items[os_])

    def __init__(self):
        self.__resolved_inherit = False
        self.iid = None
        self.name = ""
        self.guid = None
        self.remark = ""
        self.description = ""
        self.inherit = unique_list()
        self.__set_for_os = [InstallItem.os_names[0]] # reading for all platforms ('common') or for which specific platforms ('Mac', 'Win')?
        self.__items = defaultdict(InstallItem.create_items_section)
        self.var_list = None

    def read_from_yaml_by_idd(self, IID, all_items_node):
        my_node = all_items_node[IID]
        self.read_from_yaml(my_node)
        self.iid = IID # restore the IID that might have been overwritten by inheritance
        self.description = str(my_node.start_mark)

    def read_from_yaml(self, my_node):
        if 'inherit' in my_node:
            inherite_node = my_node['inherit']
            for inheritoree in inherite_node:
                self.add_inherit(inheritoree.value)
        if 'name' in my_node:
            self.name = my_node['name'].value
        if 'guid' in my_node:
            self.guid = my_node['guid'].value
        if 'remark' in my_node:
            self.remark = my_node['remark'].value
        if 'install_sources' in my_node:
            for source in my_node['install_sources']:
                self.add_source(source.value, source.tag)
        if 'install_folders' in my_node:
            for folder in my_node['install_folders']:
                self.add_folder(folder.value)
        if 'depends' in my_node:
            for source in my_node['depends']:
                self.add_depend(source.value)
        if 'actions' in my_node:
            self.read_actions(my_node['actions'])
        for os_ in InstallItem.os_names[1:]:
            if os_ in my_node:
                self.begin_set_for_specific_os(os_)
                self.read_from_yaml(my_node[os_])
                self.end_set_for_specific_os()

    def get_var_list(self):
        if self.var_list is None:
            self.var_list = ConfigVarList()
            self.var_list.set_var("iid_name").append(self.name)
            if self.guid:
                self.var_list.set_var("iid_guid").append(self.guid)
            if self.remark:
                self.var_list.set_var("iid_remark").append(self.remark)
            self.var_list.set_var("iid_inherite").extend(self._inherit_list())
            self.var_list.set_var("iid_folder_list").extend(self._folder_list())
            self.var_list.set_var("iid_depend_list").extend(self._depend_list())
            for action_type in self.action_types:
                self.var_list.set_var("iid_action_list_"+action_type).extend(self._action_list(action_type))
            source_vars_obj = self.var_list.set_var("iid_source_var_list")
            source_list = self._source_list()
            for i, source in enumerate(source_list):
                source_var = "iid_source_"+str(i)
                source_vars_obj.append(source_var)
                self.var_list.set_var(source_var).extend(source)
        return self.var_list

    def __enter__(self):
        var_list.push_scope(self.get_var_list())
        return self

    def __exit__(self, etype, value, traceback):
        var_list.pop_scope()

    def begin_set_for_specific_os(self, for_os):
        self.__set_for_os.append(for_os)

    def end_set_for_specific_os(self):
        self.__set_for_os.pop()

    def __add_item_by_os_and_category(self, item_os, item_category, item_value):
        """ Add an item to one of the oses and category e.g.:
            __add_item_by_os_and_category("Win", "install_sources", "x.dll")
            __add_item_by_os_and_category("common", "install_sources", "AudioTrack.bundle")
        """
        self.__items[item_os][item_category].append(item_value)

    def __add_item_to_default_os_by_category(self, item_category, item_value):
       """ Add an item to currently default os and category, e.g.:
            begin_set_for_specific_os("Win")
            __add_item_to_default_os_by_category("install_sources", "x.dll")
            self.end_set_for_specific_os()
            __add_item_to_default_os_by_category("install_sources", "AudioTrack.bundle")

            The default os is the one at the top of the __set_for_os stack. __set_for_os
            starts with "common" as the first o.
        """
       self.__add_item_by_os_and_category(self.__set_for_os[-1], item_category, item_value)

    def __get_item_list_by_os_and_category(self, item_os, item_category):
        retVal = list()
        if item_os in self.__items and item_category in self.__items[item_os]:
            retVal.extend(self.__items[item_os][item_category])
        return retVal

    def __get_item_list_for_default_oses_by_category(self, item_category):
        retVal = unique_list()
        for os in InstallItem._get_for_os:
            retVal.extend(self.__get_item_list_by_os_and_category(os, item_category))
        return retVal

    def add_inherit(self, inherit_idd):
        self.inherit.append(inherit_idd)

    def _inherit_list(self):
        retVal = self.inherit
        return retVal

    def add_source(self, new_source, file_type='!dir'):
        if file_type not in InstallItem.file_types:
            file_type = '!dir'
        self.__add_item_to_default_os_by_category('install_sources', (new_source, file_type, self.__set_for_os[-1]) )

    def _source_list(self):
        return self.__get_item_list_for_default_oses_by_category('install_sources')

    def add_folder(self, new_folder):
        self.__add_item_to_default_os_by_category('install_folders', new_folder )

    def _folder_list(self):
        return self.__get_item_list_for_default_oses_by_category('install_folders')

    def add_depend(self, new_depend):
        self.__add_item_to_default_os_by_category('depends', new_depend )

    def _depend_list(self):
        return self.__get_item_list_for_default_oses_by_category('depends')

    def add_action(self, action_type, new_action):
        if action_type not in InstallItem.action_types:
            raise KeyError("actions type must be one of: "+str(InstallItem.action_types)+" not "+action_type)
        self.__add_item_to_default_os_by_category(action_type, new_action)

    def read_actions(self, action_nodes):
        for action_type, new_actions in action_nodes:
            for action in new_actions:
                self.add_action(action_type, action.value)

    def _action_list(self, action_type):
        if action_type not in InstallItem.action_types:
            raise KeyError("actions type must be one of: "+str(InstallItem.action_types)+" not "+action_type)
        return self.__get_item_list_for_default_oses_by_category(action_type)

    def all_action_list(self):
        """ Get a list of all types of actions, can be used to find how many actions there are.
        """
        retVal = list()
        for action_type in InstallItem.action_types:
          retVal.extend(self.__get_item_list_for_default_oses_by_category(action_type))
        return retVal

    def get_recursive_depends(self, items_map, out_set, orphan_set):
        if self.iid not in out_set:
            out_set.append(self.iid)
            #print("get_recursive_depends: added", self.iid)
            for depend in self._depend_list():
                #print("get_recursive_depends:", self.iid, "depends on", depend)
                if depend not in out_set: # avoid cycles, save time
                    try:
                        if guid_re.match(depend): # if it's a guid translate to iid's
                            dependees = iids_from_guid(items_map, depend)
                        else:
                            dependees = [depend]
                        for dependee in dependees:
                            items_map[dependee].get_recursive_depends(items_map, out_set, orphan_set)
                    except KeyError:
                        orphan_set.append(depend)
        #else:
        #    print("get_recursive_depends: already added", self.iid)


    def repr_for_yaml_items(self, for_which_os):
        retVal = None
        if self.__items[for_which_os]:
            retVal = OrderedDict()
            if self.__items[for_which_os]['install_sources']:
                source_list = list()
                for source in self.__items[for_which_os]['install_sources']:
                    if source[1] != '!dir':
                        source_list.append(augmentedYaml.YamlDumpWrap(value=source[0], tag=source[1]))
                    else:
                        source_list.append(source[0])
                retVal['install_sources'] = source_list
            if self.__items[for_which_os]['install_folders']:
                retVal['install_folders'] = list(self.__items[for_which_os]['install_folders'])
            if self.__items[for_which_os]['depends']:
                retVal['depends'] = list(self.__items[for_which_os]['depends'])
            for action in InstallItem.action_types:
                if action in self.__items[for_which_os] and self.__items[for_which_os][action]:
                    actions_dict = retVal.setdefault('actions', OrderedDict())
                    actions_dict[action] = list(self.__items[for_which_os][action])
        return retVal

    def repr_for_yaml(self):
        retVal = OrderedDict()
        retVal['name'] = self.name
        if self.guid:
            retVal['guid'] = self.guid
        if self.remark:
            retVal['remark'] = self.remark
        if self.inherit:
            retVal['inherit'] = self._inherit_list()

        common_items = self.repr_for_yaml_items(InstallItem.os_names[0])
        if common_items:
            retVal.update(common_items)
        for os_ in InstallItem.os_names[1:]:
            os_items = self.repr_for_yaml_items(os_)
            if os_items:
                retVal[os_] = os_items

        return retVal

    def merge_from_another_InstallItem(self, otherInstallItem):
        """ merge the contents of another InstallItem """
        # self.iid = iid is not merged
        # self.name = name is not merged
        # self.guid = guid is not merged
        # name of the other item is added to the remark
        if not self.remark:
            self.remark = self.name
        self.remark += ", "+otherInstallItem.name
        self.inherit.update(otherInstallItem.inherit)
        self.merge_all_item_sections(otherInstallItem)

    def resolve_inheritance(self, InstallItemsDict):
        if not self.__resolved_inherit:
            if self.iid in self.resolve_inheritance_stack:
                raise Exception("circular resolve_inheritance of "+self.iid)
            self.resolve_inheritance_stack.append(self.iid)
            for ancestor in self._inherit_list():
                if ancestor not in InstallItemsDict:
                    raise KeyError(self.iid+" inherites from "+ancestor+" which is not in InstallItemsDict")
                ancestor_item = InstallItemsDict[ancestor]
                ancestor_item.resolve_inheritance(InstallItemsDict)
                self.merge_all_item_sections(ancestor_item)
                self.remark += ", "+ancestor_item.name+", "+ancestor_item.remark
            self.resolve_inheritance_stack.pop()


"""
            if 'inherit' in my_node:
                for inheritIDD in inherite_node:
                    try:
                        self.read_from_yaml_by_idd(inheritIDD.value, all_items_node)
                    except KeyError as ke:
                        missingIDDMessage = "While reading "+IID+", Inheritance IID '"+ke.message+" " +inherite_node.start_mark
                        raise KeyError(missingIDDMessage)
"""


def guid_list(items_map):
    retVal = unique_list()
    retVal.extend(filter(bool, [install_def.guid for install_def in items_map.values()]))
    return retVal


def iids_from_guid(items_map, guid):
    retVal = list()
    for iid, install_def in items_map.iteritems():
        if install_def.guid == guid:
            retVal.append(iid)
    return retVal
