#!/bin/bash

tokens=(token1 token2 token3)


for i in ${!tokens[*]}
do
    python3 get_date.py ${tokens[$i]} $i ${#tokens[@]} 2 &
done
