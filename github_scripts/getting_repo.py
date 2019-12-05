'''
Requirements: github3
pip install github3

'''

from github3 import login
from time import sleep

# REPO_QUERY = 'language:java pushed:>2016-12 stars:>500'
# REPO_QUERY = 'language:java pushed:>2016-12 size:>300000'
REPO_QUERY = 'language:java pushed:>2016-12'
# This query searches for a repo with a file named pom.xml containg junit
JUNIT_QUERY = 'junit in:content path [dontcare]  extension:xml filename:pom repo:{}'
# The same but with io.cucumber
CUCUMBER_QUERY = 'io.cucumber in:content path [dontcare]  extension:xml filename:pom repo:{}'
REPORT_LINE = '{} {} {}\n'

TOKEN = 'use your own token :P'


def main():
    output = open('cucumber-java.txt', 'w')
    gh = login(token=TOKEN)
    repositories = gh.search_repositories(
        REPO_QUERY, sort='stars', per_page=100)
    for result in repositories:
        repo = result.repository
        print('Inspecting', repo.full_name)
        code_matchs = gh.search_code(CUCUMBER_QUERY.format(repo.full_name))
        try:
            code_matchs.next()  # If can advance there is at least one
            print('junit found')
            #output.write(REPORT_LINE.format(repo.full_name, repo.stargazers, repo.size))
            output.write(repo.git_url)
            sleep(1)
        except StopIteration:
            pass
        sleep(3)
    output.close()


if __name__ == '__main__':
    main()
