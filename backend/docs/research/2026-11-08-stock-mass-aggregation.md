# Call-local exact mass aggregation

`stock_state` still scans every unit, location, container and owner on each call.
It retains the existing conservation, placement, capacity, seal, disposal and
whole-shipment checks. `StockLedger` still validates immutable source authority,
authorized locations and claims. No check is skipped because a revision is unchanged.

The only arithmetic change groups unit counts by the complete validated
`UnitRecipe` value during one call. The group stores exact `Fraction` net,
primary-tare and gross masses. Container contents and the onsite/shipped balance
then multiply those masses by integer counts. Container tare and disposal retain
their separate accounting. There are no rounded numbers or float tolerances.

The private `_MassPass` is recreated inside `check_state`, `contents_view` and
`balances`. It retains a strong reference to every distinct recipe object until
that call ends. Every new identity must have exact nested types before value
hashing or equality: Python's `True`, `1`, `1.0` and `Fraction(1)` can otherwise
compare equal. Equal but distinct recipe objects undergo their own validation.
The helper is not stored on the ledger, in a transaction or across ticks.

This follows the existing synchronous immutable-record execution model. It adds
neither thread safety nor permission to mutate records while a scan is running.
It is arithmetic, not an independent inventory authority or a serialized model.
Schema fields, events, versions and transaction behavior are unchanged.

Tests first reproduced 24 repeated gross-mass calculations for 24 units sharing
one recipe, independently in the checker, contents view and balance. Each call
now calculates that recipe once, including a second call at the same revision.
Hand arithmetic covers equal gross masses with distinct net/tare values,
distinct geometry, separate buckets, empty buckets, numeric aliases and changes
between calls. Existing stock and process tests remain the behavioral regression
authority; this optimization does not supply new expected warehouse outcomes.

The source model shares eight recipe objects across 12,256 units. Grouping can
reduce arithmetic there. A model with many distinct but equal objects must still
validate each identity and can be slower. Kernel measurements or measurements
during concurrent testing are diagnostics, not warehouse runtime guarantees.
