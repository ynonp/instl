**instl**: installation without magic
#####################################

.. instl documentation master file, created by
   sphinx-quickstart on Wed Jan  2 12:17:21 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. topic:: What is **instl**?

    **instl** is a cross-platform tool for creating installers.
    Installers created with **instl** can be used online or offline.

    **instl** is written in the python_ programming language but no knowledge of python is
    required in order to create installers or use them.

    **instl** uses SubVersion_ as it's back-end database for storing installation sources.
    Some knowledge SubVersion is required in order to setup an installer.

    **instl** is published as Open Source under BSD license.

    Supported platforms: Mac OS X, Windows, Linux

Contents:

.. toctree::
    :maxdepth: 12
    :numbered:

    overview
    motivation
    expect
    tutorial
    commands
    architecture
    fileformat
    example
    standard_variables
    svn configuration
    online installs
    offline installs
    packaging instl for users
    code
    FAQs



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _python: http://www.python.org/
.. _SubVersion: http://subversion.apache.org/
