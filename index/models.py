from django.db import models

import os
import sys
sys.path.append(os.path.realpath(os.path.join(__file__, "..", "..", "..", "instl")))

import yaml
from pyinstl.utils import *

class InstallSource(models.Model):
   path = models.TextField(unique=True)

class InstallFolder(models.Model):
   path = models.TextField(unique=True)

class Action(models.Model):
   action = models.TextField(unique=True)

class InstlItemModel(models.Model):
    iid = models.CharField("instl id", max_length=128, unique=True)
    guid = models.CharField("guid", max_length=36)
    name = models.CharField("name", max_length=256)
    remark = models.CharField("remark", max_length=256)
    #install_sources = models.ForeignKey(InstallSource)
    #install_folders = models.ForeignKey(InstallFolder)
    #depends = models.ForeignKey('self', related_name=iid)
    #inherit = models.ForeignKey('self', related_name=iid)


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
            print(str(ii))
            django_item = InstlItemModel(iid=ii.iid, guid=ii.guid, name=ii.name, remark=ii.remark)
            django_item.save()
        #print(InstlItemModel.objects.all())
    except yaml.YAMLError as ye:
        raise InstlException(" ".join( ("YAML error while reading file", "'"+file_path+"':\n", str(ye)) ), ye)
    except IOError as ioe:
        raise InstlException(" ".join(("Failed to read file", "'"+file_path+"'", ":")), ioe)

if __name__ == "__main__":
    create_install_items_db("/p4client/ProAudio/dev_install/beanstalk/V9/instl/index.yaml")
