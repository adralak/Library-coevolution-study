#!/bin/bash

tokens=(token1 token2 token3)


for i in ${!tokens[*]}
do
    python3 get_repos_no_threads.py ${tokens[$i]} $i ${#tokens[@]} &
done
