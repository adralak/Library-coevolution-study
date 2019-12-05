from github3 import GitHub
from urllib.parse import urljoin
from xml.dom import minidom
import requests
# import github3 as gh

gh = GitHub()
token = ""
REPO_QUERY = 'language:java stars:>12000'  # pushed:>2016-12'


def scan_dependencies(url, buf):
    response = requests.get(url)
    deps = []

    if response.ok:
        with open(buf, "w") as f:
            f.write(response.text)

        dom = minidom.parse(buf)
        depend = dom.getElementsByTagName("dependency")

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
    else:
        print("Could not get pom")
    return(deps)


def get_modules(buf):
    dom = minidom.parse(buf)
    modules = dom.getElementsByTagName("module")

    return([m.firstChild.data for m in modules])


def main():
    log = gh.login(token)
    # , sort='stars', per_page=100)
    repos = gh.search_repositories(query=REPO_QUERY)
    repos_deps = {}
    for result in repos:
        foundRepo = result.repository

        for release in foundRepo.releases():
            print(release.name)

        deps = []

        print('Inspecting', foundRepo.full_name)
        url = 'https://raw.githubusercontent.com/' + \
            foundRepo.full_name + '/master/pom.xml'

        response = requests.get(url)

        if not response.ok:
            continue

        deps += scan_dependencies(url, "pom.xml")

        modules = get_modules("pom.xml")

        for m in modules:
            url = "https://raw.githubusercontent.com/" + foundRepo.full_name \
                + "/master/" + m + "/pom.xml"
            new_deps = scan_dependencies(url, "module_pom.xml")
            if new_deps == []:
                continue

            deps += new_deps
            new_modules = get_modules("module_pom.xml")
            modules += [m + "/" + new_m for new_m in new_modules]

        repos_deps[foundRepo.name] = deps

    # TODO
    # get the pom.xml and parse it to find the dependecies
# if __name__ == '__main__':
#    main()
token = input("Prompt")
main()
