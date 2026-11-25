# Methodology

This project is a lab notebook, not a marketing page. The rules below exist so that every row of the matrix can survive review.

## Evidence levels

| Level | Meaning | Acceptable for a paper? |
|---|---|---|
| MEASURED | Exercised on this unit; there is a dated log with the commands, raw output and caveats | Yes |
| INVENTORY | Seen on the running system (a device node, a package) but not exercised | Only as a scoping statement |
| DOCUMENTED | Stated by a vendor; not verified here | Only cited as such |
| PLANNED | Intended, not run | No |
| UNKNOWN | The answer is not known and the vendor is silent | No |

A row's **status** may never claim more than its **evidence**. A `WORKS` row needs MEASURED evidence.

## Rules

1. **Log first, summarise second.** Each experiment gets a file in `logs/` named `YYYY-MM-DD_topic.md` with: question, setup, method, raw results, interpretation, limitations.
2. **Record the environment.** Board revision, BMC firmware, module SKU, slot, OS image, kernel, driver versions, and the host used to drive the test.
3. **Separate cold and warm.** Cold start (power removed by the BMC) and warm reboot behave differently on this platform, so counts are always reported per kind.
4. **Report denominators.** "Failed 2 times" is meaningless; "2 of 18 cold boots" is a result. With small samples, say so rather than quoting a rate as if it were precise.
5. **Say when a theory was retracted.** One interpretation in the mini-PCIe log was wrong and was corrected once contradicting data arrived. The log keeps both.
6. **Do not identify hardware from software strings alone.** Device-tree `model` strings are free text. Where possible, cross-check against something physical (module EEPROM, PCI IDs, measured behaviour).
7. **Reversible before irreversible.** Anything that writes flash or fuses is preceded by a verified backup and a tested restore path. Fuse and secure-boot experiments need explicit sign-off.
8. **Identifiers that could identify a person or network** (addresses, serials, MACs) are left out of the public record unless a paper needs them.

## Reproducibility

Scripts live in `scripts/` or in linked repositories. A result that cannot be re-run from a script is recorded as an observation, not a benchmark.

## Known limitations of this study

- One board, one unit of each module. Nothing here is a statement about the population of boards or modules.
- The host driving the tests is a consumer laptop on a recent Ubuntu release that NVIDIA's tools do not officially support; workarounds are documented in the recovery repository.
- Throughput numbers so far come from single `dd` runs, not `fio`; they are indicative only.
