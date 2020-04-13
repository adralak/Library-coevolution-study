from xml.dom import minidom
import requests
import csv
import datetime
from threading import Thread
from queue import Queue
from time import sleep
from sys import argv
import os


# Get to_handle from user and log in
if len(argv) < 2:
    print("Not enough arguments !")
    exit(1)
to_handle = argv[1]

# Where to write the poms to
csv_to_handle = to_handle[5:]
exec_space = "exec_space" + csv_to_handle + "/"
data_dir = "data/"
try:
    os.mkdir(exec_space)
except:
    ()

# For handling problematic repos
exceptions = open(exec_space + "exceptions" + csv_to_handle + ".txt", "w")
other_probs = open(exec_space + "errors" + csv_to_handle + ".txt", "w")


# Writes the infos stores in deps[i] to a csv
def write_to_csv(infos, to_handle=""):
    with open(exec_space + "data" + to_handle + ".csv", 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(infos)


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
        return(None)

    if m_deps == [-1]:
        exceptions.write(url + ": rewrite of property " + m_mods[0])
        return(None)
    elif m_deps == [-2]:
        exceptions.write(url + ": missing key")
        return(None)

    for mod in m_mods:
        if mod != -2:
            queue.put(url + mod + "/")

    return(m_deps)


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


# Scan a whole repo
def scan_repo(url, n=0):
    global deps

    print("Inspecting", url)

    pom_name = "pom" + str(n) + ".xml"
    is_exception = False
    repo_deps = []
    props = {}
    m_q = Queue()

    if get_pom(url, exec_space + pom_name) < 0:
        return(None)

    min_info = get_min_info(exec_space + pom_name, n)

    if min_info == []:
        exceptions.write(url + ": parent pom has parent")
        return(None)

    props["project.groupId"] = min_info[0]
    props["project.artifactId"] = min_info[1]
    props["project.version"] = min_info[2]

    r_deps, r_modules = scan_pom(exec_space + pom_name, n, props)

    # If an error occured, skip this repo and write it to a list
    if r_deps == [-1]:
        exceptions.write(url + ": rewrite of property")
        is_exception = True
        return(None)
    elif r_deps == [-2]:
        exceptions.write(url + ": missing key")
        is_exception = True
        return(None)

    repo_deps += r_deps

    for m in r_modules:
        m_q.put(url + m + "/")

    while not m_q.empty():
        try:
            module = m_q.get_nowait()
        except Queue.QueueEmpty:
            break

        m_deps = scan_module(module, pom_name, m_q, props=props)

        if m_deps is None:
            is_exception = True
    # Write the data to a csv
    if not is_exception:
        return(min_info + repo_deps)
    else:
        return(None)


def main():
    repo_urls = []

    with open(to_handle, 'r', newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) > 2:
                repo_urls.append([row[0][24:], row[0], row[1]] + row[2:])

    all_deps = []
    seen = []

    for urls in repo_urls:
        for url in urls[3:]:
            if len(url) < 34 or url in seen:
                continue
            seen.append(url)
            deps = scan_repo(url)
            if deps is None:
                break
            all_deps.append([urls[0], urls[2], url] + deps)
        seen = []

    write_to_csv(all_deps, csv_to_handle)

    print("All done !")


main()
