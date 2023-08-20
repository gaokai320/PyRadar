# RADAR: Towards Automatic Source Code Repository Information Recovery and Validation for PyPI Packages

## Environment Setup
```shell
# Ubuntu 22.04 LTS (GNU/Linux 5.19.0-41-generic x86_64)
# install pyenv from https://github.com/pyenv/pyenv#installation
pyenv install 3.11.3
pyenv virtualenv 3.11.3 radar
pyenv activate radar
pip install -r requirements.txt
# e.g., /data/pypi_data
export DATA_HOME=<Folder to Store Data>
```

## Run Scripts
1. Dump PyPI package metadata
```shell
python -u pypi_crawler.py --folder=$DATA_HOME --email=<Your Email>
```

2. Import metadata to MongoDB
```shell
python -u import_to_mongo.py $DATA_HOME
```

3. Get number of downloads for each package in recent 30 days.
```SQL
SELECT file.project, COUNT(*) AS num_downloads
FROM `bigquery-public-data.pypi.file_downloads`
WHERE DATE(timestamp)
    BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    AND CURRENT_DATE()
GROUP BY file.project
ORDER BY num_downloads DESC
```

4. Get repository URL, number of downloads, and number of dependents for each package.
```shell
python package_statistics.py
```
5. Obtain baseline results
```shell
python -m dataset.run_baselines --baseline ossgadget
python -m dataset.run_baselines --baseline warehouse
python -m dataset.run_baselines --baseline librariesio
# caution: running py2src requires very heavy http requests and is very slow
python -m dataset.run_baselines --baseline py2src --n_jobs <numOfProcessess> --chunk_size <numofChunks>
# dump baseline results to MongoDB
python -m dataset.run_baselines --dump
```
You can also obtain results of a single release by passing `--name` and `--version` arguments:
```shell
python -m dataset.run_baselines --baseline librariesio --name tensorflow --version 2.9.0
```

6. Obtain MetadataRetriever results. Since MetadataRetriever still need to search webpages, to reduce http requests as many as possible, we run it by stages.

    1. The 1st stage: use `--all` option to search repository urls from the `home_page``, `download_url`, `project_urls`, and `description` field in the metadata.

        ```shell
        python -m dataset.run_metadata_retriever --all
        ```
    2. The 2nd stage: use `--left_release` option to get all repository urls in the unique homepage and documentation webpage in the left releases whose metadata does not have repository url.

        ```shell
        python -m dataset.run_metadata_retriever --left_release --n_jobs <numOfProcessess> --chunk_size <numofChunks>
        ```

    3. The 3rd stage: use `--process_log` option to process failed urls in the 3nd stage.

        ```shell
        python -m dataset.run_metadata_retriever --process_log --n_jobs <numOfProcessess> --chunk_size <numofChunks> 2>log/metadata_retriever.log.2
        ```

    4. The 4th stage: use `--merge` option to merge retrived repository url for each webpage in the 3rd stage to MetadataRetriever results:

        ```shell
        python -m dataset.run_metadata_retriever --merge
        ```

    5. The 5th stage: use`--redirect` option to get the redirected url of each repository urls retrived by MetadataRetriever:

        ```shell
        python -m dataset.run_metadata_retriever --redirect --n_jobs <numOfProcessess> --chunk_size <numofChunks> 2>log/metadata_retriever.log
        ```

You can also obtain results of a single release by passing `--name` and `--version` arguments. There are some options:

- `--webpage`: search the webpage pointed by the Homepage and Documentation links in the metadata
- `--redirect`: get the redirected url of the retrieved repository url

```shell
python -m dataset.run_metadata_retriever --name tensorflow --version 2.10.0
```

7. construct positive and negative dataset:

```shell
python -m dataset.ground_truth --dataset
```
