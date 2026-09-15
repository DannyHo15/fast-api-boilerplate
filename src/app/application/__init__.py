"""Application layer: use cases orchestrating the domain.

Each use case is a small, focused class with one `execute` method.
Use cases depend on domain ports (interfaces), never on concrete
infrastructure - so they are trivially unit-testable with fakes.
"""
