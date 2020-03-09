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
if len(argv) < 4:
    print("Not enough arguments !")
    exit(1)
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

# Number of parent threads working on repos
n_threads = 20

# Output
deps = [[] for i in range(n_threads)]

# Where to write the poms to
exec_space = "exec_space" + token + "/"
try:
    os.mkdir(exec_space)
except:
    ()

# For handling problematic repos
exceptions = open(exec_space + "exceptions" + token + ".txt", "w")
is_exception = [False for i in range(n_threads)]
other_probs = open(exec_space + "errors" + token + ".txt", "w")


# Handle rate limit
try:
    rl = gh.get_rate_limit()
except:
    print("I am", token)
    sleep(10000)
rate_limit = rl.core.remaining - 100
mutex = Lock()
time_buffer = 5


# Writes the infos stores in deps[i] to a csv
def write_to_csv(infos, n=0):
    with open(exec_space + "data" + str(n) + ".csv", 'a', newline='') as f:
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

    mutex.acquire()

    if rate_limit <= 0:
        wait_till_reset()

    full_name = foundRepo.full_name
    rate_limit -= 1

    mutex.release()

#    print(str(n) + ": Looking for pom in " + full_name)

    pom_name = "pom" + str(ident) + ".xml"

    # Check if it has a pom
    url = 'https://raw.githubusercontent.com/' + \
        full_name + '/master/'

    if get_pom(url, exec_space + pom_name) < 0:
        return()
    print('in repo', full_name)
    # Handle rate limit
    mutex.acquire()
    if rate_limit <= 0:
        wait_till_reset()

    tags = foundRepo.get_tags()
    num_queries = tags.totalCount + 1

    if num_queries >= 4900:
        exceptions.write(url + ": Too many API requests")
        is_exception[n] = True
        return()

    rate_limit -= num_queries

    if rate_limit <= 0:
        wait_till_reset()

    rate_limit -= num_queries

    mutex.release()

#    print('Inspecting', full_name)

    base_url = 'https://raw.githubusercontent.com/' + \
        full_name + "/"
    star_count = foundRepo.stargazers_count
    urls = []

    # Iterate over releases
    for release in tags:
        if is_exception[n]:
            break

        h = release.commit.sha
        git_tag = foundRepo.get_git_commit(h)
        date = git_tag.committer.date

        # If it was released after the MDG snapshot, it is ignored
        if date > max_date:
            continue

        # Get the infos out of the master pom
        url = base_url + h + "/"
        urls.append(url)

    # Write the data to a csv
    if not is_exception[n]:
        return(["https://www.github.com/" + full_name, star_count] + urls)
    else:
        is_exception[n] = False
        return(None)


# Mother thread class
class Repo_scanner(Thread):
    def __init__(self, queue, n):
        Thread.__init__(self)
        self.queue = queue
        self.n = n

    def run(self):
        sleep(2)
        infos = []
        while True:
            #            print("New repo")
            repo = self.queue.get()
            if repo is None:
                break
            info = scan_repo(repo, self.n, self.ident)
            if info is None:
                continue
            else:
                infos.append(info)
            self.queue.task_done()
        write_to_csv(infos, self.ident)


def get_query(query):
    rate_limit = gh.get_rate_limit()
    if rate_limit.search.remaining == 0:
        sleep(60)

    return(gh.search_repositories(query=query))


class Job_giver(Thread):
    def __init__(self, queue, jobs):
        Thread.__init__(self)
        self.queue = queue
        self.jobs = jobs

    def run(self):
        while True:
            query = self.jobs.get()
            if query is None:
                break
            repos = get_query(query)
            for r in repos:
                self.queue.put(r)
            self.jobs.task_done()


def main():
    jobs = Queue()
    q = Queue()
    r_scanners = []

    # Spawn threads
    for i in range(n_threads):
        scanner = Repo_scanner(q, i)
        scanner.daemon = True
        r_scanners.append(scanner)
        scanner.start()

    job_giver = Job_giver(q, jobs)
    job_giver.daemon = True
    job_giver.start()

    # Give the threads work to do
    n_intervals = len(intervals)
    for i in [j for j in range(n_intervals) if (j % total == me)]:
        jobs.put(intervals[i])

    # Wait for the work to be done
    jobs.join()
    q.join()

    # Stop worker threads
    for i in range(n_threads):
        q.put(None)
    for t in r_scanners:
        t.join()

    jobs.put(None)
    job_giver.join()

    with open("done" + str(me) + ".txt", "r") as f:
        f.write(str(me) + "is done!")
    print("All done !")


main()
