Author: Shawn

We're working on programmer, an interactive command line tool that you can chat with to write programs

programmer uses the weave library to trace trajectories.

weave's core concept is the decorator `weave.op`, which saves Call records into a database. Call records include inputs, output, and other metadata.

```
@weave.op
def add2(a, b):
    return a + b

client = weave.init_trace_local()
add2(2, 3)
add2(5, 6)

for call in client.calls():
    ...
```

Weave also has a concept called objects. To use a weave Object, create a class that inherits from weave.Object, and add annotated type attributes. Objects inherit from pydantic.BaseModel. When a weave.Object descendent is encountered as an input or output of an op call, weave publishes the Object as a top-level record, and stores a ref uri (in the form of weave:///) to the Object record in the Call record.

Here is an Object example:

```
class Point(weave.Object):
    x: float
    y: float

@weave.op
def add_points(p1: Point, p2: Point):
    return Point(x=p1.x + p2.x, y=p1.y + p2.y)

...
```

Objects may be nested inside each-other.

In programmer we've built a new weave query interface in `programmer/weave_next/weave_query.py`.

You can use weave_query.py's functions to resolve calls with Object refs, which may contain other refs, but its a bit cumbersome at the moment.

The goal of this project is to improve the interface, into a single calls interface that allows us to fetch calls and expand refs and nested refs (recursively) in one-shot. Something like this:

```
calls_query = calls('my_op', expand_refs=['output', 'output.field_a'])
calls_df = calls_query.to_pandas()
```

There are not currently tests for weave_query.py, and we want to make sure we don't break existing behaviors. So this project should proceed in two phases:

1) write comprehensive unit tests for weave_query.py, especially ensuring we cover expanding refs in calls and expanding refs in those resulting objects
2) implement the interface improvements above. This will require first writing new unit tests to cover the new functionality.

For unit testing against weave, we have a fixture in programmer/tests/conftest.py that constructs a weave client against an in memory database. I haven't tested the fixture yet, so it may need to be updated.


Design doc questions and answers
--------------------------------
programmer asked questions, Shawn answered

- Q: Are there any specific edge cases or scenarios that are of particular concern when expanding refs that should be covered in the tests?
  - A: I'm not aware of additional edge cases not covered in the code, but there may be!
- Q: Is there any existing documentation or notes on the current limitations or known issues with the weave query interface?
  - A: No other existing docs.
- Q: Should the improved interface support any additional functionality beyond what's described (e.g., filtering, sorting)?
  - A: No additional functionality.
- Q: Are there any performance considerations or constraints we should be aware of when expanding refs recursively?
  - A: Refs should be expanded in batches. Currently _server_call_pages() fetches calls in pages. I think we should expand refs per page as well.
