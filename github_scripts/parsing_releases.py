from github3 import GitHub
from urllib.parse import urljoin
from xml.dom import minidom
import requests
import tarfile as tf
import fnmatch
import os

gh = GitHub()
token = ""
REPO_QUERY = 'language:java stars:>12000'  # pushed:>2016-12'


def scan_pom(pom):
    deps = []

    dom = minidom.parse(pom)
    depend = dom.getElementsByTagName("dependency")
    tmp_modules = dom.getElementsByTagName("module")
    modules = [m.firstChild.data for m in tmp_modules]

    for dep in depend:
        info = []

        gpId = dep.getElementsByTagName("groupId")
        if gpId != []:
            info.append(gpId[0].firstChild.data)
        else:
            continue

        artId = dep.getElementsByTagName("artifactId")
        if artId != []:
            info.append(artId[0].firstChild.data)
        else:
            continue

        version = dep.getElementsByTagName("version")
        if version != []:
            info.append(version[0].firstChild.data)
        else:
            continue
        deps.append(info)

    return(deps, modules)


def main():
    log = gh.login(token)
    # , sort='stars', per_page=100)
    repos = gh.search_repositories(query=REPO_QUERY)
    repos_deps = {}

    for result in repos:
        foundRepo = result.repository

        print("Looking for pom in " + foundRepo.full_name)

        url = 'https://raw.githubusercontent.com/' + \
            foundRepo.full_name + '/master/pom.xml'

        response = requests.get(url)

        if not response.ok:
            continue

        repos_deps[foundRepo.name] = {}
        print('Inspecting', foundRepo.name)

        for release in foundRepo.releases():
            release.archive("tarball", ".")
            files = os.listdir(".")
            for f in files:
                if fnmatch.fnmatch(f, "*.tar*"):
                    with tf.open(f) as tar:
                        membs = tar.getmembers()
                        names = tar.getnames()
                        for i in range(len(membs)):
                            if names[i] == "pom.xml":
                                break
                        tar.extract(membs[i])
                        deps, mods = scan_pom("pom.xml")
                        repos_deps[foundRepo.name][release.name] = deps
        print(repos_deps[foundRepo.name])


token = input("Prompt")
main()
