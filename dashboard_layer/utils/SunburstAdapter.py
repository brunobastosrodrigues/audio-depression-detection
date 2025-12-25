import json
import pandas as pd

class SunburstAdapter:
    def __init__(self, config_path="core/mapping/config.json"):
        """
        Initialize with the mapping config to understand the hierarchy.
        """
        with open(config_path, "r") as f:
            self.mapping_config = json.load(f)

    def process(self, indicator_record: dict, metric_records: list) -> dict:
        """
        Transform flat records into Plotly Sunburst format.

        Args:
            indicator_record: Dict containing the final DSM-5 scores (e.g., {'1_depressed_mood': 1.5})
            metric_records: List of dicts or objects containing 'metric_name' and 'analyzed_value' (Z-scores)

        Returns:
            Dict containing 'ids', 'labels', 'parents', 'values', 'colors' for Plotly.
        """

        # --- 1. Pre-process Inputs ---
        # Convert list of metrics to a quick lookup dict: { 'jitter': 2.3, ... }
        metric_lookup = {
            m['metric_name'] if isinstance(m, dict) else m.metric_name:
            m['analyzed_value'] if isinstance(m, dict) else m.analyzed_value
            for m in metric_records
        }

        # Clean indicator keys (remove "1_", "2_" prefixes for display)
        indicators = indicator_record.get('indicator_scores', {})

        # --- 2. Calculate Center (MDD Support Status) ---
        # Logic: >= 5 symptoms active, AND (Ind 1 OR Ind 2 is active)
        active_count = 0
        core_symptom_active = False

        # We assume a threshold of 1.0 for "Active" (Calibration required in future)
        THRESHOLD = 1.0

        for key, score in indicators.items():
            # Treat None as 0
            if score is None: score = 0

            if score >= THRESHOLD:
                active_count += 1
                if key.startswith("1_") or key.startswith("2_"):
                    core_symptom_active = True

        if active_count >= 5 and core_symptom_active:
            center_label = "<b>MDD<br>SUPPORT</b>"
            center_color = "#FF4136" # Red
        elif active_count > 0:
            center_label = "<b>MONITORING</b>"
            center_color = "#FFDC00" # Yellow
        else:
            center_label = "<b>NO<br>SUPPORT</b>"
            center_color = "#2ECC40" # Green

        # --- 3. Build Plotly Lists ---
        ids = ["root"]
        labels = [center_label]
        parents = [""]
        values = [0] # Root value is usually ignored or sum of children
        colors = [center_color]

        # Iterate through DSM-5 Indicators (Inner Ring)
        for ind_key, ind_details in self.mapping_config.items():

            # Prepare Label
            parts = ind_key.split('_', 1)
            clean_name = parts[1].replace('_', ' ').title() if len(parts) > 1 else ind_key

            # Shorten long names for UI readability
            if "Psychomotor" in clean_name: clean_name = "Psychomotor"
            if "Diminished" in clean_name: clean_name = "Concentration"
            if "Recurrent" in clean_name: clean_name = "Suicidal Ideation"
            if "Significant Weight" in clean_name: clean_name = "Weight Change"

            ind_score = indicators.get(ind_key, 0)
            if ind_score is None: ind_score = 0

            # ID Strategy: root -> indicator
            node_id = f"root - {ind_key}"

            ids.append(node_id)
            labels.append(f"{clean_name}<br>({ind_score:.1f})")
            parents.append("root")
            values.append(max(ind_score, 0.5)) # Ensure it has some size even if 0

            # Color logic: Orange if active, Light Grey if inactive
            colors.append("#FF851B" if ind_score >= THRESHOLD else "#DDDDDD")

            # Iterate through Acoustic Features (Outer Ring)
            # These are the children of the Indicator
            metrics = ind_details.get('metrics', {})
            for metric_name, props in metrics.items():

                weight = props['weight']
                if weight == 0: continue

                z_score = metric_lookup.get(metric_name, 0)
                if z_score is None: z_score = 0

                # Outer Ring Node
                child_id = f"{node_id} - {metric_name}"

                ids.append(child_id)
                labels.append(f"{metric_name}<br>z: {z_score:.1f}")
                parents.append(node_id)

                # Visual sizing: Use absolute Z-score to show "impact"
                size = abs(z_score) if abs(z_score) > 0.1 else 0.1
                values.append(size)

                # Color logic: Red for high contribution, Grey for normal
                colors.append("#FF4136" if abs(z_score) > 2.0 else "#AAAAAA")

        return {
            "ids": ids,
            "labels": labels,
            "parents": parents,
            "values": values,
            "colors": colors
        }
