import requests
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from base64 import b64decode
from rich.console import Console
from rich.theme import Theme


class GithubBaseClass(ABC):
    def __init__(self, access_token=None):
        """Base class for Github inference classes

        Args:
            access_token (str, optional): Github access token to increase API rate limit and access private repositories. Defaults to None.
        """
        self.access_token = access_token
        self.inference = None
        self._api_url = "https://api.github.com"
        self._console = Console(theme=Theme({"repr.str":"#54A24B", "repr.number": "#FF7F0E", "repr.none":"#808080"}))
        
    def _error_handling(self, response, graphql=False):
        """Handles errors from the Github API

        Args:
            response (requests.models.Response): Response from the Github API
        """
        if response.status_code == 200:
            if graphql:
                json_data = response.json()
                if "errors" in json_data and json_data["errors"][0]["message"]:
                    raise Exception(f"GraphQL API query error - \"{json_data['errors'][0]['message']}\"")
            return
        elif response.status_code == 401:
            if self.access_token:    
                raise Exception("Invalid access token. Please check your access token and try again.")
            else:
                raise Exception("`include_private` feature requires an access token. Please provide an access token and try again.")
        elif response.status_code == 403:
            if self.access_token:
                raise Exception("API rate limit exceeded, please try again later.")
            else:
                raise Exception("API rate limit exceeded, please provide an access token to increase rate limit.")
        elif response.status_code == 404:
            raise Exception("The requested data is unavailable. Please ensure that you have entered the correct parameters and try again.")
        else:
            raise Exception(f"Error with status code of: {response.status_code}")
        
    def _request(self, url, error_handling=True):
        """Makes a request to the Github API

        Args:
            url (str): URL to be requested
            error_handling (bool, optional): Whether to handle errors or not before returning the response. Defaults to True.

        Returns:
            requests.models.Response: Response from the Github API
        """
        if self.access_token:
            headers = {"Authorization": "token {}".format(self.access_token)}
            response = requests.get(url, headers=headers)
        else:
            response = requests.get(url)
            
        if error_handling:
            self._error_handling(response)   
        return response
    
    def _parse_next_link(self, headers):
        """Parses the next link from the Github API response headers

        Args:
            headers (dict): Response headers from the Github API

        Returns:
            str: Next link to be requested
        """
        if "Link" in headers:
            links = headers["Link"]
            if 'rel="next"' in links:
                next_link = links.split('rel="next"')[0].strip('<>; ')
                return next_link
            else:
                return None
        else:
            return None
    
    def _multipage_request(self, url, json_key=None):
        """Makes a request to the Github API and handles pagination

        Args:
            url (str): URL to be requested
            json_key (str, optional): Key of the items in the JSON response. Defaults to None.

        Returns:
            item_list (list): List of combined items from all pages
            incomplete_results (bool): Whether the results are incomplete or not (due to hitting rate limits)
            total_count (int): The total count of items for search queries. Only returned for search endpoints.
        
        """
        incomplete_results = False
        item_list = []
        is_search = "/search/" in url
        
        while url:
            response = self._request(url)
            if json_key:
                item_list.extend(response.json()[json_key])
            else:
                item_list.extend(response.json())
            url = self._parse_next_link(response.headers)
            remaining_rate = int(response.headers["X-Ratelimit-Remaining"])
            if url and remaining_rate == 0:
                incomplete_results = True
                url = None
        if is_search:
            total_count = response.json()["total_count"]
            return item_list, incomplete_results, total_count
        else:
            return item_list, incomplete_results
    
    def _graphql_request(self, query):
        """Makes a request to the Github GraphQL API

        Args:
            query (str): GraphQL query to be requested

        Returns:
            requests.models.Response: Response from the Github GraphQL API
        """
        url = f"{self._api_url}/graphql"
        if self.access_token:
            headers = {"Authorization": "token {}".format(self.access_token)}
            response = requests.post(url, headers=headers, json={"query": query})
        else:
            response = requests.post(url)
        self._error_handling(response, graphql=True)
        return response
    
    @abstractmethod
    def perform_inference(self):
        """All subclasses should implement this method
        """
        pass


