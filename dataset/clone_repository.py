from pyradar.repository import Repository

# from pyradar.utils import configure_logger


def main(urls: list[str]):
    # pid = os.getpid()
    # configure_logger(f"{pid}", f"log/clone_repository.{pid}.log", logging.INFO)
    for url in urls:
        Repository(url, "/data/kyle/pypi_data")


if __name__ == "__main__":
    import argparse

    import pandas as pd
    from joblib import Parallel, delayed

    df = pd.read_csv("data/metadata_retriever.csv")
    repo_urls = df["PyRadar.MetadataRetriever"].dropna().unique()
    print(len(repo_urls), "unique code repositories")

    parser = argparse.ArgumentParser()
    parser.add_argument("--processes", type=int, default=1)
    args = parser.parse_args()

    processes = args.processes
    print(processes, "processes")
    segments = len(repo_urls) // processes + 1
    print(segments, "repositories per process")
    Parallel(n_jobs=processes, backend="multiprocessing")(
        delayed(main)(repo_urls[i * segments : (i + 1) * segments])
        for i in range(processes)
    )
