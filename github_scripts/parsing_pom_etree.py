from github3 import login
from time import sleep
from urllib.parse import urljoin
import requests
from lxml import etree
from check_multimodule import get_repos

def main():

    single_module = []

    for repo in get_repos():
        print(repo) # Progress reporting
        url = f'https://raw.githubusercontent.com/{repo}/master/pom.xml'
        item = (repo, url)
        response = requests.get(url)
        if not response.ok:
            print("?=>", repo)
            continue
        doc = etree.fromstring(response.content)
        root = doc.getroottree()
        packaging = root.find('{http://maven.apache.org/POM/4.0.0}packaging')
        # import pdb; pdb.set_trace()
        if packaging is None or packaging.text != 'pom':
            print("==>", repo)
            single_module.append(repo)
        sleep(5)    

    with open('single_module.txt', 'w') as _file:
        _file.writelines([repo + '\n' for repo in single_module])

if _name_ == '__main__':
    main()