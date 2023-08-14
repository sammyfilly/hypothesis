# This file is part of Hypothesis, which may be found at
# https://github.com/HypothesisWorks/hypothesis/
#
# Copyright the Hypothesis Authors.
# Individual contributors are listed in AUTHORS.rst and the git log.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at https://mozilla.org/MPL/2.0/.

import math
from collections import Counter

from hypothesis.utils.dynamicvariables import DynamicVariable

collector = DynamicVariable(None)


def note_statistics(stats_dict):
    callback = collector.value
    if callback is not None:
        callback(stats_dict)


def describe_targets(best_targets):
    """Return a list of lines describing the results of `target`, if any."""
    # These lines are included in the general statistics description below,
    # but also printed immediately below failing examples to alleviate the
    # "threshold problem" where shrinking can make severe bug look trivial.
    # See https://github.com/HypothesisWorks/hypothesis/issues/2180
    if not best_targets:
        return []
    elif len(best_targets) == 1:
        label, score = next(iter(best_targets.items()))
        return [f"Highest target score: {score:g}  ({label=})"]
    else:
        lines = ["Highest target scores:"]
        lines.extend(
            f"{score:>16g}  ({label:=})"
            for label, score in sorted(
                best_targets.items(), key=lambda x: x[::-1]
            )
        )
        return lines


def format_ms(times):
    """Format `times` into a string representing approximate milliseconds.

    `times` is a collection of durations in seconds.
    """
    ordered = sorted(times)
    n = len(ordered) - 1
    assert n >= 0
    lower = int(ordered[int(math.floor(n * 0.05))] * 1000)
    upper = int(ordered[int(math.ceil(n * 0.95))] * 1000)
    if upper == 0:
        return "< 1ms"
    elif lower == upper:
        return f"~ {lower}ms"
    else:
        return f"~ {lower}-{upper} ms"


def describe_statistics(stats_dict):
    """Return a multi-line string describing the passed run statistics.

    `stats_dict` must be a dictionary of data in the format collected by
    `hypothesis.internal.conjecture.engine.ConjectureRunner.statistics`.

    We DO NOT promise that this format will be stable or supported over
    time, but do aim to make it reasonably useful for downstream users.
    It's also meant to support benchmarking for research purposes.

    This function is responsible for the report which is printed in the
    terminal for our pytest --hypothesis-show-statistics option.
    """
    lines = [stats_dict["nodeid"] + ":\n"] if "nodeid" in stats_dict else []
    prev_failures = 0
    for phase in ["reuse", "generate", "shrink"]:
        d = stats_dict.get(f"{phase}-phase", {})
        # Basic information we report for every phase
        cases = d.get("test-cases", [])
        if not cases:
            continue
        statuses = Counter(t["status"] for t in cases)
        runtime_ms = format_ms(t["runtime"] for t in cases)
        drawtime_ms = format_ms(t["drawtime"] for t in cases)
        lines.append(
            f"  - during {phase} phase ({d['duration-seconds']:.2f} seconds):\n"
            f"    - Typical runtimes: {runtime_ms}, of which {drawtime_ms} in data generation\n"
            f"    - {statuses['valid']} passing examples, {statuses['interesting']} "
            f"failing examples, {statuses['invalid'] + statuses['overrun']} invalid examples"
        )
        if distinct_failures := d["distinct-failures"] - prev_failures:
            plural = distinct_failures > 1
            lines.append(
                f'    - Found {distinct_failures}{" more" * bool(prev_failures)} distinct error{"s" * plural} in this phase'
            )
        prev_failures = d["distinct-failures"]
        # Report events during the generate phase, if there were any
        if phase == "generate":
            if events := Counter(sum((t["events"] for t in cases), [])):
                lines.append("    - Events:")
                lines += [
                    f"      * {100 * v / len(cases):.2f}%, {k}"
                    for k, v in sorted(events.items(), key=lambda x: (-x[1], x[0]))
                ]
        # Some additional details on the shrinking phase
        if phase == "shrink":
            lines.append(
                f'    - Tried {len(cases)} shrinks of which {d["shrinks-successful"]} were successful'
            )
        lines.append("")

    if target_lines := describe_targets(stats_dict.get("targets", {})):
        lines.append(f"  - {target_lines[0]}")
        lines.extend(f"    {l}" for l in target_lines[1:])
    lines.append("  - Stopped because " + stats_dict["stopped-because"])
    return "\n".join(lines)
