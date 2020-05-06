from bs4 import BeautifulSoup
from xml.dom import minidom
import requests
import csv
import datetime
from threading import Thread
from time import sleep
from sys import argv
import os
import copy

# Get to_handle from user and log in
if len(argv) < 2:
    print("Not enough arguments !")
    exit(1)
to_handle = argv[1]

# Where to write the poms to
exec_space = "dataResult/" + to_handle + "/"
data_dir = "data/"
try:
    os.mkdir(exec_space)
except:
    ()

# For handling problematic repos
parentpom = open(exec_space + "parentpom" + to_handle + ".txt", "w")
exceptions = open(exec_space + "exceptions" + to_handle + ".txt", "w")
other_probs = open(exec_space + "errors" + to_handle + ".txt", "w")
n_prob_poms = 0
donefiles = open(exec_space + "All-Done-Files.txt", "w")

# Writes the infos stores in deps[i] to a csv


def write_to_csv(infos, to_handle=""):
    with open(exec_space + to_handle + "_dependecies.csv", 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(infos)


# Gets the value of a text node
def get_value(data, props):
    if data[0] == '$':
        #print('searching for key = ' , data[2:-1])
        if data[2:-1] in props:
            #print('found value for key = ' , props[data[2:-1]])
            return(props[data[2:-1]])
        else:
            #            print("Missing: " + data[2:-1])
            return([-1])
    else:
        return(data)

# Gets the groupId, artifactId and version out of a given pom
def get_min_info(path, pom):

    with open(path + pom, 'r') as pomFile:
        soup = BeautifulSoup(pomFile, 'lxml')

    groupId, artifactId, version, packaging = None, None, None, None
    parentGID, parentV = None, None

    children = soup.project
    if children == None:
        return([None, None, None, None])
    for c in children:
        if c.name == "parent":

            for n in c.contents: #I only store the parent groupId and version in case they are not declared in the pom, the artefact is mandatory for children
                if n.name == "groupid":
                    parentGID = n.string.replace(" ", "")#here and below, it is because some times there is " ", eg, " v3.2" while in modules there might be "v3.2", so if we compare them (we do below for parents), we must not get it wrong  
                elif n.name == "version":
                    parentV = n.string.replace(" ", "")

        elif c.name == "groupid":
            groupId = c.string.replace(" ", "")
        elif c.name == "artifactid":
            artifactId = c.string.replace(" ", "")
        elif c.name == "version":
            version = c.string.replace(" ", "")
        elif c.name == "packaging":
            packaging = c.string.replace(" ", "")

    #print("parent", parentGID, parentV, "\n")
    #print("pom", groupId, artifactId, version, "\n")

    #here i use the parent groupId and version if not declared in the pom
    if (groupId is not None) and (version is not None):
        min_info = [groupId, artifactId, version, packaging]
        return(min_info)
    elif (groupId is not None) and (version is None):
        min_info = [groupId, artifactId, parentV, packaging]
        return(min_info)
    elif (groupId is None) and (version is not None):
        min_info = [parentGID, artifactId, version, packaging]
        return(min_info)
    elif (groupId is None) and (version is None):
        min_info = [parentGID, artifactId, parentV, packaging]
        return(min_info)


# Try to find parent pom in maven central and download its contents to buf
# this should be called recursively to get dependecies and properties of all pom parents
# takes the parent node,
def get_parent_pom_from_maven(path, pom, parent, props, url):

    maven_repos = ['https://repo1.maven.org/maven2/', 'https://repo.spring.io/plugins-release/', 'https://repo.spring.io/libs-milestone/', 'https://repo.spring.io/libs-release/', 'https://repo.jenkins-ci.org/releases', 'https://repo.jenkins-ci.org/incrementals/', 'https://repository.mulesoft.org/nexus/content/repositories/public/', 'https://repository.cloudera.com/artifactory/public', 'https://repository.cloudera.com/artifactory/cloudera-repos/', 'https://repo.hortonworks.com/content/repositories/releases/', 'https://packages.atlassian.com/content/repositories/atlassian-public/', 'https://jcenter.bintray.com/', 'https://repository.jboss.org/nexus/content/repositories/ea/', 'https://repository.jboss.org/nexus/content/repositories/releases/', 'https://maven.wso2.org/nexus/content/repositories/releases/', 'https://maven.wso2.org/nexus/content/repositories/public/', 'https://maven.wso2.org/nexus/content/repositories/', 'https://maven.xwiki.org/releases/', 'https://maven-eu.nuxeo.org/nexus/content/repositories/public-releases/', 'https://maven-eu.nuxeo.org/nexus/content/repositories/', 'https://dl.bintray.com/kotlin/kotlin-dev/', 'https://repo.clojars.org/', 'http://maven.geomajas.org/nexus/content/groups/public/', 'https://plugins.gradle.org/m2/', 'https://dl.bintray.com/spinnaker/spinnaker/', 'https://maven.ibiblio.org/maven2/', 'https://philanthropist.touk.pl/nexus/content/repositories/releases/', 'https://clojars.org/', 'http://maven.jahia.org/maven2/', 'https://repository.mulesoft.org/releases/', 'https://build.surfconext.nl/repository/public/releases/', 'https://build.openconext.org/repository/public/releases/']

    for mvn_repo in maven_repos:

        parentGID, parentAID, parentV = '', '', ''
        #print('\n content parent in parent', parent.contents)
        for c in parent.contents:
            if c.name == "groupid":
                # here because the GID is sub folders in the link
                parentGID = c.string.replace(" ", "").replace(".", "/")
            elif c.name == "artifactid":
                parentAID = c.string.replace(" ", "")
            elif c.name == "version":
                parentV = c.string.replace(" ", "")

        url_parent_pom = mvn_repo + parentGID + "/" + parentAID + "/" + parentV + "/" + parentAID + "-" + parentV + ".pom"

        try:
            response = requests.get(url_parent_pom)  # the links contains .pom
        except requests.ConnectionError:
            #other_probs.write(url_parent_pom + " : url does not exist \n")
            pass #this does nothing

        if response.ok:
            #print(url_parent_pom)
            with open(path + pom, "w") as f:
                f.write(response.text)
                f.close()
            parent_deps, parent_mods = scan_pom(path, pom, url, False, props)
            return(parent_deps, parent_mods)

    parentpom.write(url + "pom.xml : parent pom does not exist" + "\n") #here it means that no parent is found, better to ignore it and continue
    return([], [])


# Scans a pom for dependencies and modules
def scan_pom(path, pom, url, in_module=True, props={}):
    deps = []

    #dom = minidom.parse(path + pom)
    with open(path + pom, 'r') as pomFile:
        soup = BeautifulSoup(pomFile, 'lxml')
    dependencies = soup.find_all('dependency') #dom.getElementsByTagName("dependency")
    parent = soup.find_all('parent') #dom.getElementsByTagName("parent")
    tmp_modules = soup.find_all('module') #dom.getElementsByTagName("module")
    tmp_properties = soup.find_all('properties') #dom.getElementsByTagName("properties")
    modules = []
    modules = []
    p_deps, p_mods = [], []

    
    for m in tmp_modules:
    
        modules.append(m.string.replace(" ", ""))
    
    if parent !=[]: # is not None: #.length > 0:
        if not in_module:
            p_deps, p_mods = get_parent_pom_from_maven(path, "parent_" + pom, parent[0], props, url)

        parentGID, parentAID, parentV = '', '', ''
        
        for c in parent[0].contents: #item(0).childNodes:
            if c.name is not None:
                first_key = "project.parent." + c.name
                second_key = "parent." + c.name
                data = c.string.replace(" ", "")
                props[first_key] = data
                props[second_key] = data

            if c.name == "groupid":
                parentGID = c.string.replace(" ", "")
            elif c.name == "artifactid":
                parentAID = c.string.replace(" ", "")
            elif c.name == "version":
                parentV = c.string.replace(" ", "")

        #((props["parent.groupId"] != props["project.groupId"]) or (props["parent.artifactId"] != props["project.artifactId"]) or (props["parent.version"] != props["project.version"])):
        if in_module and ((parentGID != props["project.groupId"]) or (parentAID != props["project.artifactId"]) or (parentV != props["project.version"])):
            #print(url)
            #exceptions.write(url + ": module and his parent is not the project root" + "\n")
            p_deps, p_mods = get_parent_pom_from_maven(path, "parent_" + pom, parent[0], props, url)

    
    if tmp_properties != []:  #is not None: #.length > 0:
        for properties in tmp_properties:
            for propertiesTag in properties:
                if (propertiesTag.name is not None) and (propertiesTag.string is not None):
                    
                    key = propertiesTag.name
                    data = propertiesTag.string.replace(" ", "")
                    props[key] = data
                    

    deps += p_deps

    #if p_mods != [] and not in_module:
        #return([-3], [-3])

    if dependencies == []: #.length == 0:
        return(deps, modules)


    #todo deal with dependencyManagement and their deps at pom root, also deal with redundant deps
    
    for depend in dependencies:
        
        info = ["groupId", "artifactId", "version"]
        for dep in depend.contents: #childNodes:
            #if dep is None:
                #continue

            if dep.name == "groupid":
                v = get_value(dep.string.replace(" ", ""), props)
                if v == [-1]:
                    info[0] = dep.string.replace(" ", "")
                    exceptions.write(url + ": missing key " + dep.string + "\n")
                    #return([-2], [dep.firstChild.data[2:-1]])
                else:
                    info[0] = v

            if dep.name == "artifactid":
                v = get_value(dep.string.replace(" ", ""), props)
                if v == [-1]:
                    info[1] = dep.string.replace(" ", "")
                    exceptions.write(url + ": missing key " + dep.string + "\n")
                    #return([-2], [dep.firstChild.data[2:-1]])
                else:
                    info[1] = v

            if dep.name == "version":
                v = get_value(dep.string.replace(" ", ""), props)
                if v == [-1]:
                    info[2] = dep.string.replace(" ", "")
                    exceptions.write(url + ": missing key " + dep.string + "\n")
                    #return([-2], [dep.firstChild.data[2:-1]])
                else:
                    info[2] = v

        if info[2] == "version": #it means that the version was not specified, that case it must be in "dependencyManagement" tag, if not then we cannot find it, 
            #deps.append(info)#or ignore it and pass
            pass
        else:
            deps.append(info)

#    print(deps)
    return(deps, modules)



# Downloads a pom and writes its contents to buf
def get_pom(url, buf):
    try:
        response = requests.get(url + "pom.xml")
    except requests.ConnectionError:
        other_probs.write(url + "pom.xml : connection error \n")
        return(-1)

    if response.ok:
        with open(buf, "w") as f:
            f.write(response.text)
            f.close()
            return(0)
    else:
        return(-1)


def write_problem_pom(pom_name):
    global n_prob_poms
    n_prob_poms += 1
    with open(exec_space + pom_name, "r") as pom:
        with open(exec_space + "prob_pom" + str(n_prob_poms) + ".xml", "w") as prob:
            for line in pom:
                prob.write(line)


# Gets the pom of a module and scans in for dependencies and submodules
def scan_module(url, pom_name, stack, props={}):

    #    print("In scan_module")
    if get_pom(url, exec_space + "module_" + pom_name) < 0:
        return()
    m_deps, m_mods = None, None
    try:
        m_deps, m_mods = scan_pom(exec_space, "module_" + pom_name, url, True, props=props)
    except Exception as err:
        exceptions.write(url + "pom.xml : exception raised in scan_module" + "\n") #" -- " + err +
        #write_problem_pom("module_" + pom_name)
        #return(None)

    if (m_deps is not None) and (m_deps == [-1]):
        exceptions.write(url + "pom.xml : rewrite of property " + m_mods[0] + "\n")
        #return(None)
    elif (m_deps is not None) and (m_deps == [-2]):
        exceptions.write(url + "pom.xml : missing key " + m_mods[0] + "\n")
        #return(None)

    if m_mods is not None:
        for mod in m_mods:
            if mod != -2:
                try:
                    min_info = get_min_info(exec_space, "module_" + pom_name)
                    c_props = copy.deepcopy(props)
                    c_props["project.groupId"] = min_info[0]
                    c_props["project.artifactId"] = min_info[1]
                    c_props["project.version"] = min_info[2]
                    c_props["project.packaging"] = min_info[3]

                except Exception as err:
                    exceptions.write(url + "pom.xml : exception raised in scan_module" + "\n") #print("error ", err, "in ", url)
                #print("module min_info = ", min_info)

                mm_deps = scan_module(url + mod + "/", "module_" + pom_name, stack, props=c_props)

                if mm_deps is not None: #try:
                    m_deps += mm_deps
            #except:
                #print('mm_deps ', mm_deps, '\n')
                #print('m_deps ', m_deps, '\n')             
            #stack.append(url + mod + "/")

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
def scan_repo(url):
    global deps

    #print("Inspecting", url)

    pom_name = "pom.xml"
    is_exception = False
    repo_deps = []
    props = {}
    m_q = []

    if get_pom(url, exec_space + pom_name) < 0:
        return(None)

    try:
        min_info = get_min_info(exec_space, pom_name)
        props["project.groupId"] = min_info[0]
        props["project.artifactId"] = min_info[1]
        props["project.version"] = min_info[2]
        props["project.packaging"] = min_info[3]

        r_deps, r_modules = scan_pom(exec_space, pom_name, url, False, props)
    except Exception as err:
        exceptions.write(url + "pom.xml : exception raised in scan_repo" + "\n") #print("error ", err, "in ", url)
        #write_problem_pom(pom_name)
        return(None)

    # If an error occured, skip this repo and write it to a list
    if r_deps == [-1]:
        exceptions.write(url + "pom.xml : rewrite of property" + r_modules[0] + "\n")
        is_exception = True
        return(None)
    elif r_deps == [-2]:
        exceptions.write(url + "pom.xml : missing key" + r_modules[0] + "\n")
        is_exception = True
        return(None)
    elif r_deps == [-3]:
        exceptions.write(url + "pom.xml : parent pom has parent with modules!\n")
        is_exception = True
        return(None)

    repo_deps += r_deps

    if r_modules is not None:
        for m in r_modules:
            m_q.append(url + m + "/")

    while m_q != []:
        module = m_q.pop()

        m_deps = scan_module(module, pom_name, m_q, props=props)

        if m_deps is not None:
            repo_deps += m_deps

    # Write the data to a csv
    return(min_info + repo_deps)
    
    #if not is_exception:
        #return(min_info + repo_deps)
    #else:
        #return(None)


def main():
    repo_urls = []

    print(to_handle)
    with open(data_dir + to_handle, 'r', newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) > 2:
                repo_urls.append([row[0][23:], row[0], row[1]] + row[2:])

    all_deps = []
    seen = []

    for urls in repo_urls:
        for url in urls[3:]:
            if len(url) < 34 or url in seen:
                continue
            seen.append(url)
            deps = scan_repo(url)
            if deps is None:
                continue
            all_deps.append([urls[0], urls[2], url] + deps)

    write_to_csv(all_deps, to_handle)

    
    donefiles.write("Done for :" + to_handle +"\n")

main()
# scan_pom(exec_space + "prob_pom1.xml")