class GithubProfile(GithubBaseClass):
    def __init__(self, username, access_token=None):
        """Github profile inference class

        Args:
            username (str): Github username
            access_token (str, optional): Github access token to increase API rate limit and access private repositories. Defaults to None.
        """
        self.username = username
        super().__init__(access_token)
    
    def _username_token_check(self):
        """Checks if the Github username is associated with the provided access token, which is called when the user wants to include private repositories"""
        test_url = f"{self._api_url}/user"
        response = self._request(test_url)
        associated_username = response.json()['login']
        if associated_username != self.username:
            raise Exception("If you want to include private repositories, please ensure that the Github username is associated with the provided access token.")
        
    def _profile_inference(self):
        """Infer data regarding the user's Github profile

        Returns:
            dict: Github profile data and creation date
        """
        profile_url = f"{self._api_url}/users/{self.username}"
        response = self._request(profile_url)
        json_data = response.json()
        profile =  {
            "login": json_data["login"],
            "name": json_data["name"],
            "company": json_data["company"],
            "blog": json_data["blog"],
            "location": json_data["location"],
            "email": json_data["email"],
            "hireable": json_data["hireable"],
            "twitter_username": json_data["twitter_username"],
            "avatar_url": json_data["avatar_url"],
            "bio": json_data["bio"],
            "followers": json_data["followers"],
            "following": json_data["following"]
        }
        return {"data": profile, "created_at": json_data['created_at']}
    

    def _repository_inference(self, top_repo_n=3, include_private=False):
        """Infer data regarding the user's Github repositories

        Args:
            top_repo_n (int, optional): Number of top repositories to be included in the inference. Defaults to 3.
            include_private (bool, optional): Whether to include private repositories in the inference. Defaults to False.

        Returns:
            dict: Github repositories statistics and list of original repositories
        """
        if include_private:
            self._username_token_check()
            user_repos_url = f"{self._api_url}/user/repos?per_page=100"
        else:
            user_repos_url = f"{self._api_url}/users/{self.username}/repos?per_page=100"
            
        repos, incomplete_results = self._multipage_request(user_repos_url)

        repos.sort(
            key=lambda r: r["stargazers_count"] + r["forks_count"],
            reverse=True,
        )

        original_repos, forked_repos = [], []
        for r in repos:
            if r["fork"] == False and r['owner']['login'] == self.username:
                original_repos.append(r)
            elif r["fork"] == True and r['owner']['login'] == self.username:
                forked_repos.append(r)

        counts = {"stargazers_count": 0, "forks_count": 0}
        for r in original_repos:
            counts["stargazers_count"] += r["stargazers_count"]
            counts["forks_count"] += r["forks_count"]

        popular_repos = []
        for r in original_repos[:top_repo_n]:
            popular_repos.append(
                {
                    "name": r["name"],
                    "html_url": r["html_url"],
                    "description": r["description"],
                    "top_language": r["language"],
                    "stargazers_count": r["stargazers_count"],
                    "forks_count": r["forks_count"],
                }
            )

        stats = {
            "incomplete_repo_results": incomplete_results,
            "inference_from_repo_count": len(repos),
            "original_repo_count": len(original_repos),
            "forked_repo_count": len(forked_repos),
            "counts": counts,
            "top_repo_stars_forks": popular_repos,
        }

        return {"stats": stats, "original_repos": original_repos}
    
    def _contribution_inference(self, created_profile_date, original_repos, include_private=False):
        """Infers data regarding a user's contributions to repositories on GitHub.

        Args:
            created_profile_date (str): The user's Github profile creation date (from `_profile_inference()`)
            original_repos (list): Original repository data (from `_repository_inference()`)
            include_private (bool, optional): Whether to include private repositories in the inference. Defaults to False.

        Returns:
            dict: Github contribution statistics
        """
        if not self.access_token:
            return None
        
        created_date = datetime.strptime(created_profile_date, "%Y-%m-%dT%H:%M:%SZ")
        created_year = created_date.year
        today = datetime.now()
        current_year = today.year
        
        def query_pattern_day(start_date, end_date):
            return f"""
                query {{
                    user(login: "{self.username}") {{
                        contributionsCollection(from: "{start_date.isoformat()}", to: "{end_date.isoformat()}") {{
                            contributionCalendar {{
                                totalContributions
                                weeks {{
                                    contributionDays {{
                                        date
                                        contributionCount
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            """
        
        contribution_detail = """
            repository {
                description
                name
                url
                languages(first: 1, orderBy: {field: SIZE, direction: DESC}) {
                    nodes {
                        name
                    }
                }
                owner {
                    __typename
                    ... on User {
                        login
                    }
                    ... on Organization {
                        login
                    }
                }
                isPrivate
            }
            contributions {
                totalCount
            }
        """
        
        def query_pattern_repo(start_date, end_date):
            return f"""
                query {{
                    user(login: "{self.username}") {{
                        contributionsCollection(from: "{start_date.isoformat()}", to: "{end_date.isoformat()}") {{
                            commitContributionsByRepository(maxRepositories: 100) {{
                                {contribution_detail}
                            }}
                            issueContributionsByRepository(maxRepositories: 100) {{
                                {contribution_detail}
                            }}
                            pullRequestContributionsByRepository(maxRepositories: 100) {{
                                {contribution_detail}
                            }}
                            pullRequestReviewContributionsByRepository(maxRepositories: 100) {{
                                {contribution_detail}
                            }}
                        }}
                    }}
                }}
            """
        
        contributions_per_day = []
        contributions_per_repo = []
        contributions_count = 0
        for i in range(created_year, current_year + 1):
            if i == created_year:
                query_day = query_pattern_day(created_date, datetime(i, 12, 31))
                query_repo = query_pattern_repo(created_date, datetime(i, 12, 31))
            elif i == current_year:
                query_day = query_pattern_day(datetime(i, 1, 1), today)
                query_repo = query_pattern_repo(datetime(i, 1, 1), today)
            else:
                query_day = query_pattern_day(datetime(i, 1, 1), datetime(i, 12, 31))
                query_repo = query_pattern_repo(datetime(i, 1, 1), datetime(i, 12, 31))

            response_day = self._graphql_request(query_day)
            day_data = response_day.json()['data']
            new_contribution_day=[]
            for week in day_data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
                new_contribution_day.extend([day for day in week["contributionDays"]])
            contributions_per_day.extend(new_contribution_day)
            contributions_count += day_data["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]

            response_repo = self._graphql_request(query_repo)
            repo_data = response_repo.json()['data']
            def extract_repo_detail(repository, contributions):
                return {
                    "name": repository['name'],
                    "owner": repository['owner']['login'],
                    "owner_type": repository['owner']["__typename"],
                    "html_url": repository['url'],
                    "description": repository['description'],
                    "top_language": repository['languages']['nodes'][0]['name'].lower().replace(" ", "-") if repository['languages']['nodes'] else None,
                    "contributions_count": contributions['totalCount'],
                    "is_private": repository['isPrivate']
                }
            new_commits = [extract_repo_detail(item['repository'], item['contributions']) for item in repo_data['user']['contributionsCollection']['commitContributionsByRepository']]
            new_issues = [extract_repo_detail(item['repository'], item['contributions']) for item in repo_data['user']['contributionsCollection']['issueContributionsByRepository']]
            new_pr = [extract_repo_detail(item['repository'], item['contributions']) for item in repo_data['user']['contributionsCollection']['pullRequestContributionsByRepository']]
            new_pr_review = [extract_repo_detail(item['repository'], item['contributions']) for item in repo_data['user']['contributionsCollection']['pullRequestReviewContributionsByRepository']]
            contributions_per_repo.extend(new_commits + new_issues + new_pr + new_pr_review)
            
        if not include_private:
            contributions_per_repo = [repo for repo in contributions_per_repo if not repo['is_private']]
            
        one_year_ago = datetime.now() - timedelta(days=365)
        count = {"day": {}, "month": {}}
        for c in contributions_per_day:
            c_date = datetime.strptime(c["date"], "%Y-%m-%d")
            c_day = c_date.strftime("%a")
            c_month = c_date.strftime("%b")
            is_one_year_ago = c_date >= one_year_ago
            
            count["day"][c_day] = count["day"].get(c_day, [0, 0])
            if is_one_year_ago:
                count["day"][c_day][0] += c['contributionCount']
            count["day"][c_day][1] +=  c['contributionCount']
            
            count["month"][c_month] = count["month"].get(c_month, [0, 0])
            if is_one_year_ago:
                count["month"][c_month][0] += c['contributionCount']
            count["month"][c_month][1] += c['contributionCount']
            
        final_count = {
            "day": count["day"],
            "month": count["month"],
            "owned_repo": {},
            "other_repo": [],
            "User": {},
            "Organization": {},
        }
        
        for c in contributions_per_repo:
            repo_type = "owned_repo" if c['owner'] == self.username else "other_repo"

            if repo_type == "owned_repo":
                final_count[repo_type][c['name']] = final_count[repo_type].get(c['name'], 0) + c['contributions_count']
            else:
                index = next((i for i, obj in enumerate(final_count[repo_type]) if obj['html_url'] == c['html_url']), -1)
                if index == -1:
                    data = {k: v for k, v in c.items() if k not in ["owner_type", "is_private"]}
                    final_count[repo_type].append(data)             
                else:
                    final_count[repo_type][index]["contributions_count"] += c['contributions_count']      

            final_count[c['owner_type']][c['owner']] = final_count[c['owner_type']].get(c['owner'], 0) + c['contributions_count']

        sorted_count = {}
        for k, v in final_count.items():
            if k == "day" or k == "month":
                sorted_count[k] = dict(sorted(v.items(), key=lambda item: item[1][0], reverse=True))
            elif k == "other_repo":
                sorted_count[k] = sorted(v, key=lambda v: v["contributions_count"], reverse=True)
            else:
                sorted_count[k] = dict(sorted(v.items(), key=lambda item: item[1], reverse=True))
            
        total_weeks = round((today - created_date).days / 7)
        weekly_avg_contributions = round(contributions_count / total_weeks, 3)
        
        contrib_data = []
        for r in original_repos[:10]:
            response = self._request(r['contributors_url'])
            repo_data = response.json()
            contrib_data.extend(repo_data)

        incoming_contribution = {}
        for d in contrib_data:
            login = d['login']
            if login != self.username:
                incoming_contribution[login] = incoming_contribution.get(login, 0) + d['contributions']

        sorted_incoming_contribution = dict(sorted(incoming_contribution.items(), key=lambda item: item[1], reverse=True))
        
        contribution = {
            'contribution_count': contributions_count,
            'weekly_average_contribution': weekly_avg_contributions,
            'contribution_count_per_day': sorted_count["day"],
            'contribution_count_per_month': sorted_count["month"],
            'contribution_count_per_owned_repo': sorted_count["owned_repo"],
            'contribution_count_per_other_repo': sorted_count["other_repo"],
            'contribution_count_per_repo_org_owner': sorted_count["Organization"],
            'contribution_count_per_repo_user_owner': sorted_count["User"],
            'external_contribution_to_top_10_repo': sorted_incoming_contribution
        }
        
        return contribution
    
    def _skill_inference(self, bio, original_repos, top_language_n=3):
        """Infer data regarding the user's skills from their Github bio and repositories.

        Args:
            bio (str): The user's Github bio
            original_repos (dict): Original repository data from _repository_inference()
            top_language_n (int, optional): The number of top languages to consider. Defaults to 3.

        Returns:
            dict: Inferred data regarding the user's skills
        """
        response = requests.get("https://raw.githubusercontent.com/supertypeai/collective/main/src/data/profileTagsChoices.json")
        keywords = response.json()
        
        labels = [item["label"].lower() for item in keywords]
        values = [item["value"].replace("-", " ").lower() for item in keywords]
        keywords_set = set(labels + values)
        
        profile_keywords = set()
        
        if bio:
            decode_bio = re.sub(re.compile("\\n|###|'|ð|http[s]?://\S+|[\(\[].*?[\)\]]|<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});"),'',bio).lower()
            bio_keywords = {word for word in keywords_set if re.search(rf"\b{word}\b", decode_bio, re.IGNORECASE)}
            profile_keywords.update(bio_keywords)
        
        readme_url = f"{self._api_url}/repos/{self.username}/{self.username}/contents/README.md"
        response = self._request(readme_url, error_handling=False)
        readme_data = response.json()
        if 'content' in readme_data:
            decode_readme = b64decode(readme_data['content']).decode()
            decode_readme = re.sub(re.compile("\\n|###|'|ð|http[s]?://\S+|[\(\[].*?[\)\]]|<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});"),'',decode_readme).lower()
            readme_keywords = {word for word in keywords_set if re.search(rf"\b{word}\b", decode_readme, re.IGNORECASE)}
            profile_keywords.update(readme_keywords)
        
        keywords_from_values = {word.replace(" ", "-").replace("/", "-") for word in values if word in profile_keywords}

        capitalized_profile_keywords = {word.title() for word in profile_keywords}

        keywords_from_labels = {item["value"] for item in keywords if item["label"].title() in capitalized_profile_keywords}

        key_qualifications = list(keywords_from_values | keywords_from_labels)

        languages_count = {}
        if self.access_token:
            for r in original_repos:
                response = self._request(r["languages_url"])
                r_lang = response.json()
                for key in r_lang.keys():
                    formatted_key = key.replace(" ", "-").lower()
                    languages_count[formatted_key] = languages_count.get(formatted_key, 0) + 1
            sorted_languages = sorted(languages_count, key=languages_count.get, reverse=True)
            languages_percentage = {lang: round(languages_count[lang] / len(original_repos), 3) for lang in sorted_languages}
        else:
            for r in original_repos:
                if r['language']:
                    formatted_lang = r["language"].replace(" ", "-").lower()
                    languages_count[formatted_lang] = languages_count.get(formatted_lang, 0) + 1
            sorted_languages = sorted(languages_count, key=languages_count.get, reverse=True)
            languages_percentage = None
        
        skill = {
            "inference_from_originalrepo_count": len(original_repos),
            "key_qualifications": key_qualifications, 
            "top_n_languages": sorted_languages[:top_language_n], 
            "languages_percentage": languages_percentage,
            }
        
        return skill
    
    def perform_inference(self, top_repo_n=3, top_language_n=3, include_private=False):
        """Perform inference on the user's Github profile. This will print out a dictionary that includes data and statistics regarding their profile, repository, skill, activity, and contribution. The dictionary will also be stored in the inference attribute.

        Args:
            top_repo_n (int, optional): Number of top repositories to be included in the inference. Defaults to 3.
            top_language_n (int, optional): Number of top languages to be included in the inference. Defaults to 3.
            include_private (bool, optional): Whether to include private repositories in the inference. Defaults to False.
        """
        profile = self._profile_inference()
        repository = self._repository_inference(top_repo_n=top_repo_n, include_private=include_private)
        skill = self._skill_inference(bio=profile['data']['bio'], original_repos=repository['original_repos'], top_language_n=top_language_n)
        contribution = self._contribution_inference(created_profile_date=profile['created_at'], original_repos=repository['original_repos'], include_private=include_private)
        
        self.inference = {
            "profile": profile['data'],
            "skill": skill,
            "stats": repository["stats"],
            # "activity": activity,
            "contribution": contribution
        }
        
        self._console.print(self.inference)
        

class GithubRepo(GithubBaseClass):
    def __init__(self, repo_owner, repo_name, access_token=None):
        """Github repo inference class

        Args:
            repo_owner (str): The Github username of the repository owner
            repo_name (str): The name of the repository
            access_token (str, optional): Github access token to increase API rate limit and access private repositories. Defaults to None.
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        super().__init__(access_token)
        
    
    def perform_inference(self):
        """Perform inference on the Github repository. This will print out a dictionary that includes data and statistics regarding the repository along with its contributions and events. The dictionary will also be stored in the inference attribute.

        Returns:
            dict: Data about the repository
        """
        repo_url = f"{self._api_url}/repos/{self.repo_owner}/{self.repo_name}"
        response = self._request(repo_url)
        repo_data = response.json()
        
        repo_language = self._request(repo_data["languages_url"]).json()
        language_data = {lang: round(bytes / sum(repo_language.values()), 3) for lang, bytes in repo_language.items()}
        
        events_url = f"{repo_data['events_url']}?per_page=100"
        repo_events, incomplete_events = self._multipage_request(events_url)
        event_type_count = {}
        for event in repo_events:
            event_type_count[event['type']] = event_type_count.get(event['type'], 0) + 1
            
        contributors_url = f"{repo_data['contributors_url']}?per_page=100"
        repo_contributors, incomplete_contributors = self._multipage_request(contributors_url)
        total_contributions = sum(contributor['contributions'] for contributor in repo_contributors)
        total_contributors = len(repo_contributors)
        
        contributions_data = []
        for user in repo_contributors:
            contributions_data.append(
            {'contributor_username': user['login'],
            'contributor_html_url': user['html_url'],
            'contributor_repos_url': user['repos_url'],
            'contributor_type': user['type'],
            'contributions': user['contributions'],
            'contributions_percentage': round(user['contributions'] / total_contributions, 3)}
            )
        
        self.inference = {"name": repo_data["name"],
                "html_url": repo_data["html_url"],
                "description": repo_data["description"],
                "owner_username": repo_data["owner"]["login"],
                "owner_html_url": repo_data["owner"]["html_url"],
                "topic": repo_data["topics"],
                "visibility": repo_data["visibility"],
                "created_at": repo_data["created_at"],
                "last_pushed_at": repo_data["pushed_at"],
                "top_language": repo_data["language"],
                "languages_percentage": language_data,
                "stargazers_count": repo_data["stargazers_count"],
                "forks_count": repo_data["forks_count"],
                "watchers_count": repo_data["watchers_count"],
                "subscribers_count": repo_data["subscribers_count"],
                "open_issues_count": repo_data["open_issues_count"],
                "incomplete_contribution_results": incomplete_contributors,
                "contributors_count": total_contributors,
                "contributions_count": total_contributions,
                "contributions": contributions_data,
                "incomplete_event_results": incomplete_events,
                "events_count": event_type_count}
        
        self._console.print(self.inference)

        
        
        