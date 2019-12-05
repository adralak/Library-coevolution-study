from github3 import GitHub
from urllib.parse import urljoin
from xml.dom import minidom
import requests
import tarfile as tf
import fnmatch
import os
import csv

gh = GitHub()
token = ""
REPO_QUERY = 'language:java stars:>20000'  # pushed:>2016-12'


def write_to_csv(repos_infos):
    infos = []

    for repo in repos_infos:
        repo_infos = repos_infos[repo]

        for info in repo_infos:
            infos.append(info)

    with open("data.csv", 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(infos)


def get_min_info(pom):
    dom = minidom.parse(pom)
    groupId = dom.getElementsByTagName("groupId")
    artifactId = dom.getElementsByTagName("artifactId")
    version = dom.getElementsByTagName("version")
    min_info = [groupId[0].firstChild, artifactId[0].firstChild,
                version[0].firstChild]

    return(min_info)


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


def get_pom(url, buf):
    response = requests.get(url)

    if response.ok:
        with open(buf, "w") as f:
            f.write(response.text)
            return(0)
    else:
        return(-1)


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

        if get_pom(url, "pom.xml") < 0:
            continue

        repos_deps[foundRepo.name] = {}
        print('Inspecting', foundRepo.name)

        base_url = 'https://raw.githubusercontent.com/' + \
            foundRepo.full_name + "/"
        deps = []

        for release in foundRepo.tags():
            h = release.commit.sha
            # print(h)
            url = base_url + h + "/pom.xml"
            get_pom(url, "pom.xml")
            min_info = get_min_info("pom.xml")
            r_deps, r_modules = scan_pom("pom.xml")
            for m in r_modules:
                # print(m)
                url = base_url + h + m + "/pom.xml"
                get_pom(url, "module_pom.xml")
                m_deps, m_mods = scan_pom("module_pom.xml")

                if m_deps != []:
                    r_deps += m_deps

                if m_mods != []:
                    r_modules += [m + "/" + m_mod for m_mod in m_mods]
            deps.append(min_info + r_deps)

        repos_deps[foundRepo.name] = deps

    write_to_csv(repos_deps)


token = input("Prompt")
main()
