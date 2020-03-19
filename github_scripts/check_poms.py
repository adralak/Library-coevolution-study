from github import Github
from xml.dom import minidom
import requests
import csv
import datetime
from threading import Thread, Lock
from queue import Queue
from time import sleep
from sys import argv
import os


# Get token from user and log in
token = argv[1]
gh = Github(token, per_page=1000)
intervals = []

with open("intervals.txt", 'r') as f:
    for line in f:
        intervals.append(line)

# These variables help filter which repos are seen
max_date = datetime.datetime(year=2019, day=31, month=12)

# Where to write the poms to
exec_space = "exec_space" + token + "/"
try:
    os.mkdir(exec_space)
except:
    ()

# For handling problematic repos
exceptions = open(exec_space + "exceptions" + token + ".txt", "w")
other_probs = open(exec_space + "errors" + token + ".txt", "w")

# Handle rate limit
try:
    rl = gh.get_rate_limit()
except:
    print("I am", token)
    sleep(10000)
rate_limit = rl.core.remaining - 100
time_buffer = 5


# Writes the infos stores in deps[i] to a csv
def write_to_csv(infos, n=0):
    with open(exec_space + "data" + str(n) + ".csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(infos)


# Downloads a pom and writes its contents to buf
def get_pom(url, buf):
    try:
        response = requests.get(url + "pom.xml")
    except requests.ConnectionError:
        other_probs.write(url + ": connection error")
        return(-1)

    if response.ok:
        with open(buf, "w") as f:
            f.write(response.text)
            return(0)
    else:
        return(-1)


def wait_till_reset():
    global rate_limit

    now = datetime.datetime(year=1, month=1, day=1).now(
        datetime.timezone.utc).replace(microsecond=0, tzinfo=None)
    rl = gh.get_rate_limit()
    reset = rl.core.reset
    if(reset > now):
        wait = reset - now
    else:
        wait = datetime.timedelta()
    print("Going to sleep till API reset", wait)
    sleep(wait.total_seconds() + time_buffer)
    print("API has reset")
    rl = gh.get_rate_limit()
    rate_limit = rl.core.remaining - 100


# Scan a whole repo
def scan_repo(foundRepo, n=0, ident=0):
    global rate_limit

    if rate_limit <= 0:
        wait_till_reset()

    full_name = foundRepo.full_name
    rate_limit -= 1

#    print(str(n) + ": Looking for pom in " + full_name)

    pom_name = "pom" + str(ident) + ".xml"

    # Check if it has a pom
    url = 'https://raw.githubusercontent.com/' + \
        full_name + '/master/'

    if get_pom(url, exec_space + pom_name) < 0:
        return(False, full_name)
    else:
        return(True, full_name)


def get_query(query):
    rate_limit = gh.get_rate_limit()
    if rate_limit.search.remaining == 0:
        sleep(60)

    return(gh.search_repositories(query=query))


def main():
    n_intervals = len(intervals)

    for i in range(n_intervals):
        repos = get_query(intervals[i])
        infos = []

        for repo in repos:
            info, name = scan_repo(repo)

            if info:
                infos.append(name)
        write_to_csv(infos, i)

    print("All done !")


main()
