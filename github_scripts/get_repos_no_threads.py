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
me = int(argv[2])
total = int(argv[3])
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
exceptions = open(exec_space + "exceptions" + token + ".txt", "a")
other_probs = open(exec_space + "errors" + token + ".txt", "a")

# Handle rate limit
try:
    rl = gh.get_rate_limit()
except:
    print("I am", token)
    sleep(3600)
rate_limit = rl.core.remaining - 100
time_buffer = 120


# Writes the infos stores in deps[i] to a csv
def write_to_csv(infos, q=""):
    with open(exec_space + "data_" + q + ".csv", 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(infos)


# Gets the groupId, artifactId and version out of a given pom
def get_min_info(pom, n=0):
    dom = minidom.parse(pom)
    temp = dom.childNodes
    parent = False

    for c in temp:
        if c.nodeName == "project":
            children = c.childNodes
            break

    for c in children:
        if c.nodeName == "parent":
            parent = True
            break
        if c.nodeName == "groupId":
            groupId = c
        elif c.nodeName == "artifactId":
            artifactId = c
        elif c.nodeName == "version":
            version = c

    if not parent:
        min_info = [groupId.firstChild.data, artifactId.firstChild.data,
                    version.firstChild.data]

        return(min_info)
    else:
        return([])


# Downloads a pom and writes its contents to buf
def get_pom(url, buf):
    try:
        response = requests.get(url + "pom.xml")
    except requests.ConnectionError:
        other_probs.write(url + ": connection error \n")
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
    #rl = gh.get_rate_limit()
    try:
        rl = gh.get_rate_limit()
    except:
        print("Going to sleep for 1h due error in rl = gh.get_rate_limit()")
        sleep(3600)
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
        return(None)  # return(False, full_name)
    # else:
    # return(True, full_name)
    # Comment the rest below
    print('in repo', full_name)
    # Handle rate limit

    if rate_limit <= 0:
        wait_till_reset()

    tags = foundRepo.get_tags()
    num_queries = 3 * tags.totalCount + 3

    if num_queries >= 4900:
        exceptions.write(url + ": Too many API requests \n")
        return(None)

    rate_limit -= num_queries

    if rate_limit <= 0:
        wait_till_reset()

    rate_limit -= num_queries

#    print('Inspecting', full_name)

    base_url = 'https://raw.githubusercontent.com/' + \
        full_name + "/"
    star_count = foundRepo.stargazers_count
    urls = []

    # Iterate over releases
    for release in tags:
        h = release.commit.sha
        #git_tag = foundRepo.get_git_commit(h)
		#handle error from getting the commit, it happens sometimes
        try:
            git_tag = foundRepo.get_git_commit(h)
        except:
            print("encountered error in git_tag = foundRepo.get_git_commit(h) for "+full_name)
            other_probs.write("https://github.com/" + full_name + " : error in gettign a comlit h \n")
            continue
			#sleep(3600)
        date = git_tag.committer.date

        # If it was released after the MDG snapshot, it is ignored
        if date > max_date:
            continue

        # Get the infos out of the master pom
        url = base_url + h + "/"
        urls.append(url)

    # Write the data to a csv
    return(["https://www.github.com/" + full_name, star_count] + urls)


def get_query(query):
    rate_limit = gh.get_rate_limit()
    if rate_limit.search.remaining == 0:
        sleep(60)

    return(gh.search_repositories(query=query))


def main():
    n_intervals = len(intervals)

    for i in range(n_intervals):
        if i % total != me:
            continue

        repos = get_query(intervals[i])
        infos = []

        for repo in repos:
            info = scan_repo(repo)

            if info is None:  # if info:
                continue  # infos.append(name)
            # Comment following line
            infos.append(info)
        write_to_csv(infos, intervals[i])

    print("All done !")


main()
