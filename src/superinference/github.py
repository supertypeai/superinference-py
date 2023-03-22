import requests
import re
from datetime import datetime
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
            str: Next link
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
    
    def _multipage_request(self, url, item_name="items", json_key=None):
        """Makes a request to the Github API and handles pagination

        Args:
            url (str): URL to be requested
            item_name (str, optional): Name of the items requested, will be used in the message. Defaults to "items".
            json_key (str, optional): Key of the items in the JSON response. Defaults to None.

        Returns:
            list: List of items
        """
        item_list = []
        message = None
        while url:
            response = self._request(url)
            if json_key:
                item_list.extend(response.json()[json_key])
            else:
                item_list.extend(response.json())
            url = self._parse_next_link(response.headers)
            remaining_rate = int(response.headers["X-Ratelimit-Remaining"])
            if url and remaining_rate == 0:
                message = f"Hey there! Looks like the inference above is from the latest {len(item_list)} {item_name} since you've reached the API rate limit 😉."
                url = None
        return item_list, message
    
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
        profile_data = response.json()
        return {
            "login": profile_data["login"],
            "name": profile_data["name"],
            "company": profile_data["company"],
            "blog": profile_data["blog"],
            "location": profile_data["location"],
            "email": profile_data["email"],
            "hireable": profile_data["hireable"],
            "twitter_username": profile_data["twitter_username"],
            "avatar_url": profile_data["avatar_url"],
            "bio": profile_data["bio"],
            "followers": profile_data["followers"],
            "following": profile_data["following"]
        }
    

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
            
        repos, repo_message = self._multipage_request(repo_url, "repos")

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
            "original_repo_count": len(original_repos),
            "forked_repo_count": len(forked_repos),
            "counts": counts,
            "top_repo_stars_forks": popular_repos,
        }

        return {"stats": stats, "original_repos": original_repos, "repos": repos, "repo_api_message": repo_message}
    
    def _contribution_inference(self, include_private=False):
        """Infer data regarding the user's Github contributions (issues and pull requests)

        Args:
            include_private (bool, optional): Whether to include private repositories in the inference. Defaults to False.

        Returns:
            dict: Github contribution data and statistics
        """
        repo_url = f"{self._api_url}/users/{self.username}/repos?sort=updated&direction=desc&per_page=100"
        if include_private:
            self._username_token_check()
            issue_url = f"{self._api_url}/search/issues?q=type:issue author:{self.username}&sort=author-date&order=desc&per_page=100"
            pr_url = f"{self._api_url}/search/issues?q=type:pr author:{self.username}&sort=author-date&order=desc&per_page=100"
        else:
            issue_url = f"{self._api_url}/search/issues?q=type:issue author:{self.username} is:public&sort=author-date&order=desc&per_page=100"
            pr_url = f"{self._api_url}/search/issues?q=type:pr author:{self.username} is:public&sort=author-date&order=desc&per_page=100"
        
        issue_data, issue_message = self._multipage_request(issue_url, "issues", "items")
        pr_data, pr_message = self._multipage_request(pr_url, "PRs", "items")
        repo_data, ingoing_contribution_message = self._multipage_request(repo_url, "repositories")

        issues, prs, ingoing_contributions =  [], [], {}

        for i in issue_data:
            if i['author_association'] != 'OWNER':
                split_url = i['html_url'].split('/')
                issues.append({
                    'issue_title': i['title'],
                    'created_at': i['created_at'],
                    'state': i['state'],
                    'state_reason': i['state_reason'],
                    'repo_owner': split_url[3],
                    'repo_name': split_url[4],
                    'repo_url': f'https://github.com/{split_url[3]}/{split_url[4]}'
                })

        for p in pr_data:
            if p['author_association'] != 'OWNER':
                split_url = p['html_url'].split('/')
                prs.append({
                    'pr_title': p['title'],
                    'created_at': p['created_at'],
                    'merged_at': p['pull_request']['merged_at'],
                    'state': p['state'],
                    'state_reason': p['state_reason'],
                    'repo_owner': split_url[3],
                    'repo_name': split_url[4],
                    'repo_url': f'https://github.com/{split_url[3]}/{split_url[4]}'
                })
        
        for r in repo_data:
            if not r['fork']:
                repo_contributor, ingoing_contribution_message = self._multipage_request(r['contributors_url'], "contribution")
                
                for contribution in repo_contributor:
                    contributor = contribution['login']
                    if contributor != self.username:
                        ingoing_contributions[contributor]= ingoing_contributions.get(contributor, 0) + contribution['contributions']

        merged_pr_count = len([p for p in prs if p['merged_at']])

        contribution_count = {}
        for ip in issues + prs:
            repo_owner = ip['repo_owner']
            contribution_count[repo_owner] = contribution_count.get(repo_owner, 0) + 1

        contribution_count = dict(sorted(contribution_count.items(), key=lambda x: x[1], reverse=True))
        ingoing_contributions = dict(sorted(ingoing_contributions.items(), key = lambda item: item[1], reverse = True))
        
        contribution = {
                        'issue_count': len(issues),
                        'total_pr_count': len(prs),
                        'merged_pr_count': merged_pr_count,
                        'user_contribution_to_other_repo': contribution_count,
                        'other_contribution_to_user_repo' : ingoing_contributions,
                        'created_issue': issues,
                        'created_pr': prs,
                        'issue_api_message': issue_message,
                        'pr_api_message': pr_message,
                        'contribution_api_message': ingoing_contribution_message
                        }

        return {'contribution': contribution, 'issue_api_message': issue_message, 'pr_api_message': pr_message, 'contribution_api_message' : ingoing_contribution_message}
    
    def _activity_inference(self, original_repos, top_repo_n=3, include_private=False):
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
        commit_data, commit_message = self._multipage_request(commit_url, "commits", "items")

        commits = []
        for c in commit_data:
            commits.append({
            "created_at": c["commit"]["committer"]["date"][:10],
            "repo_owner": c["repository"]["owner"]["login"],
            "repo_owner_type": c["repository"]["owner"]["type"],
            "repo_name": c["repository"]["name"]})

        counts = {
            "date": {},
            "day": {},
            "month": {},
            "owned_repo": {},
            "other_repo": {},
            "repo_org_owner": {},
            "repo_user_owner": {},
        }
        for c in commits:
            c_date = c["created_at"]
            c_day = datetime.strptime(c_date, "%Y-%m-%d").strftime("%a")
            c_month = datetime.strptime(c_date, "%Y-%m-%d").strftime("%b")
            counts["date"][c_date] = counts["date"].get(c_date, 0) + 1
            counts["day"][c_day] = counts["day"].get(c_day, 0) + 1
            counts["month"][c_month] = counts["month"].get(c_month, 0) + 1
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
            if k == 'date':
                sorted_counts[k] = counts[k]
            else:
                sorted_counts[k] = dict(sorted(counts[k].items(), key=lambda x: x[1], reverse=True))
                
        most_active_repo_name = list(sorted_counts['owned_repo'].keys())[:top_repo_n]
        most_active_repo = []
        for r in original_repos:
            if r['name'] in most_active_repo_name:
                most_active_repo.append({
                    'name': r['name'],
                    'html_url': r['html_url'],
                    'description': r['description'],
                    'top_language': r['language'],
                    'commits_count': sorted_counts['owned_repo'][r['name']]
                })
                
        if len(commits) > 0:
            last_commit_date = datetime.strptime(commits[0]['created_at'], '%Y-%m-%d')
            first_commit_date = datetime.strptime(commits[-1]['created_at'], '%Y-%m-%d')
            total_weeks = round((last_commit_date - first_commit_date).days / 7)
            weekly_avg_commits = round(len(commits) / total_weeks, 3)
        else:
            weekly_avg_commits = 0
            
        activity = {
            'commit_count': len(commits),
            'most_active_day': list(sorted_counts['day'].keys())[0] if len(commits) > 0 else None,
            'most_active_month': list(sorted_counts['month'].keys())[0] if len(commits) > 0 else None,
            'weekly_average_commits': weekly_avg_commits,
            'commit_count_per_day': sorted_counts['day'],
            'commit_count_per_month': sorted_counts['month'],
            'commit_count_per_owned_repo': sorted_counts['owned_repo'],
            'commit_count_per_other_repo': sorted_counts['other_repo'],
            'commit_count_per_repo_org_owner': sorted_counts['repo_org_owner'],
            'commit_count_per_repo_user_owner': sorted_counts['repo_user_owner'],
            'commit_api_message': commit_message
        }

        return {'activity': activity, 'most_active_repo': most_active_repo, 'commit_api_message': commit_message}
    
    def _skill_inference(self, bio, original_repos, repo_message, top_language_n=3):
        """Infer data regarding the user's skills from their Github bio and repositories.

        Args:
            bio (str): The user's Github bio
            original_repos (dict): Original repository data (from _repo_inference)
            repo_message (str): Message from _repo_inference
            top_language_n (int): Number of top languages to be included in the inference. Defaults to 3.

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
            languages_percentage = "Sorry, it looks like the information you're requesting is only available for authenticated requests 😔"
        
        return {
            "key_qualifications": key_qualifications, 
            "top_n_languages": sorted_languages[:top_language_n], 
            "languages_percentage": languages_percentage,
            "repo_api_message": repo_message
            }
    
    def perform_inference(self, top_repo_n=3, top_language_n=3, include_private=False):
        """Perform inference on the user's Github profile. This will print out a dictionary that includes data and statistics regarding their profile, repository, skill, activity, and contribution. The dictionary will also be stored in the inference attribute.

        Args:
            top_repo_n (int, optional): Number of top repositories to be included in the inference. Defaults to 3.
            top_language_n (int, optional): Number of top languages to be included in the inference. Defaults to 3.
            include_private (bool, optional): Whether to include private repositories in the inference. Defaults to False.
        """
        profile = self._profile_inference()
        repository = self._repository_inference(top_repo_n=top_repo_n, include_private=include_private)
        skill = self._skill_inference(bio=profile['bio'], original_repos=repository['original_repos'], repo_message=repository['repo_api_message'], top_language_n=top_language_n)
        activity = self._activity_inference(original_repos=repository['original_repos'], top_repo_n=top_repo_n, include_private=include_private)
        contribution = self._contribution_inference(include_private=include_private)
        
        self.inference = {
            "profile": profile,
            "skill": skill,
            "stats": repository["stats"],
            "activity": activity,
            "contribution": contribution
        }
        
        console.print(self.inference)