from data_process import Layer


class CgroupReduction(Layer):
    def process(self, data):
        active_cpu_metrics = [
            metrics
            for metrics in data.values()
            if metrics.get("INST_RETIRED", 0) != 0
        ]
        if not active_cpu_metrics:
            raise ValueError("no active CPU metrics for local inference")

        feature_names = active_cpu_metrics[0].keys()
        averaged_features = {
            feature_name: sum(
                metrics[feature_name]
                for metrics in active_cpu_metrics
            ) / len(active_cpu_metrics)
            for feature_name in feature_names
        }
        return {0: averaged_features}
