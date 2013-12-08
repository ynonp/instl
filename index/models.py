from django.db import models

import os
import sys
sys.path.append(os.path.realpath(os.path.join(__file__, "..", "..", "..", "instl")))

import yaml
from pyinstl.utils import *
from pyinstl.installItem import InstallItem

class Define(models.Model):
    identifier = models.CharField("identifier", max_length=128, unique=True)
    value = models.TextField()

class InstallFolder(models.Model):
   path = models.TextField(unique=True)

class Action(models.Model):
   action = models.TextField(unique=True)

class InstlItemModel(models.Model):
    iid = models.CharField("instl id", max_length=128, unique=True)
    guid = models.CharField("guid", max_length=36, null=True)
    name = models.CharField("name", max_length=256, null=True)
    remark = models.CharField("remark", max_length=256, null=True)
    #install_sources = models.ForeignKey(InstallSource)
    #install_folders = models.ForeignKey(InstallFolder)
    #depends = models.ForeignKey('self', related_name=iid)
    #inherit = models.ForeignKey('self', related_name=iid)


class InstallSource(models.Model):
    instlItem = models.ForeignKey(InstlItemModel)
    os = models.CharField("os", max_length=6, choices=zip(InstallItem.os_names,InstallItem.os_names), default="common")
    path = models.TextField()

def create_install_items_db(path_to_index):
    from pyinstl.installItem import read_index_from_yaml
    the_dict = None
    try:
        with open_for_read_file_or_url(path_to_index, None) as file_fd:
            for a_node in yaml.compose_all(file_fd):
                if a_node.tag == '!define':
                    pass
                    #self.read_defines(a_node)
                elif a_node.tag == '!index':
                    the_dict = read_index_from_yaml(a_node)
        for ii in the_dict.values():
            #print(ii.repr_for_yaml())
            django_item = InstlItemModel(iid=ii.iid, guid=ii.guid, name=ii.name, remark=ii.remark)
            django_item.save()
            for os_name in ii.os_names:
                ii.implicit_default_os_names = (os_name,)
                for source in ii.source_list():
                    source_item = InstallSource(instlItem=django_item, os=os_name, path=source)
                    source_item.save()
        #print(InstlItemModel.objects.all())
    except yaml.YAMLError as ye:
        raise InstlException(" ".join( ("YAML error while reading file", "'"+file_path+"':\n", str(ye)) ), ye)
    except IOError as ioe:
        raise InstlException(" ".join(("Failed to read file", "'"+file_path+"'", ":")), ioe)

if __name__ == "__main__":
    create_install_items_db("/p4client/ProAudio/dev_install/beanstalk/V9/instl/index.yaml")
