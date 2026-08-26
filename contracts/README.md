# Contracts

The wire contracts use JSON Schema Draft 2020-12. `profile.v1` is project-owned input;
`issue.v1`, `evidence.v1`, and `report.v1` are deterministic audit output contracts.

Breaking changes require a new schema filename, `$id`, and Python parser branch. A report always
records both the profile identity and the exact JSON Pointer that supplied each expected value.
`report.v1.assets` is an additive field containing the collected metadata for every successful
asset, including passing metrics that would otherwise produce no issue evidence. Older v1 reports
without this optional field remain schema-valid.
Current reports also include additive execution counters for requested, processed, cancelled, and
completed batches plus the applied batch size. Their parser enforces internally consistent counts.
`benchmark.v1` records real-host timing provenance and integrity; it is not an offline fixture
contract and its limitations are mandatory.
