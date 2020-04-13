#!/bin/bash

for filename in data/*; do
    python3 scan_poms_no_threads.py $filename &
done
		
