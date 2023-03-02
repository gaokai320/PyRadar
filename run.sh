for i in {0..39}; do
    python -u collect_pypi_metadata.py /data/kyle/pypi_data /data/kyle/pypi_data/metadata 0 $i 2>log/collect_pypi_metadata.error.log.$i &
done
