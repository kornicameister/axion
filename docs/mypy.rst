***********
mypy plugin
***********

*axion* ships with `mypy <https://github.com/python/mypy>`_ plugin that allows to
perform static analysis of **API** handlers against any specification available in project.

Usage
#####

In order to use *axion* static analysis you have to mark an endpoint with appropriate decorator.
That is a necessity because otherwise `mypy` ignores API handlers. In other words your `mypy` configuration
should resemble following ::

    [mypy]
    plugins = axion.mypy

    [axion-mypy]
    oas_directories = ./

Most essential part if not enabling a plugin but pointing at a directory where *axion* should look for
OpenAPI specifications. Once again that is by design. Not to mention that not every `*.yml` is an OAS file.

What it does?
#############

Plugin will do two major things:

1) Confront **API handler** definition against linked OAS definition.
2) Suggest shifting things around if needed.
