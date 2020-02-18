#!/bin/bash

tokens=()

for i in ${!tokens[*]}
do
    python3 parallelized.py ${tokens[$i]} $i ${#tokens[@]}&
done
