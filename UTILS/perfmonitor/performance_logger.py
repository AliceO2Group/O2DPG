import time
import psutil
import socket
import getpass
import pandas as pd
import matplotlib.pyplot as plt
from typing import Union, List, Dict, Optional

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
        for path in log_paths:
            with open(path) as f:
                for line in f:
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
                        "logfile": path
                    }

                    if "[" in step and "]" in step:
                        base, idx = step.split("[")
                        row["step"] = base
                        idx = idx.rstrip("]")
                        for i, val in enumerate(idx.split(",")):
                            if val.isdigit():
                                row[f"index_{i}"] = int(val)
                    rows.append(row)

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

            if "sort" in config:
                subdf = subdf.sort_values(config["sort"])

            x = subdf[config.get("varX", "timestamp")]
            y = subdf[config.get("varY", "elapsed_sec")]
            kind = config.get("kind", "line")

            plt.figure()
            if kind == "line":
                plt.plot(x, y, marker="o")
            elif kind == "bar":
                plt.bar(x, y)
            else:
                raise ValueError(f"Unsupported plot kind: {kind}")

            plt.title(config.get("title", name))
            plt.xlabel(config.get("xlabel", config.get("varX", "timestamp")))
            plt.ylabel(config.get("ylabel", config.get("varY", "elapsed_sec")))
            plt.xticks(rotation=45)
            plt.tight_layout()

            if output_pdf:
                pdf.savefig()
                plt.close()
            else:
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
        "RSS vs step": {
            "kind": "line",
            "varX": "step",
            "varY": "rss_gb",
            "title": "RSS over Time",
        },
        "Elapsed Time vs Step": {
            "kind": "bar",
            "varX": "step",
            "varY": "elapsed_sec",
            "title": "Elapsed Time per Step",
            "sort": "step"
        }
}

default_summary_config={
        "by": ["step"],
        "stats": ["mean", "max", "min"]
    }

