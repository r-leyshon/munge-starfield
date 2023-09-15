from bs4 import BeautifulSoup
import requests
from urllib3.util import Retry
import pandas as pd
import toml
from pyprojroot import here
import time
import re
import matplotlib.pyplot as plt
import seaborn as sns

# configure scraping parameters
CONFIG = toml.load(here("secrets.toml"))
USER_AGENT = CONFIG["SCRAPING"]["USER-AGENT"]
domain = "https://inara.cz"
resources_index_url = domain + "/starfield/resources/"

#### define request retry strategy
retry_strategy = Retry(
    total=4,  # Max No.
    # below codes to retry, have encountered a 500 for this domain
    status_forcelist=[429, 500, 502, 503, 504],
    # ease off the server a bit if we're encountering errors
    backoff_factor=0.1, backoff_max=30
)

# setup the adapter class
adapter = requests.adapters.HTTPAdapter(retry_strategy)

############scraping session 1###############
# Create a new scraping session
session = requests.Session()
# specify secure protocol, let's be safe
session.mount('https://', adapter)
 
response = session.get(
    resources_index_url, headers={"user-agent": USER_AGENT}
    )
content = None
if response.status_code == 200:
    content = response.content
else:
    raise requests.exceptions.RequestException(
        f"Request Error: {response.reason}")

soup = BeautifulSoup(content, "html.parser")

# get all the table data tags
tds = soup.find_all("td")

##### get links to resource detail url

links = [i.find_all("a") for i in tds]
links = [a for a in links if len(a) > 0]

hrefs = []
for i in links:
    for j in i:
        this_href = j.get("href")
        if this_href not in hrefs:
            hrefs.append(this_href)


##### get item rarities
rarities = []
# utility function - regex search tag text
rarities_pat = re.compile("Common|Uncommon|Rare|Exotic|Unique")

for i in tds:
    txt = i.get_text()
    result = rarities_pat.search(txt)
    if bool(result):
        rarities.append(result.group())

    
############scraping session 1###############
# now we have all the links, time to scrape them all
# Create a new scraping session
session1 = requests.Session()
# specify secure protocol, let's be safe
session1.mount('https://', adapter)
soup_list = []
l = len(hrefs)
for ind, i in enumerate(hrefs):
    resp = session1.get(f"{domain}{i}")
    # simple back off, no retry implemented
    time.sleep(0.3)
    if resp.status_code == 200:
        print(f"{ind + 1} of {l} requests returned ok. Let's make soup!")
        resource_soup = BeautifulSoup(resp.content, "html.parser")
        soup_list.append(resource_soup)
    else:
        raise requests.exceptions.RequestException(
            f"Response error: {resp.status_code}: {resp.reason}")


# regex extraction of the required values

# https://regex101.com/r/6NQRh9/1
mass_val_pat = re.compile("(?<=Mass)(.*)(?=Value)")
value_val_pat = re.compile("(?<=Value)\d+")

# https://regex101.com/r/KoQzA2/1
resource_nm_pat = re.compile("[A-Za-z].*(?= - resource)")
entry_dict = dict()

for i in soup_list:
    txt = i.get_text()
    nm = resource_nm_pat.search(txt).group(0)
    g = float(mass_val_pat.search(txt).group(0))
    cred = int(value_val_pat.search(txt).group(0))
    entry_dict[nm] = {"mass": g, "value": cred}


df = pd.DataFrame.from_dict(entry_dict, orient="index")
df["ratio"] = round(df["value"] / df["mass"], 1)
# add in the rarities column
df["rarity"] = rarities
df.sort_values(by="ratio", inplace=True, ascending=False)
# some of the resources should be filtered out
# df[df["ratio"].isna()]
df = df.dropna()
df.to_pickle("starfield-resources.pkl")
