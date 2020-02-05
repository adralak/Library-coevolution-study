#!/bin/bash

tokens=()
intervals=('stars:2240..90000 language:Java' 'stars:1240..2239 language:Java')

for i in ${!tokens[*]}
do
    python3 parallelized.py ${tokens[$i]} ${intervals[$i]} &
done
