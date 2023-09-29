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

## Folder Structure

> - baseline_analysis.ipynb: Code for RQ1 results for Metadata-based Retriever evaluation.
> - dist_diff_analysis.ipynb and dist_file_analysis.ipynb: Code for why use the source distribution.
> - phantom_file_analysis.ipynb: Code for RQ2 results.
> - validator_analysis.ipynb: Code for Source Code Repository Validator evaluation.
> - retriever_analysis.ipynb: Code for Source Code-based Retriever evaluation.


## Run Scripts
1. Dump PyPI package metadata
    ```shell
    python -u pypi_crawler.py --folder=$DATA_HOME --email=<Your Email> --processes <numOfProcessess> --chunk <numofDataPerChunk>
    ```

2. Import metadata to MongoDB. We provide the dump in the `mongodb`  folder (`release_metadata.bson.gz` and `distribution_file_info.bson.gz`).
    ```shell
    python -u import_to_mongo.py --base_folder $DATA_HOME --metadata --distribution --drop
    ```

1. Obtain baseline results. We provide a MongoDB dump in the `mongodb` folder (`baseline_results.bson.gz`)
    ```shell
    python -m dataset.run_baselines --baseline ossgadget
    python -m dataset.run_baselines --baseline warehouse
    python -m dataset.run_baselines --baseline librariesio
    # caution: running py2src requires very heavy http requests and is very slow
    python -m dataset.run_baselines --baseline py2src --n_jobs <numOfProcessess> --chunk_size <numofDataPerChunk>
    # dump baseline results to MongoDB
    python -m dataset.run_baselines --dump
    ```
    You can also obtain results of a single release by passing `--name` and `--version` arguments:
    ```shell
    python -m dataset.run_baselines --baseline librariesio --name tensorflow --version 2.9.0
    ```

1. Obtain MetadataRetriever results. Since MetadataRetriever still need to search webpages, to reduce http requests as many as possible, we run it by stages.

    1. The 1st stage: use `--all` option to search repository urls from the `home_page``, `download_url`, `project_urls`, and `description` field in the metadata.

        ```shell
        python -m dataset.run_metadata_retriever --all
        ```
    2. The 2nd stage: use `--left_release` option to get all repository urls in the unique homepage and documentation webpage in the left releases whose metadata does not have repository url.

        ```shell
        python -m dataset.run_metadata_retriever --left_release --n_jobs <numOfProcessess> --chunk_size <numofDataPerChunk>
        ```

    3. The 3rd stage: use `--process_log` option to process failed urls in the 3nd stage.

        ```shell
        python -m dataset.run_metadata_retriever --process_log --n_jobs <numOfProcessess> --chunk_size <numofDataPerChunk> 2>log/metadata_retriever.log.2
        ```

    4. The 4th stage: use `--merge` option to merge retrived repository url for each webpage in the 3rd stage to MetadataRetriever results:

        ```shell
        python -m dataset.run_metadata_retriever --merge
        ```

    5. The 5th stage: use`--redirect` option to get the redirected url of each repository urls retrived by MetadataRetriever:

        ```shell
        python -m dataset.run_metadata_retriever --redirect --n_jobs <numOfProcessess> --chunk_size <numofDataPerChunk> 2>log/metadata_retriever.log
        ```

    You can also obtain results of a single release by passing `--name` and `--version` arguments. There are some options:

   - `--webpage`: search the webpage pointed by the Homepage and Documentation links in the metadata
   - `--redirect`: get the redirected url of the retrieved repository url

    ```shell
    python -m dataset.run_metadata_retriever --name tensorflow --version 2.10.0
    ```

1. List repositories's blobs based on metadata retriever results:

    ```shell
    # Clone repositories to local
    python -m dataset.clone_repository --base_folder $DATA_HOME --processes <numOfProcessess> --chunk_size <numofDataPerChunk>

    # List repositories's blobs
    python -m dataset.list_blobs --base_folder $DATA_HOME --processes <numOfProcessess> --chunk_size <numofDataPerChunk>
    ```

8. Compare the difference between source distributions and binary distributions

    ```shell
    python -m dataset.dist_diff --base_folder $DATA_HOME --all --processes <numOfProcessess> --chunk_size <numofDataPerChunk> [ --mirror <PyPI mirror site> ]
    ```

9.  construct dataset:

    ```shell
    # collect Python repositories on GitHub with more than 100 stars.
    python -m dataset.ground_truth --repository

    # collect packages in these GitHub repositories
    python -m dataset.ground_truth --package --n_jobs <numOfProcessess> --chunk_size <numofDataPerChunk>

    # collect PyPI package's PyPI maintainer
    python -m dataset.ground_truth --maintainer --n_jobs <numOfProcessess> --chunk_size <numofDataPerChunk>

    # construct ground truth dataset for validator
    python -m dataset.ground_truth --dataset

    # download source distributions for releases in the ground truth dataset, you can specify a PyPI mirror site to accelerate the downloading.
    python -m dataset.ground_truth --download --dest $DATA_HOME --n_jobs <numOfProcessess> --chunk_size <numofDataPerChunk> [ --mirror <PyPI mirror site> ]

    # Get Phantom files in matched and mismatched releases.
    python -m dataset.run_validator --base_folder $DATA_HOME --n_jobs <numOfProcessess> --chunk_size <numofDataPerChunk> --phantom_file

    # Get validator features for matched and mismatched releases.
    python -m dataset.run_validator --base_folder $DATA_HOME --n_jobs <numOfProcessess> --features

    # Download the source distributions for the latest release of all PyPI packages
    python -m dataset.run_validator --base_folder $DATA_HOME --n_jobs <numOfProcessess> --pypi [ --mirror <PyPI mirror site> ]

    # Get validator features for all PyPI releases.
    python -m dataset.run_validator --base_folder $DATA_HOME --n_jobs <numOfProcessess> --pypi_features

    # Get files shas for correct links
    python -m dataset.run_retriever --base_folder $DATA_HOME --n_jobs <numOfProcessess> --fileshas

    # Get candidates from WoC
    python -m dataset.run_retriever --base_folder $DATA_HOME --n_jobs <numOfProcessess> --candidates [ --mirror <PyPI mirror site> ]

    # Get topn candidates
    python -m dataset.run_retriever --base_folder $DATA_HOME --most_common

    # Get upstream forks
    python -m dataset.run_retriever --base_folder $DATA_HOME --chunk_size <numofDataPerChunk> --defork

    # Get final returned repository
    python -m dataset.run_retriever --base_folder $DATA_HOME --final

    # Retrieve for releasess for which the Metadata-based Retreiver can not retrieve repository information
    python -m dataset.run_retriever --base_folder $DATA_HOME --n_jobs <numOfProcessess> --download_remaining [ --mirror <PyPI mirror site> ]
    python -m dataset.run_retriever --base_folder $DATA_HOME --n_jobs <numOfProcessess> --candidate_remaining [ --mirror <PyPI mirror site> ]
    python -m dataset.run_retriever --base_folder $DATA_HOME --chunk_size <numofDataPerChunk> --most_common_remaining --defork_remaining --final_remaining
    ```

10. fit machine learning models on validator features:

    ```shell
    # run Logistic Regression, Decision Tree, Random Forest, AdaBoost, Gradient Boosting, SVM, XGBoost
    python -m models.fit_model --all --n_jobs <numOfProcessess>
    ```

11.
