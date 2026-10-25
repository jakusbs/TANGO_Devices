"""tango.test_context runs each device server in a child process.  The tests
substitute dependencies by putting fake modules into sys.modules before the
server class is imported (the ZI2 test stubs `zhinst`), which only reaches
the child when it is forked — pin the start method, since Python 3.14
changes the default to forkserver."""
import multiprocessing

try:
    multiprocessing.set_start_method("fork")
except RuntimeError:          # already set by an earlier import
    pass
