# RADAR: Towards Automatic Source Code Repository Information Recovery and Validation for PyPI Packages

## Environment Setup
```shell
# Ubuntu 20.04.3 LTS (GNU/Linux 5.4.0-113-generic x86_64)
conda create -n radar python=3.8.11
conda activate radar
pip install ipykernel
pip install -r requirements.txt
export DATA_HOME=<Folder to Store Data>
```

## Run Scripts
1. Dump PyPI package metadata
```shell
python -u pypi_crawler.py --folder=$DATA_HOME --email=gaokai19@pku.edu.cn
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