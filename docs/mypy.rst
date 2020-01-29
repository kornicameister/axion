*****
mypy plugin
*****

*axion* ships with `mypy <https://github.com/python/mypy>`_ plugin that allows to
peform static analysis of **API** handlers against any specification available in project.

Usage
#####

In order to use *axion* static analysis you have to mark an endpoint with appropriate decorator.
That is a necessity because otherwise `mypy` ignores API handlers.
