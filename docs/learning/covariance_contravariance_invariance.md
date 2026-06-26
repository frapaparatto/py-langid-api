# Variance: Covariance, Contravariance, Invariance

**Link:** https://youtu.be/FdFBYUQCuHQ?si=uJl1FYy2uOpLsDFc

A cleaned-up, ordered version of the variance explanation, with the intuition that resolves why mutable containers must be invariant.


## The opening puzzle

Can you use a **list of cats** where a **list of animals** is expected?

If all cats are animals, shouldn't a list of cats also be a list of animals? The answer, most of the time, is **no**. The reason is variance, and specifically that `list` is a generic type whose type parameter is **invariant**. The rest of this builds up to why.


## Covariance: the fruit bag

If you ask for a **bag of fruits** and I give you a **bag of apples**, you should be happy. You wanted a bag you can take fruits out of. I gave you a bag you can take apples out of, and since apples are fruits, everything you take out is still a fruit.

I substituted what you asked for with something that **produces a more specific type** (apples instead of fruit). This is **covariance**: substituting toward a more specific type, and it is safe **when the type is used as output** (you only take things out).


## Contravariance: the juicer

If you ask for a machine that **juices oranges**, and I give you a machine that **juices any fruit**, you should be happy. You can still put oranges in, since oranges are fruit, but I have given you a more general machine that accepts any fruit.

I substituted what you asked for with something that **accepts a more general type**. This is **contravariance**: substituting toward a more general type, and it is safe **when the type is used as input** (you only put things in).


## The formal definitions

Variance describes how subtyping of a compound type relates to the subtyping of the type it uses.

- **Covariance:** if `A` is a subtype of `B`, then `Container[A]` is a subtype of `Container[B]`. Same direction. (`A` left, `B` right, on both sides.)
- **Contravariance:** if `A` is a subtype of `B`, then `Container[B]` is a subtype of `Container[A]`. Reversed direction. (`A` left, `B` right becomes `B` left, `A` right.)
- **Invariance:** neither. No substitution in either direction; the types must match exactly.

Reading aid: "X is a subtype of Y" means "X can be used wherever Y is expected" (X is substitutable for Y).

- An apple-producing sequence can be used wherever a fruit-producing sequence is expected. Covariance.
- A general fruit juicer can be used wherever an orange juicer is expected. Contravariance.


## The trap, and how to read the juicer claim correctly (in my own words)

The contravariance claim looks illogical at first because it sounds like it says "general fruit is a subtype of orange," which is backwards. The fix is to **stop considering the relationship between orange and fruit, and consider only the relationship between the juicers.**

Two separate subtype relationships are in play, pointing opposite ways:

- Among the fruits: `Orange` is a subtype of `Fruit` (an orange is a fruit). Normal direction.
- Among the juicers: `FruitJuicer` is a subtype of `OrangeJuicer`. Reversed direction.

The reversal is the whole point of "contra" (against). The claim is never about the fruits; it is about the juicers built on them.

Why the juicers reverse: you **can't** use an orange juicer where someone requires a fruit juicer, because that person expects to make lots of different juices, and a specific (orange-only) juicer can't do it. But you **can** use a fruit juicer where an orange juicer is expected, since it handles oranges and everything else. So the more general the input it accepts, the more places it fits, which makes it the more substitutable one, the subtype.

Restated as a rule for machines (with X a subtype of T):

- If you build a machine that **accepts** type X, you can substitute it with a machine that accepts T (a more general input is safe). You can pass X to a machine that accepts T.
- If you build a machine that **produces** type X, it can't produce T even though X is a subtype of T, so you can't substitute a machine that produces T with one that produces X.

Producing favors the specific (covariant output); accepting favors the general (contravariant input).


## Why invariance: the read-write conflict

This is the core idea, and it resolves why mutable containers are different from functions.

A type parameter is safe to be:

- **covariant only when used as output** (you read/produce from it),
- **contravariant only when used as input** (you write/accept into it).

A **mutable list of `T`** does **both**: you add items in (input) and read items out (output). Because it uses `T` as input *and* output at the same time, it can be **neither** covariant nor contravariant. So it must be **invariant**.

