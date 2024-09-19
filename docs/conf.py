# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys
import re

# Add the path to your SDK source code
sys.path.insert(0, os.path.abspath('../../junction/'))

# Get path for the file containing the version info
init_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                              '../../junction/__init__.py')
def get_version():
    with open(init_file_path, 'r') as version_file:
        # Construct a regex pattern for the version variable passed
        pattern = re.compile(r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]')
        for line in version_file:
            match = pattern.match(line)
            if match:
                return match.group(1)
    raise RuntimeError("Unable to find version string.")
    
# Get the version
version = get_version()

project = 'Junction API SDK'
copyright = '2024, SnowfallTravel'
author = 'SnowfallTravel'
release = version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'autoapi.extension',
]
autoapi_dirs = ['../../junction/']  # Specify the directory where your SDK source code is located
autoapi_generate_api_docs = True
templates_path = ['_templates']
# autoapi_ignore = ["*conf.py", "*booking.py", "*submodule.py", "*typedefs.py"]
autoapi_ignore = ["*conf.py", "*typedefs.py"]

# AutoAPI options to exclude certain members
autoapi_options = [
    "members",
    "undoc-members",            # Include undocumented members
    "show-inheritance",
    "special-members=False",    # Exclude special methods like __init__, __aenter__, etc.
    "private-members=False",    # Exclude private members (those starting with '_')
]

# Custom autodoc options
autodoc_default_options = {
    'members': True,                       # Include public members
    'undoc-members': False,                # Do not include undocumented members
    'private-members': False,              # Exclude members starting with '_'
    'special-members': False,              # Exclude special members (__init__, __aenter__, etc.)
    'exclude-members': '',  # Exclude specific members
}

# Enable autosummary (optional, useful if you want function/class summaries)
# autosummary_generate = True

exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
