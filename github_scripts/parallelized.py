from github import Github
from xml.dom import minidom
import requests
import csv
import datetime
from threading import Thread
from queue import Queue
from time import sleep


# Get token from user and log in
token = input("Prompt")
gh = Github(token)

# These variables help filter which repos are seen
REPO_QUERY = 'language:java stars:>40000'  # pushed:>2016-12'
STARS_MIN = 40000
STARS_MAX = 2000000
max_date = datetime.datetime(year=2018, day=6, month=9)

# Number of parent threads working on repos
n_threads = 10
# Number of children threads working on modules
n_mod_threads = 15

# Keep track of the threads
r_scanners = []
m_scanners = [[] for i in range(n_threads)]

# Output
deps = [[] for i in range(n_threads)]

# Children threads queues
m_q = [Queue() for i in range(n_threads)]

# Properties of each repo
props = [{} for i in range(n_threads)]

# For handling problematic repos
exceptions = []

# Where to write the poms to
exec_space = "exec_space/"


# Writes the infos stores in deps[i] to a csv
def write_to_csv(infos, n=0):
    print("Writing...")
    print(infos)
    with open("data" + str(n) + ".csv", 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(infos)
    print("Done !")


# Gets the groupId, artifactId and version out of a given pom
def get_min_info(pom, n=0):
    dom = minidom.parse(pom)
    groupId = dom.getElementsByTagName("groupId")
    artifactId = dom.getElementsByTagName("artifactId")
    version = dom.getElementsByTagName("version")
    min_info = [groupId[0].firstChild.data, artifactId[0].firstChild.data,
                version[0].firstChild.data]
    return(min_info)


# Gets the value of a text node
def get_value(data, n):
    if data[0] == '$':
        return(props[n][data[2:-1]])
    else:
        return(data)


# Scans a pom for dependencies and modules
def scan_pom(pom, n=0):
    deps = []

    dom = minidom.parse(pom)
    depend = dom.getElementsByTagName("dependency")
    tmp_modules = dom.getElementsByTagName("module")
    tmp_properties = dom.getElementsByTagName("properties")
    modules = [m.firstChild.data for m in tmp_modules]

    if tmp_properties.length > 0:
        for node in tmp_properties.item(0).childNodes:
            if node.hasChildNodes():
                key = node.nodeName
                data = node.firstChild.data

                if key in props[n] and data != props[n][key]:
                    return([-1], [-1])
                else:
                    props[n][key] = data

    for dep in depend:
        info = []

        gpId = dep.getElementsByTagName("groupId")
        if gpId != []:
            info.append(get_value(gpId[0].firstChild.data, n))
        else:
            continue

        artId = dep.getElementsByTagName("artifactId")
        if artId != []:
            info.append(get_value(artId[0].firstChild.data, n))
        else:
            continue

        version = dep.getElementsByTagName("version")
        if version != []:
            info.append(get_value(version[0].firstChild.data, n))
        else:
            continue
        deps.append(info)

#    print(deps)
    return(deps, modules)


# Downloads a pom and writes its contents to buf
def get_pom(url, buf):
    response = requests.get(url)

    if response.ok:
        with open(buf, "w") as f:
            f.write(response.text)
            return(0)
    else:
        return(-1)


# Gets the pom of a module and scans in for dependencies and submodules
def scan_module(url, pom_name, n=0, m=0, base_url=""):
    if get_pom(url, exec_space + "module_" + str(m) + pom_name) < 0:
        return()

    try:
        m_deps, m_mods = scan_pom(
            exec_space + "module_" + str(m) + pom_name, n)
    except:
        print(url)
        with open(exec_space + "module_" + str(m) + pom_name, "r") as f:
            with open("../pb_pom" + str(n) + str(m) + ".xml", "w") as g:
                for line in f:
                    g.write(line)
        return()

    if m_deps == [-1]:
        exceptions.append(base_url)

    if m_deps != []:
        deps[n] += m_deps

        for mod in m_mods:
            m_q[n].put(url + "/" + mod)


# Class for the children threads
class Module_scanner(Thread):
    def __init__(self, queue, n, m, base_url):
        Thread.__init__(self)
        self.queue = queue
        self.n = n
        self.m = m
        self.pom_name = "pom" + str(self.n) + ".xml"
        self.base_url = base_url

    def run(self):
        self.pom_name = str(self.ident) + self.pom_name
        while True:
            url = self.queue.get()
            if url is None:
                break
            scan_module(url, self.pom_name, self.n, self.m, self.base_url)
            self.queue.task_done()


# Reduces a list of list to a list
def red(s):
    return [x for i in range(len(s)) for x in s[i]]


# Scan a whole repo
def scan_repo(foundRepo, n=0):
    # First, check if it is the star range we're interested in
    if foundRepo.stargazers_count < STARS_MIN \
       or foundRepo.stargazers_count > STARS_MAX:
        return()

    print(str(n) + ": Looking for pom in " + foundRepo.full_name)

    url = 'https://raw.githubusercontent.com/' + \
        foundRepo.full_name + '/master/pom.xml'
    pom_name = "pom" + str(n) + ".xml"

    # Check if it has a pom
    if get_pom(url, exec_space + pom_name) < 0:
        return()

    print('Inspecting', foundRepo.name)

    base_url = 'https://raw.githubusercontent.com/' + \
        foundRepo.full_name + "/"
    repo_deps = []

    # Spawn children
    for i in range(n_mod_threads):
        scanner = Module_scanner(m_q[n], n, i, base_url)
        scanner.daemon = True
        m_scanners[n].append(scanner)
        scanner.start()

    # Iterate over releases
    for release in foundRepo.get_tags():
        if base_url in exceptions:
            deps[n] = []
            props[n] = {}
            break

        h = release.commit.sha
        git_tag = foundRepo.get_git_commit(h)
        date = git_tag.committer.date
        print(date)

        # If it was released after the MDG snapshot, it is ignored
        if date > max_date:
            continue

        # Get the infos out of the master pom
        url = base_url + h + "/pom.xml"
        get_pom(url, pom_name)
        min_info = get_min_info(pom_name)
        r_deps, r_modules = scan_pom(pom_name, n)

        if "project.groupId" not in props:
            props[n]["project.groupId"] = min_info[0]
            props[n]["project.artifactId"] = min_info[1]
            props[n]["project.version"] = min_info[2]

        # If an error occured, skip this repo and write it to a list
        if r_deps == [-1]:
            exceptions.append(base_url)
            deps[n] = []
            props[n] = {}
            break

        # Give the children work: one url = one pom from a module
        base_url_h = base_url + h + "/"
        for m in r_modules:
            m_q[n].put(base_url_h + m + "/pom.xml")

        # Wait for the children to finish
        m_q[n].join()

        print("Done with " + str(h))

        # Add the info + dependencies to the output list
        repo_deps.append(min_info + red(deps[n]))
        # Reset deps and props to avoid trouble
        deps[n] = []
        min_info = [props[n]["project.groupId"], props[n]
                    ["project.artifactId"], props[n]["project.version"]]
        props[n] = {}
        props[n]["project.groupId"] = min_info[0]
        props[n]["project.artifactId"] = min_info[1]
        props[n]["project.version"] = min_info[2]

    props[n] = {}
    # Stop worker threads
    for i in range(n_mod_threads):
        m_q[n].put(None)
    for t in m_scanners[n]:
        t.join()

    # Write the data to a csv
    if base_url not in exceptions:
        write_to_csv(repo_deps)


# Mother thread class


class Repo_scanner(Thread):
    def __init__(self, queue, n):
        Thread.__init__(self)
        self.queue = queue
        self.n = n

    def run(self):
        while True:
            repo = self.queue.get()
            if repo is None:
                break
            scan_repo(repo, self.n)
            self.queue.task_done()


def main():
    # Get the repos filtered somewhat
    repos = gh.search_repositories(query=REPO_QUERY)
    q = Queue()

    # Spawn threads
    for i in range(n_threads):
        scanner = Repo_scanner(q, i)
        scanner.daemon = True
        r_scanners.append(scanner)
        scanner.start()

    # Give the threads work to do
    for foundRepo in repos:
        q.put(foundRepo)

    # Wait for the work to be done
    q.join()

    # Stop worker threads
    for i in range(n_threads):
        q.put(None)
    for t in r_scanners:
        t.join()

    with open(exec_space + "exceptions", "w") as f:
        for pb in exceptions:
            f.write(pb)

    print("All done !")


# a, b = scan_pom("../pb_pom.xml")
main()
