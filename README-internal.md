# Junction SDK

An SDK for the Junction API.\
...\
... placeholder for SDK overview...\
...

## Documentation

The documentation is automatically generated from the code using 'Sphinx' and 'autoapi'.

## Command to create the documentation

- Go to the directory containing the top level python files (for eg. \python_sdk\junction).
- Run the command: sphinx-build -b html ..\docs\source ..\docs\build\html
(sphinx-build -b {{format of the documentation files}} {{location of the configuration files}}  {{{location where to generate the documentation files}})

or

- Go to the dir containing the make file and
- Run the command : make html\
(The location of configuration and output would be taken from the make file).

To update the documentation, you can modify the .py file and add appropriate docstrings to the functions, classes, or methods you wish to document. Once you've made these changes, simply regenerate the documentation by running the command:\

```code
make html
```

This will rebuild the HTML documentation, and your updates will be reflected accordingly.
The sample changes are in 'client.py'->class JunctionClient:

## Directory and File Descriptions

### First level directory

**docs/**:

- Purpose: Root directory for documentation project.
- Contains:\
   **Makefile**: For building the documentation on Unix-like systems.\
   **make.bat**: For building the documentation on Windows systems.\
   **source/**\
   **build/**\
   _\_static/_ (optional): Directory for static assets like CSS files, images, and JavaScript.\
   _\_templates/_(optional): Directory for custom Sphinx HTML templates.\

### Second level directories

**source/**:

- Purpose: Source files for the documentation.
- Contains:\
   **conf.py**: Configuration file for Sphinx, containing settings and extensions. _Most important configuration file_\
   **index.rst**: Main entry point for the documentation. Typically includes the table of contents. This is the main index page layout.\
   _usage.rst_: Example of a documentation file that describes usage. (optional)\
   _api.rst_: Example of a documentation file that describes the API. (optional)

```text
Note:
Customise the index.rst to detail the documentation as per your requirements.
```

**build/**: Directory where the built documentation files are placed (HTML, PDF, etc.). This is the dir that is generated with the docs. This dir name is as specified in the make file. Used in the sphinx-build command.

- Purpose: Contains the output from the Sphinx build process.
- Contains:\
   html/: HTML output files (website). for eg. index.html
  - Contains: \_static/: Store static files that are included in the documentation.

## How to ignore submodules

If you're using autoapi.extension, you can use the autoapi_ignore option in the conf.py file to exclude certain submodules from being processed:

```code
autoapi_ignore = ["*conf.py", "*booking.py", "*submodule.py", "*typedefs.py"]
```

## How to ignore special or private members

Use _autodoc_default_options_ to Exclude Members.\
You can use the autodoc_default_options configuration to exclude certain members by default (like submodules). For example, if you don't want submodules to be listed in the class and module documentation, you could use:

```code
autodoc_default_options = {
    'members': True,
    'undoc-members': False,
    'private-members': False,
    'special-members': False,
    'inherited-members': False,
    'show-inheritance': False,
    'exclude-members': '**weakref**',  # Or specify submodules or members to exclude
}
```

Similarly you could also use '**autoapi_options**'.
