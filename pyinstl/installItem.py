#!/usr/local/bin/python2.7

from __future__ import print_function

import sys
import platform
import yaml
from collections import OrderedDict, defaultdict

sys.path.append("..")
from aYaml import augmentedYaml

current_os = platform.system()
if current_os == 'Darwin':
    current_os = 'mac';
elif current_os == 'Windows':
    current_os = 'win';

def read_index_from_yaml(all_items_node):
    retVal = dict() #OrderedDict()
    for GUID in all_items_node.iterkeys():
        if GUID in retVal:
            pass#print(GUID, "already in all_items_node")
        else:
            #print(GUID, "not in all_items_node")
            item = InstallItem()
            item.read_from_yaml_by_guid(GUID, all_items_node)
            retVal[GUID] = item
    return retVal

class InstallItem(object):
    __slots__ = ("guid", "name", "license",
                "remark", "description", "__items")
    action_types = ("before", "after", "folder_in", "folder_out")
    def __init__(self):
        self.guid = None
        self.name = None
        self.license = None
        self.remark = None
        self.description = ""
        self.__items = {"sources": list(),
                      "folders": list(),
                      "depends": list(),
                      "actions": defaultdict(list)
                      }

    def read_from_yaml_by_guid(self, GUID, all_items_node):
        my_node = all_items_node[GUID]
        self.read_from_yaml(my_node, all_items_node)
        self.guid = GUID # restore the GUID that might have been overwritten by inheritance
        self.description = str(my_node.start_mark)

    def read_from_yaml(self, my_node, all_items_node):
        if "inherit" in my_node:
            for inheriteGUID in my_node["inherit"]:
                try:
                    self.read_from_yaml_by_guid(inheriteGUID.value, all_items_node)
                except KeyError as ke:
                    missingGUIDMessage = "While reading "+GUID+", Inheritance GUID '"+ke.message+" " +my_node["inherit"].start_mark
                    raise KeyError(missingGUIDMessage)
        if "name" in my_node:
            self.name = my_node["name"].value
        if "license" in my_node:
            self.license = my_node["license"].value
        if "remark" in my_node:
            self.remark = my_node["remark"].value
        if "install_sources" in my_node:
            for source in my_node["install_sources"]:
                self.add_source(source.value, source.tag)
        if "install_folders" in my_node:
            for folder in my_node["install_folders"]:
                self.add_folder(folder.value)
        if "depends" in my_node:
            for source in my_node["depends"]:
                self.add_depend(source.value)
        if "actions" in my_node:
            self.read_actions(my_node["actions"])
        if current_os in my_node:
            self.read_from_yaml(my_node[current_os], all_items_node)

    def add_source(self, new_source, type='!dir'):
        if new_source not in self.__items["sources"]:
            self.__items["sources"].append( (new_source, type) )

    def source_list(self):
        return self.__items["sources"]

    def add_folder(self, new_folder):
        if new_folder not in self.__items["folders"]:
            self.__items["folders"].append(new_folder)

    def folder_list(self):
        return self.__items["folders"]

    def add_depend(self, new_depend):
        if new_depend not in self.__items["depends"]:
            self.__items["depends"].append(new_depend)

    def depend_list(self):
        return self.__items["depends"]

    def add_action(self, where, action):
        if where in action_types:
            self.__items["actions"][where].append(action)
        else:
            raise KeyError("actions type must be one of: "+str(action_types)+" not "+where)

    def read_actions(self, action_nodes):
        for action_pair in action_nodes:
            if action_pair[0] in action_types:
                for action in action_pair[1]:
                    self.__items["actions"][action_pair[0]].append(action.value)
            else:
                raise KeyError("actions type must be one of: "+str(action_types)+" not "+action_pair[0])

    def action_list(self, which):
        if which not in action_types
            raise KeyError("actions type must be one of: "+str(action_types)+" not "+which)
        return self.__items["actions"][which]

    def get_recursive_depends(self, items_map, out_set, orphan_set):
        if self.guid not in out_set:
            out_set.add(self.guid)
            for depend in self.__items["depends"]:
                if depend not in out_set: # avoid cycles
                    try:
                        items_map[depend].get_recursive_depends(items_map, out_set, orphan_set)
                    except KeyError:
                        orphan_set.add(depend)

    def repr_for_yaml(self):
        retVal = OrderedDict()
        retVal["name"] = self.name
        if self.license:
            retVal["license"] = self.license
        if self.remark:
            retVal["remark"] = self.remark
        if self.__items["sources"]:
            retVal["install_sources"] = [source[0] for source in self.__items["sources"]]
        if self.__items["folders"]:
            retVal["install_folders"] = self.__items["folders"]
        if self.__items["actions"]:
            retVal["actions"] = dict(self.__items["actions"])
        if self.__items["depends"]:
            retVal["depends"] = self.__items["depends"]
        return retVal
