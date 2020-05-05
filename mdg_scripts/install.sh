#!/bin/bash

wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
echo 'deb https://debian.neo4j.com stable latest' | sudo tee -a /etc/apt/sources.list.d/neo4j.list
sudo apt update
sudo add-apt-repository universe
sudo apt install neo4j
pip3 install git+https://github.com/technige/py2neo.git#egg=py2neo
