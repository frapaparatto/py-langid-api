# Python Type Hints

*Notes on Python's type hint system, focused on the parts that came up while typing FastAPI exception handlers: what an annotation actually claims, and the two reasons a "more specific" type can be rejected where a broader one is expected (**contravariance** and **invariance**).*


## What a type hint is

A type hint is a **claim checked by a static type checker** (Pyright, mypy), not by Python at runtime. Python itself ignores annotations during execution; they exist for tooling and for human readers. So a type error is a static-analysis complaint about a contract, not a runtime crash. Code can be type-incorrect and still run perfectly, which is exactly the situation with exception handlers.


## What an annotation on a parameter claims

Writing `def f(x: SomeType)` is a **promise about what the function accepts**: "this function knows how to handle a `SomeType`, or anything more specific than it (a subclass)."

The "or anything more specific" part matters. A function annotated `def f(x: Animal)` accepts a `Dog`, because a `Dog` is an `Animal`. This feels natural and is the source of the confusion that follows.


## Subtyping: the basic rule

A subtype can stand in for its supertype **as a value**. If `Dog` subclasses `Animal`, a `Dog` value is usable anywhere an `Animal` value is expected. This is **covariant** intuition, and it is correct for plain values and for return types.

The confusion starts when this intuition is applied to **function parameters** and to **mutable containers**, where it does not hold.


## Contravariance: why function parameters reverse

When you ask "can function A be used where function B is expected," the parameters compare in **reverse**. This is **contravariance**.

Concretely: a slot expects a function that accepts `Animal`. Can a function that accepts only `Dog` fill it?

- Intuition says yes (a `Dog` is an `Animal`).
- The answer is **no**, and the reasoning is safety.

The slot promises "I might pass you any `Animal`." A function that only handles `Dog` would break if handed a `Cat`. So a function is only safe to use in that slot if it accepts **the same type or a broader one**, never a narrower one.

- Slot wants a function accepting `Animal`.
- Function accepting `Animal` is fine (same).
- Function accepting `LivingThing` (broader) is fine.
- Function accepting `Dog` (narrower) is a type error.

**The job-posting analogy.** The slot is a posting: "must repair any vehicle." A mechanic who only repairs one specific car cannot take it, the job might hand them a truck. A mechanic who repairs any vehicle qualifies. The job demands breadth; a narrow specialist does not satisfy it.

**Where this hit the project.** A FastAPI exception handler slot expects a function accepting `Exception`. A handler annotated `exc: ModelUnavailableError` (narrower) is rejected by Pyright on contravariance. The fix is to widen the handler's parameter to the type the slot expects (`Exception`) and narrow inside the body when specific attributes are needed.


## Invariance: why mutable containers reject substitution entirely

A separate rule applies to mutable containers like `dict` and `list`. They are **invariant** in their element types: `dict[Narrow, V]` is **not** interchangeable with `dict[Wide, V]`, in either direction, even though `Narrow` is a subtype of `Wide`.

The reasoning is mutability. Suppose a function expects `dict[int | type[Exception], Handler]` and you pass a `dict[type[SpecificError], Handler]`. Inside the function, the code is allowed to insert an `int` key (the parameter type permits it). But the dict you actually passed cannot hold an `int` key. So allowing the substitution would let the function corrupt the dict. To prevent that, the checker forbids the substitution: the two dict types must match exactly.

- A `dict[type[SpecificError], H]` is not a `dict[type[Exception], H]`.
- Even though `SpecificError` is a subtype of `Exception`.
- Because the dict is mutable, and the wider-typed slot could mutate it in ways the narrower dict cannot hold.

**Where this hit the project.** A dict literal `{RequestValidationError: ..., LanguagePredictionError: ...}` is **inferred** by Pyright as a narrow type, roughly `dict[type[RequestValidationError | LanguagePredictionError], ...]`. Passing it to a parameter typed `dict[int | type[Exception], ExceptionHandler]` fails on invariance. The fix is to **annotate the dict literal explicitly** so its declared type matches the parameter:

```python
exception_handlers: dict[int | type[Exception], ExceptionHandler] = {
    RequestValidationError: validation_exception_handler,
    LanguagePredictionError: language_prediction_error_handler,
}
```

With the annotation, both sides are the same declared type, the literal's contents are still valid (the keys are `type[Exception]`, the values are handlers), and the invariance problem disappears.


## Contravariance vs invariance, side by side

Both reject a "more specific" type where a broader one is expected, but for different reasons:

- **Contravariance** is about **function parameters**. A function accepting a narrow type cannot fill a slot expecting a broad type, because the slot might pass something the narrow function cannot handle. The direction is reversed: broader parameters are the safe ones.
- **Invariance** is about **mutable containers**. A container of a narrow type cannot be used where a container of a broad type is expected (and vice versa), because mutation through the wider-typed reference could violate the narrower container. The types must match exactly.

The shared lesson: subtype-substitution intuition (a `Dog` works where an `Animal` is wanted) is correct for plain values and return types, but breaks for function parameters (reversed) and mutable containers (forbidden).


## Practical fixes that came up

- **Widen a function parameter, narrow inside.** When a handler must satisfy a broad slot but needs a specific type's attributes, annotate the parameter as the broad type and use `assert isinstance(x, Specific)` at the top of the body. The assert both satisfies the checker (it narrows the type for the rest of the function) and acts as a runtime sanity check.
- **Annotate container literals explicitly.** When passing a dict or list literal to a function expecting a wider element type, annotate the literal at creation so its declared type matches the parameter, rather than letting the checker infer a narrower type.


## The runtime reality

None of these are runtime errors. The code runs correctly regardless: FastAPI dispatches each exception to the right handler and passes exactly the expected type. The type checker is enforcing contracts statically, and it cannot see the runtime guarantees that make the code safe. The fixes make the static contract honest, they do not change behavior.
