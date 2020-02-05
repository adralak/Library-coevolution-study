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
if len(argv) < 3:
    print("Not enough arguments !")
    exit(1)
token = argv[1]
interval = argv[2]
gh = Github(token, per_page=1000)

# These variables help filter which repos are seen
REPO_QUERY = 'language:java stars:>40000'  # pushed:>2016-12'
STARS_MIN = 40000
STARS_MAX = 2000000
max_date = datetime.datetime(year=2018, day=6, month=9)

# Number of parent threads working on repos
n_threads = 5
# Number of children threads working on modules
n_mod_threads = 15

# Output
deps = [[] for i in range(n_threads)]

# Where to write the poms to
exec_space = "exec_space" + token + "/"
list_dir = os.listdir()
if exec_space not in list_dir:
    os.mkdir(exec_space)

# For handling problematic repos
exceptions = open(exec_space + "exceptions" + token + ".txt", "w")
is_exception = [False for i in range(n_threads)]
other_probs = open(exec_space + "errors" + token + ".txt", "w")


# Handle rate limit
rl = gh.get_rate_limit()
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


# Gets the value of a text node
def get_value(data, props):
    if data[0] == '$':
        if data[2:-1] in props:
            return(props[data[2:-1]])
        else:
            #            print("Missing: " + data[2:-1])
            return([-1])
    else:
        return(data)


# Scans a pom for dependencies and modules
def scan_pom(pom, n=0, props={}):
    deps = []

    dom = minidom.parse(pom)
    dependencies = dom.getElementsByTagName("dependency")
    tmp_modules = dom.getElementsByTagName("module")
    tmp_properties = dom.getElementsByTagName("properties")
    modules = [m.firstChild.data for m in tmp_modules]

    if tmp_properties.length > 0:
        for node in tmp_properties.item(0).childNodes:
            if node.hasChildNodes():
                key = node.nodeName
                data = node.firstChild.data

                if key in props and data != props[key]:
                    return([-1], [key])
                else:
                    props[key] = data

    if dependencies.length == 0:
        return([], modules)

    for depend in dependencies:
        info = ["groupId", "artifactId", "version"]
        for dep in depend.childNodes:
            if not dep.hasChildNodes():
                continue

            if dep.nodeName == "groupId":
                v = get_value(dep.firstChild.data, props)
                if v == [-1]:
                    return([-2], [-2])
                info[0] = v

            if dep.nodeName == "artifactId":
                v = get_value(dep.firstChild.data, props)
                if v == [-1]:
                    return([-2], [-2])
                info[1] = v

            if dep.nodeName == "version":
                v = get_value(dep.firstChild.data, props)
                if v == [-1]:
                    return([-2], [-2])
                info[2] = v

        deps.append(info)

#    print(deps)
    return(deps, modules)


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


# Gets the pom of a module and scans in for dependencies and submodules
def scan_module(url, pom_name, queue, n=0, m=0, base_url="", props={}):
    #    print("In scan_module")
    if get_pom(url, exec_space + "module_" + str(m) + pom_name) < 0:
        return()

    try:
        m_deps, m_mods = scan_pom(
            exec_space + "module_" + str(m) + pom_name, n, props)
    except:
        #        print(url)
        exceptions.write(url + ": exception raised in scan_pom")
        return()

    if m_deps == [-1]:
        exceptions.write(url + ": rewrite of property " + m_mods[0])
        is_exception[n] = True
        return()
    elif m_deps == [-2]:
        exceptions.write(url + ": missing key")
        is_exception[n] = True
        return()

    if m_deps != []:
        deps[n] += m_deps

    for mod in m_mods:
        if mod != -2:
            queue.put(url + mod + "/")

#  print("Out of scan_module")


