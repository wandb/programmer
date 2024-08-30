import asyncio
import pandas as pd
from typing import Optional
import random
import weave

from .swebench_model import SWEBenchProgrammerModel
from .score import score_swebench
from ..agent import Agent
from ..config import agent_4o_basic


def load_raw_dataset(name: str, split: str):
    return pd.read_parquet(
        f"hf://datasets/princeton-nlp/{name}/data/{split}-00000-of-00001.parquet"
    )


def load_weave_dataset(
    name: str,
    split: str,
    limit: Optional[int] = None,
    instance_ids: Optional[list[str]] = None,
    shuffle_seed: Optional[int] = None,
):
    df = load_raw_dataset(name, split)

    data_list = df.to_dict("records")
    if shuffle_seed is not None:
        random.seed(shuffle_seed)
        random.shuffle(data_list)
    data_list = [
        r for r in data_list if instance_ids is None or r["instance_id"] in instance_ids
    ]
    data_list = data_list[:limit] if limit else data_list
    data_list = [{"instance": r} for r in data_list]

    return weave.Dataset(name=f"Verified-{limit}-{shuffle_seed}", rows=data_list)  # type: ignore


def main():
    weave.init("weavedev-programmereval1")
    instance_ids = [
        "django__django-16569",
        "django__django-11099",
        "scikit-learn__scikit-learn-12585",
        "django__django-13658",
        "django__django-9296",
        "astropy__astropy-14309",
        "django__django-12155",
        "django__django-16527",
        "sympy__sympy-24213",
        "django__django-11066",
    ]
    # ds = load_weave_dataset("SWE-bench_Verified", "test", instance_ids=instance_ids)
    ds = load_weave_dataset("SWE-bench_Verified", "test", limit=50, shuffle_seed=42)
    eval = weave.Evaluation(
        name="SWE-bench_Verified", dataset=ds, scorers=[score_swebench], trials=1
    )

    model = SWEBenchProgrammerModel(
        agent=agent_4o_basic,
        max_runtime_seconds=180,
    )
    res = asyncio.run(eval.evaluate(model))
    print("RES", res)


if __name__ == "__main__":
    main()
