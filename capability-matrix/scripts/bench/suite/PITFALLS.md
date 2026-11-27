# Pitfalls this suite exists to prevent

Every item below produced a **plausible-looking wrong number** on this cluster, and every one was
caught by the data being implausible rather than by anything erroring. They are listed first
because the guards in `preflight.sh` and the experiment scripts only make sense as answers to them.

The general rule, learned the hard way: **a value that is flat, zero, or suspiciously round is
usually instrumentation, not physics.**

## 1. Timing work that never happened

A `.rknn` model needs a 4-dim `NHWC` input. Fed a 3-dim array, every `rknnlite` inference raised —
but the exception was swallowed inside the library and the timing loop kept running, happily
reporting throughput for inferences that all failed.

**Guard:** `e1` probes once and raises if `inference()` returns `None`, and re-checks inside the
loop. Never time a call whose success you have not asserted.

Same class: a shell arm whose label contained a space produced `>/tmp/bt_$2.log` → "ambiguous
redirect" → the server never started → the script timed `kill` on a nonexistent PID and reported
`0.00s` four times. Four identical zeros is not a measurement.

## 2. Measuring the wrong engine entirely

`llama-completion` on a build with a Vulkan backend **offloads every layer to the GPU by default**.
A sweep intended to characterise the CPU instead measured Mali, and reproduced the published Mali
figure to two decimals (9.21 / 9.21 / 9.20 tok/s at 1, 4 and 8 threads). The tell was that thread
count changed nothing.

**A CPU-only run needs BOTH `-ngl 0` AND `-dev none`.** `-ngl 0` alone is not enough: the Vulkan
backend still loads and yields non-monotonic nonsense (1.32 / 4.83 / 2.62 at 1 / 4 / 8 threads).

**Guard:** `preflight.sh` asserts that a `-ngl 0 -dev none` run's decode rate *changes* with thread
count, and that an `-ngl 99` run drives `gpu_load` above zero.

## 3. Parsing the wrong field

`eval time =` and `prompt eval time =` both end in `tokens per second`. A non-greedy regex anchored
on `eval time` matches the **prompt** line first, so decode figures came back as prefill rates
(2.79 tok/s reported as decode).

**Guard:** anchor on `runs`, which only the decode line has:
`eval time =\s+[\d.]+ ms /\s+\d+ runs.*?([\d.]+) tokens per second`

## 4. Reading a sysfs path that does not exist

`/sys/devices/17000000.gpu/devfreq/17000000.gpu/cur_freq` is wrong on this image. It returned
nothing, the arithmetic turned that into `0`, and a thermal run reported `min GPU clock 0 MHz` —
which reads exactly like severe throttling. The real path is
`/sys/class/devfreq/17000000.gpu/cur_freq` (1173 MHz at full tilt).

**Guard:** `preflight.sh` fails loudly if any instrumentation path is missing, before any arm runs.

## 5. Bare `wait`, and traps inherited by subshells

Two separate shell faults, both of which left hardware running:

- A script hand-started `llama-server` as a background job and then called bare `wait`, which waits
  for **every** background job including the server. It hung for **3 h 46 m** with the managed
  service down and an unmanaged server serving on localhost.
- A backgrounded rail sampler was a subshell that **inherited the `EXIT` trap**. When it finished
  it ran `cleanup()`, restarting the managed service mid-test; the service then held the GPU memory
  the next arm needed, and the GPU arms died with `failed to create context`.

**Guards:** never bare `wait` — collect PIDs and `wait "$p"` each. Every backgrounded subshell
starts with `trap - EXIT`. `cleanup()` returns immediately unless `$$` equals the main shell's PID.

## 6. `pkill -f` matching your own command line

`pkill -9 -f "/tmp/cutover.sh"` killed the ssh session issuing it, because that string was in its
own command line. The same self-match made `pgrep -f npu_submit.py` report a dead process as alive,
and made an `until ! pgrep -f iso3.sh` waiter wait forever on itself.

**Guard:** kill by captured PID. To count, use `ps -eo args | grep "[p]attern"` and read the PIDs,
never a bare count.

## 7. Settling too briefly, then calling it idle

After an 8-stream run, `gpu_load` still read 999 and the rail 26.52 W twenty seconds after the load
generators were killed — the server was still draining queued requests. That looks like a leak and
is not one.

**Guard:** `idle_verify.sh` polls until idle with a timeout rather than sleeping a fixed interval,
and reports the numbers it saw.

## 8. Picking the configuration that hides the effect

A thermal run used 8 concurrent streams and peaked at 80 °C, missing a 98 °C condition seen
earlier. Paper 006 predicts exactly this: 2 → 8 streams *lowers* module power by 4.51 W, so 8
streams is the **cold** configuration. The experiment was run in the one setting least likely to
show the effect.

**Guard:** `e5` documents why it uses 2 streams, not 8. More generally: check whether your own prior
results predict that your chosen operating point suppresses what you are looking for.

## 9. Inferring a hardware limit from one knob

Several wrong conclusions came from varying one parameter and generalising: a "shared ~253 qps DLA
ceiling" (refuted at 1133.8 qps), a "newer-build regression" (inverted by a same-node A/B), "the
stall is deterministic in `n_predict`" (256 both stalled and did not), "the per-slot context is the
boundary" (512 stalls, 1024 does not).

**Guard:** every experiment here fits on one knob and then **predicts an arm it did not fit**. The
out-of-sample error is the result; the fit alone is not.

## 10. Trusting a two-rep sample

A 1.323× figure came from 2 reps that happened to catch the fast mode of a bimodal arm (48.6, 49.0,
then 33.2, 35.5, 38.6). Arms that saturate all four A76 cores are bimodal, which is *not* thermal
or DVFS — clocks held 2256 MHz, min = max = mean, at 44–60 °C — and is most likely OS starvation
when every big core is claimed.

**Guards:** 5 reps minimum, per-rep values printed so bimodality is visible, and a spare core left
for the OS where the budget allows.

## 11. A function cannot hand back a background PID

`p=$(run_something_in_background)` runs the function body in a **command-substitution subshell**.
The job becomes a grandchild of the script, so the parent's `wait "$p"` fails with "not a child"
and the script races straight on. In `e7`'s first version this launched all 20 arms at once instead
of one at a time, orphaned ~20 `llama-completion` processes on an 8-core board (loadavg **22.69**),
and reported `FAIL` for every arm because the parser read incomplete files.

**Guard:** launch in the current shell and capture `$!` there — a helper may *set* a variable
(`LASTPID=$!`) but must never be called through `$( )` to obtain one.

This is the **third** variant of the same root cause in one day, alongside bare `wait` (pitfall 5)
and `EXIT` traps inherited by subshells (also 5). All three left hardware running: a 3 h 46 m hang
with a managed service down, a mid-test service restart that voided two GPU arms, and an orphan
storm. **Shell job control is the most dangerous part of this work** — more dangerous than any
measurement error, because the failures keep the cluster busy rather than stopping it.

Before running any new script here, check all three:

- no bare `wait` — collect PIDs, `wait "$p"` each
- every backgrounded subshell begins `trap - EXIT`
- no `$( )` around anything that backgrounds a job
