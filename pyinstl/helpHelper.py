#!/usr/bin/env python2.7
from __future__ import print_function

import fnmatch
import yaml
from pyinstl.utils import *

from configVarStack import var_stack as var_list

# This method will be used to patch instlObj to read !help yaml documents
def read_help_node(instlObj, a_node):
    instlObj.helpHelper.read_help_node(a_node)

class HelpItem(object):
    def __init__(self, topic, name):
        self.topic = topic
        self.name = name
        self.texts = dict()

    def read_from_yaml(self, item_value_node):
        for value_name, value_text in item_value_node:
            self.texts[value_name] = var_list.resolve(value_text.value)

    def short_text(self):
        return self.texts.get("short", "?")

    def long_text(self):
        return self.texts.get("long", "")

class HelpHelper(object):
    def __init__(self, instlObj):
        self.help_items = dict()
        self.instlObj = instlObj
        self.instlObj.helpHelper = self # make HelpHelper member of instlObj
        instlObj.read_help = read_help_node  # patch instlObj to read help files

    def read_help_node(self, a_node):
        if a_node.isMapping():
            for topic_name, topic_items_node  in a_node:
                var_list.push_scope()
                var_list.set_var("TOPIC_NAME").append(topic_name)
                for item_name, item_value_node  in topic_items_node:
                    var_list.push_scope()
                    var_list.set_var("ITEM_NAME").append(item_name)
                    newItem = HelpItem(topic_name, item_name)
                    newItem.read_from_yaml(item_value_node)
                    self.help_items[item_name] = newItem
                    var_list.pop_scope()
                var_list.pop_scope()

    def topics(self):
        topics = set()
        for item in self.help_items.values():
            topics.add(item.topic)
        return topics

    def topic_summery(self, topic):
        retVal = "no such topic: "+topic
        short_list = list()
        for item in self.help_items.values():
            if item.topic == topic:
                short_list.append( (item.name+":", item.short_text()) )
        short_list.sort()
        if len(short_list) > 0:
            width_list = [0, 0]
            for name, short_text in short_list:
                width_list[0] = max(width_list[0], len(name))
                width_list[1] = max(width_list[1], len(short_text))
            format_list = gen_col_format(width_list)
            retVal = "\n".join(format_list[2].format(name, short) for name, short in short_list)
        return retVal

    def item_help(self, item_name):
        retVal = "no such item: "+item_name
        item = self.help_items.get(item_name)
        if item:
            import textwrap
            long_formated = "\n\n".join([textwrap.fill(line, 80,
                                          replace_whitespace=False,
                                          initial_indent='    ',
                                          subsequent_indent='    ')for line in item.long_text().splitlines()])
            retVal = "\n".join((
                            item.name+": "+item.short_text(),
                            "",
                            long_formated
                            ))
        return retVal

    def defaults_help(self):
        defaults_folder_path = os.path.join(var_list.resolve("$(__INSTL_DATA_FOLDER__)"), "defaults")
        for yaml_file in os.listdir(defaults_folder_path):
            if fnmatch.fnmatch(yaml_file, '*.yaml') and yaml_file != "P4.yaml": # hack to not read the P4 defaults
                self.instlObj.read_yaml_file(os.path.join(defaults_folder_path, yaml_file))
        defaults_list = [("Variable name", "Raw value", "Resolved value"),
                         ("_____________", "_________", "______________")]
        for var in sorted(var_list):
            if not var.startswith("__"):
                cv = var_list.get_configVar_obj(var)
                raw_value = " ".join([value for value in cv])
                resolved_value = var_list.resolve_var(var)
                if raw_value != resolved_value:
                    defaults_list.append( (var, raw_value, resolved_value) )
                else:
                    defaults_list.append( (var, raw_value) )

        col_format = gen_col_format(max_widths(defaults_list))
        for res_line in defaults_list:
            print(col_format[len(res_line)].format(*res_line))

def do_help(subject, help_folder_path, instlObj):
    hh = HelpHelper(instlObj)
    for help_file in os.listdir(help_folder_path):
        if fnmatch.fnmatch(help_file, '*help.yaml'):
            instlObj.read_yaml_file(os.path.join(help_folder_path, help_file))

    if not subject:
        for topic in hh.topics():
            print("instl", "help", "<"+topic+">")
        print("instl", "help", "<defaults>")
    elif subject in hh.topics():
        print(hh.topic_summery(subject))
    else:
        if subject == "defaults":
            hh.defaults_help()
        else:
            print(hh.item_help(subject))
