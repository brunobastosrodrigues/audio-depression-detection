"""Edge-offload gap-filler: skip server extractors for features a node already computed.

Kept dependency-free (no audio libs) so it imports cheaply and is unit-testable on its own.
"""

# Server extractor task-key -> the metric name(s) it produces, for tasks whose ENTIRE output
# a node can provide on-device (so the extractor is skipped when those metrics are in
# provided_features). Only single-output, edge-feasible extractors are listed; the
# multi-output dynamic tasks (pitch, *_dynamic) are intentionally excluded -- they're not
# edge-offloadable and must keep running server-side.
SKIPPABLE_TASK_OUTPUTS = {
    "snr": ["snr"],
    "spectral_flatness": ["spectral_flatness"],
    "temporal_modulation": ["temporal_modulation"],
    "spectral_modulation": ["spectral_modulation"],
    "voice_onset_time": ["voice_onset_time"],
    "glottal_pulse_rate": ["glottal_pulse_rate"],
    "f2_transition_speed": ["f2_transition_speed"],
    "jitter": ["jitter"],
    "shimmer": ["shimmer"],
}


def select_tasks(all_tasks, provided_features, skippable=SKIPPABLE_TASK_OUTPUTS):
    """Split the extractor task list given the node-provided features.

    Returns (tasks_to_run, preseeded_results): any task whose ENTIRE output is present in
    provided_features is skipped, and its node value is seeded into results. With no
    provided_features, all tasks run and results is empty (today's behavior).
    """
    results = {}
    if not provided_features:
        return list(all_tasks), results
    kept = []
    for key, fn, args in all_tasks:
        outputs = skippable.get(key)
        if outputs and all(o in provided_features for o in outputs):
            for o in outputs:
                results[o] = provided_features[o]
        else:
            kept.append((key, fn, args))
    return kept, results