Restated in my own words (with X a subtype of T):

- **List of T:** it can produce X (read side is fine), but you can't use a list of X as a substitute for it.
- **List of X:** it can't produce T, but you could substitute it with a list of T on the write side.

Since a list is both read and write, each candidate substitution breaks one of the two rules. So you have to pass the exact same type. That is invariance.


## The proof, both directions

**Try covariance (list of cats as a list of animals):**

- Reading is fine: the compile-time type says "animals come out," the runtime list holds cats, and cats are animals, so every item read is indeed an animal. Safe.
- Writing breaks it: the compile-time type "list of animal" says you may add any animal, a dog or a duck. But the real object is a list of cats and does not accept dogs or ducks. Runtime error.
- So covariance is unsafe when the type is used as **input**.

**Try contravariance (list of animals as a list of cats):**

- Writing is fine: the compile-time type "list of cat" says you add cats, the runtime list accepts any animal, and cats are animals, so adding cats is fine. Safe.
- Reading breaks it: the compile-time type "list of cat" says everything you read is a cat, but the runtime list of animals might contain dogs and ducks. Reading one and treating it as a cat is a runtime error.
- So contravariance is unsafe when the type is used as **output**.

Since a read-write list is unsafe both ways, it must be invariant. The only escape:

- A **read-only** list (a source) could safely be covariant.
- A **write-only** list (a sink) could safely be contravariant.
- A read-write list can be neither.


## Why functions are not invariant

A function separates its uses cleanly, which is exactly why it can have variance where a mutable container cannot:

- **Parameters are pure input**, so they are **contravariant** (accept the same type or a more general one).
- **The return is pure output**, so it is **covariant** (return the same type or a more specific one).

Each position has a single role, so each gets its own safe variance direction. A mutable container mixes both roles into one type parameter, so it gets neither.

This is the resolution to the "blueprint versus creation time" confusion: it is not about *when* the check happens. It is about whether the type is used as input only, output only, or both. Functions split input and output into separate positions; mutable containers fuse them, forcing invariance.


## The Robustness Principle (a memory aid)

"Be conservative in what you do, and liberal in what you accept from others."

- **Conservative in what you produce (output):** a subtype's methods should return the same type as the supertype, or something more specific. Users are not surprised. This is covariance of return types.
- **Liberal in what you accept (input):** a subtype's methods should accept the same type as the supertype, or something more general. Users are not surprised. This is contravariance of parameters.


## Where variance shows up

- **Generics (parametric polymorphism):** some languages let you declare a type parameter's variance (for example C#'s `in` for contravariance and `out` for covariance, which line up with the input/output rule).
- **Classes:** many languages allow covariant return types; contravariant inputs often require interfaces.
- **Functions:** where functions are first-class, the rule is clean: **contravariant in parameter types, covariant in return types.**


## Summary

1. **Covariance:** a type may be replaced by a more specific type. Safe for output.
2. **Contravariance:** a type may be replaced by a more general type. Safe for input.
3. **Invariance:** neither; the type must match exactly. Required when a type is used as both input and output (mutable containers).
4. Functions are contravariant in their parameters and covariant in their return, because those positions are pure input and pure output respectively.


## Back to the two project errors

- **Handler parameter error (contravariance):** a handler slot expects a function accepting `Exception`. A handler accepting the narrower `ModelUnavailableError` cannot fill it, because parameters are contravariant: the slot might pass any `Exception`, and the narrow handler could not cope. Fix: widen the parameter to `Exception`, narrow inside with `assert isinstance`.
- **Registration dict error (invariance):** a `dict` is mutable (read and write), so it is invariant. An inferred `dict[type[SpecificError], H]` is not the same type as the expected `dict[type[Exception], H]`, even though `SpecificError` is a subtype of `Exception`. The conflict is on the **write side**: inside the function, the parameter type `dict[type[Exception], H]` permits writing a new broad key (for example `dict[KeyError] = ...`), but the dict actually passed only holds the specific exception types, so that write would corrupt it. Fix: annotate the dict literal explicitly as `dict[int | type[Exception], ExceptionHandler]` so its declared type matches the parameter exactly.
