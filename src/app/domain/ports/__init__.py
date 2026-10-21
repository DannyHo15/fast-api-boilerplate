"""Ports (interface contracts) implemented by the infrastructure layer.

Using `typing.Protocol` gives us structural subtyping: any class that
implements the methods satisfies the port, which makes unit testing with
in-memory fakes trivial.
"""
