from github import Github
import csv
import datetime
from time import sleep
from sys import argv
import os


# Get token from user and log in
token = argv[1]
to_handle = argv[2]
pos = int(argv[3])
gh = Github(token, per_page=1000)
intervals = []

# Where to write to
exec_space = "exec_space" + token + "/"
try:
    os.mkdir(exec_space)
except:
    ()

# Rate limit
try:
    rl = gh.get_rate_limit()
except:
    print("I am", token)
    sleep(3600)
rate_limit = rl.core.remaining - 100
time_buffer = 120


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
    #rl = gh.get_rate_limit()
    try:
        rl = gh.get_rate_limit()
    except:
        print("Going to sleep for 1h due error in rl = gh.get_rate_limit()")
        sleep(3600)
        rl = gh.get_rate_limit()
    rate_limit = rl.core.remaining - 100


def extract_repo_and_hash(url):
    if len(url) < 34:
        return(None, None)

    repo_and_hash = url[34:]
    slash = 0

    for i in range(len(repo_and_hash)):
        if repo_and_hash[i] == '/':
            slash += 1

        if slash == 2:
            return(repo_and_hash[:i], repo_and_hash[i+1:-1])

    return(None, None)


def write_to_csv(infos, csv_name):
    with open(exec_space + csv_name, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(infos)


def main():
    global rate_limit

    repo_dates = []

    with open(to_handle, 'r') as f:
        reader = csv.reader(f)

        for row in reader:
            repo_name, h = extract_repo_and_hash(row[pos])
            print(repo_name)
            if repo_name is None:
                continue

            if rate_limit < 4:
                wait_till_reset()

            rate_limit -= 3
            repo = gh.get_repo(repo_name)
            commit = repo.get_commit(h)

            coordinates = row[3] + ":" + row[4] + ":" + row[5]
            date = commit.commit.committer.date.isoformat()

            repo_dates.append([coordinates, date])

    write_to_csv(repo_dates, "dates.csv")


main()