# Class for the children threads
class Module_scanner(Thread):
    def __init__(self, queue, n, m, base_url, props):
        Thread.__init__(self)
        self.queue = queue
        self.n = n
        self.m = m
        self.pom_name = "pom" + str(self.n) + ".xml"
        self.base_url = base_url
        self.props = props

    def run(self):
        self.pom_name = str(self.ident) + self.pom_name
        while True:
            #            print(self.queue.empty())
            url = self.queue.get()
            if url is None:
                break

            scan_module(url, self.pom_name, self.queue, self.n,
                        self.m, self.base_url, self.props)

            self.queue.task_done()


# Reduces a list of list to a list
def red(s):
    try:
        r = [x for i in range(len(s)) for x in s[i]]
    except TypeError:
        r1 = list(filter(lambda a: a != -1, s))
        r2 = list(filter(lambda a: a != -2, r1))
        # print(s) #with -1 -2
        # print(r2) #without -1 -2
        return [x for i in range(len(r2)) for x in r2[i]]
    return [x for i in range(len(s)) for x in s[i]]


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


def scan_repo(foundRepo, n=0):
    global rate_limit
    global deps

    mutex.acquire()

    if rate_limit <= 0:
        wait_till_reset()

    full_name = foundRepo.full_name
    rate_limit -= 1

    mutex.release()

#    print(str(n) + ": Looking for pom in " + full_name)

    pom_name = "pom" + str(n) + ".xml"

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

    if num_queries >= 5000:
        exceptions.write(url + ": Too many API requests")
        is_exception[n] = True
        return()

    rate_limit -= num_queries

    if rate_limit <= 0:
        wait_till_reset()

    mutex.release()

#    print('Inspecting', full_name)

    base_url = 'https://raw.githubusercontent.com/' + \
        full_name + "/"
    repo_deps = []
    star_count = foundRepo.stargazers_count
    m_q = Queue()
    m_scanners = []
    props = {}

    # Spawn children
    for i in range(n_mod_threads):
        scanner = Module_scanner(m_q, n, i, base_url, props)
        scanner.daemon = True
        m_scanners.append(scanner)
        scanner.start()

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
        if get_pom(url, exec_space + pom_name) < 0:
            continue
        min_info = get_min_info(exec_space + pom_name)

        if min_info == []:
            exceptions.write(url + ": parent pom has parent")
            is_exception[n] = True
            break

        props["project.groupId"] = min_info[0]
        props["project.artifactId"] = min_info[1]
        props["project.version"] = min_info[2]

        r_deps, r_modules = scan_pom(exec_space + pom_name, n, props)

        # If an error occured, skip this repo and write it to a list
        if r_deps == [-1]:
            exceptions.write(url + ": rewrite of property")
            is_exception[n] = True
            break
        elif r_deps == [-2]:
            exceptions.write(url + ": missing key")
            is_exception[n] = True
            break

        deps[n] += r_deps

        # Give the children work: one url = one pom from a module
        base_url_h = base_url + h + "/"

        if r_modules != []:
            #            print(r_modules)
            for m in r_modules:
                m_q.put(base_url_h + m + "/")

            # Wait for the children to finish
            m_q.join()

#        print("Done with " + str(h))

        # Add the info + dependencies to the output list
        repo_deps.append([star_count] + min_info + red(deps[n]))
        # Reset deps and props to avoid trouble
        deps[n] = []
        props = {}

    # Stop worker threads
    for i in range(n_mod_threads):
        m_q.put(None)
    for t in m_scanners:
        t.join()

    # Write the data to a csv
    if not is_exception[n]:
        write_to_csv(repo_deps, n)

    is_exception[n] = False


# Mother thread class
class Repo_scanner(Thread):
    def __init__(self, queue, n):
        Thread.__init__(self)
        self.queue = queue
        self.n = n

    def run(self):
        sleep(2)
        while True:
            #            print("New repo")
            repo = self.queue.get()
            if repo is None:
                break
            scan_repo(repo, self.n)
            self.queue.task_done()


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
    jobs.put(interval)

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

    print("All done !")


main()
