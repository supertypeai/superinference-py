import requests
import re
from datetime import datetime, timedelta
from base64 import b64decode
from rich.console import Console
from rich.theme import Theme

console = Console(theme=Theme({"repr.str":"#54A24B", "repr.number": "#FF7F0E", "repr.none":"#808080"}))

class GithubProfile:
    def __init__(self, username, access_token=None):
        """Github profile inference class

        Args:
            username (str): Github username
            access_token (str, optional): Github access token to increase API rate limit and access private repositories. Defaults to None.
        """
        self.username = username
        self.access_token = access_token
        self.inference = None
        self._api_url = "https://api.github.com"

    def _request(self, url, error_handling=True):
        """Makes a request to the Github API

        Args:
            url (str): URL to be requested
            error_handling (bool, optional): Whether to handle errors or not before returning the response. Defaults to True.

        Returns:
            str: Response from the API
        """
        if self.access_token:
            headers = {"Authorization": "token {}".format(self.access_token)}
            response = requests.get(url, headers=headers)
        else:
            response = requests.get(url)
            
        if error_handling:
            if response.status_code == 200:
                return response
            elif response.status_code == 401:
                if self.access_token:    
                    raise Exception("Invalid access token. Please check your access token and try again.")
                else:
                    raise Exception("This feature requires an access token. Please provide an access token and try again.")
            elif response.status_code == 403:
                if self.access_token:
                    raise Exception("API rate limit exceeded, please try again later.")
                else:
                    raise Exception("API rate limit exceeded, please provide an access token to increase rate limit.")
            elif response.status_code == 404:
                raise Exception("Invalid GitHub username inputted.")
            else:
                raise Exception(f"Error with status code of: {response.status_code}")
        else:
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
            dict: Github profile data
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
        return profile
    

    def _repository_inference(self, top_repo_n=3, include_private=False):
        """Infer data regarding the user's Github repositories

        Args:
            top_repo_n (int, optional): Number of top repositories to be included in the inference. Defaults to 3.
            include_private (bool, optional): Whether to include private repositories in the inference. Defaults to False.

        Returns:
            dict: Github repository data and statistics
        """
        if include_private:
            self._username_token_check()
            repo_url = f"{self._api_url}/user/repos?per_page=100"
        else:
            repo_url = f"{self._api_url}/users/{self.username}/repos?per_page=100"
            
        repos, incomplete_results = self._multipage_request(repo_url)

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
    
    def _contribution_inference(self, original_repo, include_private=False):
        """Infers a user's contributions (issue + PR) to repositories on GitHub.

        Args:
            original_repo(list): Original repository data from _repository_inference().
            include_private (bool, optional): Whether to include private repositories in the inference. Defaults to False.

        Returns:
            dict: Github contribution data and statistics
        """
        if include_private:
            self._username_token_check()
            issue_url = f"{self._api_url}/search/issues?q=type:issue author:{self.username}&sort=author-date&order=desc&per_page=100"
            pr_url = f"{self._api_url}/search/issues?q=type:pr author:{self.username}&sort=author-date&order=desc&per_page=100"
        else:
            issue_url = f"{self._api_url}/search/issues?q=type:issue author:{self.username} is:public&sort=author-date&order=desc&per_page=100"
            pr_url = f"{self._api_url}/search/issues?q=type:pr author:{self.username} is:public&sort=author-date&order=desc&per_page=100"
            
        issue_data, incomplete_issue_results, _ = self._multipage_request(issue_url, "items")
        pr_data, incomplete_pr_results, _ = self._multipage_request(pr_url, "items")
        issues, prs = [], []

        for i in issue_data:
            if i['author_association'] != 'OWNER':
                split_url = i['html_url'].split('/')
                issues.append({
                    'repo_owner': split_url[3],
                })

        for p in pr_data:
            if p['author_association'] != 'OWNER':
                split_url = p['html_url'].split('/')
                prs.append({
                    'merged_at': p['pull_request']['merged_at'],
                    'repo_owner': split_url[3],
                })
                
        merged_pr_count = len([p for p in prs if p['merged_at']])

        contribution_count = {}
        for ip in issues + prs:
            repo_owner = ip['repo_owner']
            contribution_count[repo_owner] = contribution_count.get(repo_owner, 0) + 1

        contribution_count = dict(sorted(contribution_count.items(), key=lambda x: x[1], reverse=True))
        
        data_contrib = []
        for r in original_repo[:10]:
            repo_data, incomplete_repo_results = self._multipage_request(r['contributors_url'])
            data_contrib.extend(repo_data)
        
        incoming_contribution = {}
        for d in data_contrib:
            login = d['login']
            if login != self.username:
                incoming_contribution[login] = incoming_contribution.get(login, 0) + 1
        
        incoming_contribution = dict(sorted(incoming_contribution.items(), key=lambda x: x[1], reverse=True))

        contribution = {'incomplete_issue_results': incomplete_issue_results,
                        'incomplete_pr_results': incomplete_pr_results,
                        'inference_from_issue_count': len(issues),
                        'inference_from_pr_count': len(prs),
                        'merged_pr_count': merged_pr_count,
                        'self_contribution_to_external': contribution_count,
                        'external_contribution_to_self': incoming_contribution
                        }

        return contribution
    
    def _activity_inference(self, include_private=False):
        """Infer data regarding the user's Github activity (commits)

        Args:
            original_repos (dict): Original repository data (from _repo_inference)
            top_repo_n (int, optional): Number of top repositories to be included in the inference. Defaults to 3.
            include_private (bool, optional): Whether to include private repositories in the inference. Defaults to False.

        Returns:
            dict: Github activity data and statistics
        """
        if include_private:
            self._username_token_check()
            commit_url = self._api_url + f"/search/commits?q=committer:{self.username}&sort=committer-date&order=desc&per_page=100"
        else:
            commit_url = self._api_url + f"/search/commits?q=committer:{self.username} is:public&sort=committer-date&order=desc&per_page=100"
        commit_data, incomplete_results, total_count = self._multipage_request(commit_url, "items")

        commits = []
        for c in commit_data:
            commits.append({
            "created_at": c["commit"]["committer"]["date"][:10],
            "repo_owner": c["repository"]["owner"]["login"],
            "repo_owner_type": c["repository"]["owner"]["type"],
            "repo_name": c["repository"]["name"],
            "html_url": c["repository"]["html_url"],
            "description": c["repository"]["description"]
            })
        
        one_year_ago = datetime.now() - timedelta(days=365)
        counts = {
            "day": {},
            "month": {},
            "owned_repo": {},
            "other_repo": {},
            "repo_org_owner": {},
            "repo_user_owner": {},
        }
        for c in commits:
            c_date = datetime.strptime(c["created_at"], "%Y-%m-%d")
            c_day = c_date.strftime("%a")
            c_month = c_date.strftime("%b")
            is_one_year_ago = c_date >= one_year_ago
            
            counts["day"][c_day] = counts["day"].get(c_day, [0, 0])
            if is_one_year_ago:
                counts["day"][c_day][0] += 1
            counts["day"][c_day][1] += 1
            
            counts["month"][c_month] = counts["month"].get(c_month, [0, 0])
            if is_one_year_ago:
                counts["month"][c_month][0] += 1
            counts["month"][c_month][1] += 1
   
            repo_owner, repo_owner_type, repo_name = c["repo_owner"], c["repo_owner_type"], c["repo_name"]
            if repo_owner == self.username:
                counts["owned_repo"][repo_name] = counts["owned_repo"].get(repo_name, 0) + 1
            else:
                counts["other_repo"][repo_name] = counts["other_repo"].get(repo_name, 0) + 1
            if repo_owner_type == "Organization":
                counts["repo_org_owner"][repo_owner] = counts["repo_org_owner"].get(repo_owner, 0) + 1
            else:
                counts["repo_user_owner"][repo_owner] = counts["repo_user_owner"].get(repo_owner, 0) + 1
        
        sorted_counts = {}
        for k in counts:
            if k == "day" or k == "month":
                sorted_counts[k] = dict(sorted(counts[k].items(), key=lambda item: item[1][0], reverse=True))
            else:
                sorted_counts[k] = dict(sorted(counts[k].items(), key=lambda item: item[1], reverse=True))
        
        other_repo_commits = []
        for c in commits:
            if c["repo_owner"] != self.username:
                is_duplicated = any(r["repo_name"] == c["repo_name"] for r in other_repo_commits)
            if not is_duplicated:
                other_repo_commits.append({
                    "repo_name": c["repo_name"],
                    "owner": c["repo_owner"],
                    "html_url": c["html_url"],
                    "description": c["description"],
                    "commits_count": sorted_counts["other_repo"][c["repo_name"]]
                    })
                other_repo_commits.sort(key=lambda x: x["commits_count"], reverse=True)
        
        if len(commits) > 0:
            last_commit_date = datetime.strptime(commits[0]['created_at'], '%Y-%m-%d')
            first_commit_date = datetime.strptime(commits[-1]['created_at'], '%Y-%m-%d')
            total_weeks = round((last_commit_date - first_commit_date).days / 7)
            weekly_avg_commits = round(len(commits) / total_weeks, 3)
        else:
            weekly_avg_commits = 0
            
        activity = {
            'commit_count': total_count,
            'incomplete_commit_results': incomplete_results,
            'inferece_from_commit_count': len(commits),
            'weekly_average_commits': weekly_avg_commits,
            'commit_count_per_day': sorted_counts['day'],
            'commit_count_per_month': sorted_counts['month'],
            'commit_count_per_owned_repo': sorted_counts['owned_repo'],
            'commit_count_per_other_repo': other_repo_commits,
            'commit_count_per_repo_org_owner': sorted_counts['repo_org_owner'],
            'commit_count_per_repo_user_owner': sorted_counts['repo_user_owner'],
        }

        return activity
    
    def _skill_inference(self, bio, original_repos, top_language_n=3):
        """Infer data regarding the user's skills from their Github bio and repositories.

        Args:
            bio (str): The user's Github bio
            original_repos (dict): Original repository data (from _repo_inference)

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
                    languages_count[key] = languages_count.get(key, 0) + 1
            sorted_languages = sorted(languages_count, key=languages_count.get, reverse=True)
            languages_percentage = {lang: round(languages_count[lang] / len(original_repos), 3) for lang in sorted_languages}
        else:
            for r in original_repos:
                languages_count[r["language"]] = languages_count.get(r["language"], 0) + 1
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
        skill = self._skill_inference(bio=profile['bio'], original_repos=repository['original_repos'], top_language_n=top_language_n)
        activity = self._activity_inference(include_private=include_private)
        contribution = self._contribution_inference(include_private=include_private)
        
        self.inference = {
            "profile": profile,
            "skill": skill,
            "stats": repository["stats"],
            "activity": activity,
            "contribution": contribution
        }
        
        console.print(self.inference)