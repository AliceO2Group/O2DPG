import time
import psutil
import socket
import getpass
import pandas as pd
import matplotlib.pyplot as plt
from typing import Union, List, Dict, Optional
import sys

class PerformanceLogger:
    def __init__(self, log_path: str, sep: str = "|"):
        self.log_path = log_path
        self.start_time = time.time()
        self.sep = sep
        self.user = getpass.getuser()
        self.host = socket.gethostname()

    def log(self, step: str, index: Optional[List[int]] = None):
        elapsed = time.time() - self.start_time
        mem_gb = psutil.Process().memory_info().rss / (1024 ** 3)
        index_str = "" if index is None else f"[{','.join(map(str, index))}]"
        step_full = f"{step}{index_str}"
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')},{int(time.time() * 1000) % 1000:03d} {self.sep} {step_full} {self.sep} {elapsed:.2f} {self.sep} {mem_gb:.2f} {self.sep} {self.user} {self.sep} {self.host}\n"
        with open(self.log_path, "a") as f:
            f.write(line)
        print(f"{step_full} | {elapsed:.2f} | {mem_gb:.2f} | {self.user} | {self.host}")


    @staticmethod
    def log_to_dataframe(log_paths: Union[str, List[str]], sep: str = "|") -> pd.DataFrame:
        if isinstance(log_paths, str):
            log_paths = [log_paths]

        rows = []
        for log_id, path in enumerate(log_paths):
            try:
                with open(path) as f:
                    for row_id, line in enumerate(f):
                        parts = [x.strip() for x in line.strip().split(sep)]
                        if len(parts) < 5:
                            continue
                        timestamp, step, elapsed_str, rss_str, user, host = parts[:6]
                        row = {
                            "timestamp": timestamp,
                            "step": step,
                            "elapsed_sec": float(elapsed_str),
                            "rss_gb": float(rss_str),
                            "user": user,
                            "host": host,
                            "logfile": path,
                            "rowID": row_id,
                            "logID": log_id
                        }

                        if "[" in step and "]" in step:
                            base, idx = step.split("[")
                            row["step"] = base
                            idx = idx.rstrip("]")
                            for i, val in enumerate(idx.split(",")):
                                if val.strip().isdigit():
                                    row[f"index_{i}"] = int(val.strip())
                        rows.append(row)
            except FileNotFoundError:
                continue

        return pd.DataFrame(rows)

    @staticmethod
    def summarize_with_config(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
        group_cols = config.get("by", ["step"])
        stats = config.get("stats", ["mean", "max", "min"])
        agg = {}
        for col in ["elapsed_sec", "rss_gb"]:
            agg[col] = stats
        return df.groupby(group_cols).agg(agg)
    @staticmethod
    def summarize_with_configs(df: pd.DataFrame, config_dict: Dict[str, Dict]) -> Dict[str, pd.DataFrame]:
        summaries = {}
        for name, config in config_dict.items():
            summaries[name] = PerformanceLogger.summarize_with_config(df, config)
        return summaries

    @staticmethod
    def plot(df: pd.DataFrame,
             config_dict: Dict[str, Dict],
             filter_expr: Optional[str] = None,
             output_pdf: Optional[str] = None):

        if filter_expr:
            df = df.query(filter_expr)

        if output_pdf:
            from matplotlib.backends.backend_pdf import PdfPages
            pdf = PdfPages(output_pdf)

        for name, config in config_dict.items():
            subdf = df.copy()
            if "filter" in config:
                subdf = subdf.query(config["filter"])

            varX = config.get("varX", "timestamp")
            varY = config.get("varY", "elapsed_sec")
            aggregation = config.get("aggregation")
            xlabel = config.get("xlabel", varX)
            ylabel = config.get("ylabel", varY)

            if aggregation:
                if isinstance(aggregation, list):
                    agg_df = subdf.groupby(varX)[varY].agg(aggregation)
                    subdf = agg_df.reset_index()
                else:
                    subdf = subdf.groupby(varX)[varY].agg(aggregation).reset_index()

            sort_column = config.get("sort")
            if sort_column:
                subdf = subdf.sort_values(sort_column)

            plt.figure()

            if aggregation and isinstance(aggregation, list):
                for stat in aggregation:
                    plt.plot(subdf[varX], subdf[stat], marker="o", label=stat)
                plt.legend()
            else:
                y = subdf[varY]
                kind = config.get("kind", "line")
                if kind == "line":
                    plt.plot(subdf[varX], y, marker="o")
                elif kind == "bar":
                    plt.bar(subdf[varX], y)
                else:
                    raise ValueError(f"Unsupported plot kind: {kind}")

            if "xticklabels" in config:
                plt.xticks(ticks=subdf[varX], labels=subdf[config["xticklabels"]], rotation=45)

            plt.title(config.get("title", name))
            plt.xlabel(xlabel)
            plt.ylabel(ylabel)
            plt.tight_layout()
            is_testing = "pytest" in sys.modules
            if output_pdf:
                pdf.savefig()
                plt.close()
            elif not is_testing:
                plt.show()

        if output_pdf:
            pdf.close()




# Default configurations

default_plot_config={
    "RSS vs Time": {
        "kind": "line",
        "varX": "timestamp",
        "varY": "rss_gb",
        "title": "RSS over Time",
        "sort": "timestamp"
    },
    "RSS vs Step (chronological)": {
        "kind": "line",
        "varX": "rowID",
        "varY": "rss_gb",
        "title": "RSS vs Step",
        "xlabel": "step",
        "xticklabels": "step",
        "sort": "rowID"
    },
    "Elapsed Time vs Step": {
        "kind": "bar",
        "varX": "step",
        "varY": "elapsed_sec",
        "title": "Elapsed Time per Step",
        "sort": None
    },
    "RSS Summary Stats": {
        "varX": "step",
        "varY": "rss_gb",
        "aggregation": ["mean", "median", "std"],
        "title": "RSS Summary Statistics",
        "xlabel": "Step",
        "ylabel": "RSS (GB)",
        "sort": "step"
    },
    "Elapsed Time Summary Stats": {
        "varX": "step",
        "varY": "elapsed_sec",
        "aggregation": ["mean", "median", "std"],
        "title": "Elapsed Time Summary Statistics",
        "xlabel": "Step",
        "ylabel": "Elapsed Time (s)",
        "sort": "step"
    },
}

default_summary_config={
    "summary_by_step": {
        "by": ["step"],
        "stats": ["mean", "max", "min", "count"]
    },
    "summary_by_step_and_index": {
        "by": ["step", "index_0"],
        "stats": ["mean", "max", "min", "count"]
    }
}